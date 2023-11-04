import logging
import os
import concurrent.futures

from localstack.aws.handlers import serve_custom_service_request_handlers
from localstack.services.plugins import SERVICE_PLUGINS, Service
from localstack.aws.api import RequestContext
from localstack.services.s3.v3.provider import S3Provider as S3V3Provider
from localstack.services.s3.v3.storage.ephemeral import EphemeralS3ObjectStore
from threading import Thread, Condition

from .visitors import LoadStateVisitor, SaveStateVisitor
from .config import BASE_DIR, is_persistence_enabled
from .prepare_service import prepare_service

LOG = logging.getLogger(__name__)

IDEMPOTENT_VERBS = ["GET", "HEAD", "QUERY", "LIST", "DESCRIBE"]


def lazy_load(service_name: str):
    # Lambda relies on other services being ready
    return service_name == "lambda"


def invoke_hooks(service_name: str):
    # Both lambda and opensearch must intialise their runtimes after loading state.
    return service_name == "lambda" or service_name == "opensearch"


class StateTracker:
    def __init__(self):
        self.affected_services = set()
        self.loaded_services = set()
        self.cond = Condition()
        self.is_running = False

    def start(self):
        assert not self.is_running
        self.is_running = True
        serve_custom_service_request_handlers.append(self.on_request)
        Thread(target=self._run).start()

    def stop(self):
        assert self.is_running
        self.is_running = False
        with self.cond:
            self.save_all_services_state()
            self.cond.notify()

    def on_request(self, _chain, context: RequestContext, _res):
        if not context.service or not context.request or not context.operation:
            return

        service_name = context.service.service_name

        if not is_persistence_enabled(service_name):
            return

        prepare_service(service_name)

        # Does the service need lazy loading of state?
        if lazy_load(service_name):
            with self.cond:
                if service_name not in self.loaded_services:
                    self._load_service_state(service_name)

        op = context.operation.name.upper()
        if context.request.method in IDEMPOTENT_VERBS or any(
            op.startswith(v) for v in IDEMPOTENT_VERBS
        ):
            return

        self.add_affected_service(service_name)

    def load_all_services_state(self):
        LOG.info("Loading persisted state of all services...")
        if not os.path.exists(BASE_DIR):
            return

        with os.scandir(BASE_DIR) as it:
            for entry in it:
                if is_persistence_enabled(entry.name) and not lazy_load(entry.name):
                    if not entry.is_dir():
                        LOG.warning("Expected %s to be a directory", entry.path)
                        continue

                    self._load_service_state(entry.name)

    def save_all_services_state(self):
        with self.cond:
            if not self.affected_services:
                LOG.debug("Nothing to persist - no services were changed")
                return

            LOG.debug("Persisting state of services: %s", self.affected_services)

            for service_name in self.affected_services:
                if is_persistence_enabled(service_name):
                    self._save_service_state(service_name)

            LOG.debug("Finished persisting %d services.", len(self.affected_services))

            self.affected_services.clear()

    def add_affected_service(self, service_name: str):
        with self.cond:
            self.affected_services.add(service_name)

    def _run(self):
        while self.is_running:
            with self.cond:
                self.save_all_services_state()
                self.cond.wait(10)

    def _load_service_state(self, service_name: str):
        LOG.info("Loading persisted state of service %s...", service_name)
        prepare_service(service_name)
        self.loaded_services.add(service_name)

        service = SERVICE_PLUGINS.get_service(service_name)
        if not service:
            LOG.warning(
                "No service %s found in service manager",
                service_name,
            )
            return

        should_invoke_hooks = invoke_hooks(service_name)
        try:
            if should_invoke_hooks:
                service.lifecycle_hook.on_before_state_load()
            self._invoke_visitor(LoadStateVisitor(service_name), service)
            if should_invoke_hooks:
                service.lifecycle_hook.on_after_state_load()
        except:
            LOG.exception("Error while loading state of service %s", service_name)

    def _save_service_state(self, service_name: str):
        LOG.info("Persisting state of service %s...", service_name)

        service = SERVICE_PLUGINS.get_service(service_name)
        if not service:
            LOG.error("No service %s found in service manager", service_name)
            return

        try:
            service.lifecycle_hook.on_before_state_save()
            self._invoke_visitor(SaveStateVisitor(service_name), service)
            service.lifecycle_hook.on_after_state_save()
        except:
            LOG.exception("Error while persisting state of service %s", service_name)

    @staticmethod
    def _invoke_visitor(visitor: SaveStateVisitor | LoadStateVisitor, service: Service):
        service.accept_state_visitor(visitor)
        if (backend := getattr(service._provider, "_storage_backend", None)) and (
            isinstance(backend, EphemeralS3ObjectStore)
        ):
            visitor.visit(backend)


STATE_TRACKER = StateTracker()
