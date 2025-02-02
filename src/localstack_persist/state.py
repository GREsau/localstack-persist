import logging
import os
from typing import cast

from localstack.aws.handlers import (
    serve_custom_service_request_handlers,
    run_custom_response_handlers,
    run_custom_finalizers,
)
from localstack.services.plugins import SERVICE_PLUGINS
from localstack.aws.api import RequestContext
from collections import defaultdict
from threading import Thread, Condition
from readerwriterlock.rwlock import RWLockWrite, Lockable
from .visitors import LoadStateVisitor, SaveStateVisitor
from .config import BASE_DIR, is_persistence_enabled, PERSIST_FREQUENCY
from .prepare_service import prepare_service

LOG = logging.getLogger(__name__)

IDEMPOTENT_VERBS = ["GET", "HEAD", "QUERY", "LIST", "DESCRIBE"]


def lazy_load(service_name: str):
    # Lambda relies on other services being ready
    return service_name == "lambda"


def invoke_load_hooks(service_name: str):
    # Both lambda and opensearch must intialise their runtimes after loading state.
    return service_name == "lambda" or service_name == "opensearch"


class StateTracker:
    def __init__(self):
        self.affected_services = set()
        self.loaded_services = set()
        self.cond = Condition()
        self.is_running = False
        self.rwlocks = defaultdict[str, RWLockWrite](lambda: RWLockWrite())

    def start(self):
        assert not self.is_running
        self.is_running = True
        serve_custom_service_request_handlers.append(self.on_request)
        run_custom_response_handlers.append(self.on_response)
        run_custom_finalizers.append(self.on_finalize)
        Thread(target=self._run).start()

    def stop(self):
        assert self.is_running
        self.is_running = False
        with self.cond:
            self.save_all_services_state()
            self.cond.notify()

    def on_request(self, chain, context: RequestContext, response):
        if not context.service:
            return

        service_name = context.service.service_name

        if not is_persistence_enabled(service_name):
            return

        prepare_service(service_name)

        # Does the service need lazy loading of state?
        if lazy_load(service_name) and service_name not in self.loaded_services:
            with self.cond:
                if service_name not in self.loaded_services:
                    self._load_service_state(service_name)

        # Prevent persistence from running for this service while handling this request
        rlock = self.rwlocks[service_name].gen_rlock()
        setattr(context, "localstack-persist_rlock", rlock)
        rlock.acquire()

    def on_response(self, chain, context: RequestContext, response):
        if not context.service or not context.request or not context.operation:
            return

        service_name = context.service.service_name

        if not is_persistence_enabled(service_name):
            return

        op = context.operation.name.upper()
        if context.request.method in IDEMPOTENT_VERBS or any(
            op.startswith(v) for v in IDEMPOTENT_VERBS
        ):
            return

        self.add_affected_service(service_name)

    def on_finalize(self, chain, context: RequestContext, response):
        if rlock := getattr(context, "localstack-persist_rlock", None):
            cast(Lockable, rlock).release()

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

            affected_services = list(self.affected_services)
            self.affected_services.clear()

            LOG.debug("Persisting state of services: %s", affected_services)

            for service_name in affected_services:
                if is_persistence_enabled(service_name):
                    try:
                        self._save_service_state(service_name)
                    except:
                        LOG.exception(
                            "Error while persisting state of service %s", service_name
                        )
                        self.affected_services.add(service_name)

            LOG.debug("Finished persisting %d services.", len(affected_services))

    def add_affected_service(self, service_name: str):
        self.affected_services.add(service_name)

    def _run(self):
        while self.is_running:
            with self.cond:
                self.save_all_services_state()
                self.cond.wait(PERSIST_FREQUENCY)

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

        should_invoke_hooks = invoke_load_hooks(service_name)
        try:
            if should_invoke_hooks:
                service.lifecycle_hook.on_before_state_load()
            service.accept_state_visitor(LoadStateVisitor(service_name))
            if should_invoke_hooks:
                service.lifecycle_hook.on_after_state_load()
            LOG.debug("Finished loading persisted state of service %s", service_name)
        except:
            LOG.exception("Error while loading state of service %s", service_name)

    def _save_service_state(self, service_name: str):
        service = SERVICE_PLUGINS.get_service(service_name)
        if not service:
            LOG.error("No service %s found in service manager", service_name)
            return

        with self.rwlocks[service_name].gen_wlock():
            LOG.info("Persisting state of service %s...", service_name)
            service.lifecycle_hook.on_before_state_save()
            service.accept_state_visitor(SaveStateVisitor(service_name))
            service.lifecycle_hook.on_after_state_save()
            LOG.debug("Finished persisting state of service %s", service_name)


STATE_TRACKER = StateTracker()
