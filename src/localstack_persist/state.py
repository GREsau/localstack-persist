import logging
import os

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

        if not is_persistence_enabled(context.service.service_name):
            return

        prepare_service(context.service.service_name)

        if context.service.service_name == "lambda":
            self._init_lambda()

        op = context.operation.name.upper()
        if context.request.method in IDEMPOTENT_VERBS or any(
            op.startswith(v) for v in IDEMPOTENT_VERBS
        ):
            return

        with self.cond:
            self.affected_services.add(context.service.service_name)

    def load_all_services_state(self):
        LOG.info("Loading persisted state of all services...")
        if not os.path.exists(BASE_DIR):
            return

        with os.scandir(BASE_DIR) as it:
            for entry in it:
                # lambda is a special case, as it requires on_after_state_load() which starts some services
                if is_persistence_enabled(entry.name) and entry.name != "lambda":
                    if not entry.is_dir():
                        LOG.warning("Expected %s to be a directory", entry.path)
                        continue

                    self._load_service_state(entry.name)

    def save_all_services_state(self):
        LOG.debug("Persisting state of all services...")
        with self.cond:
            if not self.affected_services:
                LOG.debug("Nothing to persist - no services were changed")
                return

            for service_name in self.affected_services:
                if is_persistence_enabled(service_name):
                    self._save_service_state(service_name)

            self.affected_services.clear()

    def _run(self):
        while self.is_running:
            with self.cond:
                self.save_all_services_state()
                self.cond.wait(10)

    def _load_service_state(self, service_name: str, invoke_hooks=False):
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

        try:
            if invoke_hooks:
                service.lifecycle_hook.on_before_state_load()
            self._invoke_visitor(LoadStateVisitor(), service)
            if invoke_hooks:
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
            self._invoke_visitor(SaveStateVisitor(), service)
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

    def _init_lambda(self):
        with self.cond:
            if "lambda" not in self.loaded_services:
                self._load_service_state("lambda", invoke_hooks=True)


STATE_TRACKER = StateTracker()
