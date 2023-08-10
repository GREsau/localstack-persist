import logging
import os
from importlib import import_module
import sys

from localstack.aws.handlers import serve_custom_service_request_handlers
from localstack.services.plugins import SERVICE_PLUGINS
from localstack.aws.chain import Handler as OnRequestHandler
from localstack.aws.api import RequestContext
from threading import Thread, Condition

from .visitors import LoadStateVisitor, SaveStateVisitor
from .config import BASE_DIR, should_persist

LOG = logging.getLogger(__name__)


class StateTracker:
    def __init__(self):
        self.affected_services = set()
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
        if context.service and context.service.service_name:
            with self.cond:
                self.affected_services.add(context.service.service_name)

    def load_all_services_state(self):
        LOG.info("Loading persisted state of all services...")
        if not os.path.exists(BASE_DIR):
            return

        with os.scandir(BASE_DIR) as it:
            for entry in it:
                if should_persist(entry.name):
                    self._load_service_state(entry)

    def save_all_services_state(self):
        LOG.debug("Persisting state of all services...")
        with self.cond:
            if not self.affected_services:
                LOG.debug("Nothing to persist - no services were changed")
                return

            for service_name in self.affected_services:
                if should_persist(service_name):
                    self._save_service_state(service_name)

            self.affected_services.clear()

    def _run(self):
        while self.is_running:
            with self.cond:
                self.save_all_services_state()
                self.cond.wait(10)

    def _load_service_state(self, entry: os.DirEntry):
        LOG.info("Loading persisted state of service %s...", entry.name)

        if not entry.is_dir():
            LOG.warning("Expected %s to be a directory", entry.path)
            return

        service = SERVICE_PLUGINS.get_service(entry.name)
        if not service:
            LOG.warning(
                "No service %s found in service manager",
                entry.name,
            )
            return

        if entry.name == "lambda":
            # Define localstack.services.awslambda as a backward-compatible alias for localstack.services.lambda_
            # (and vice-versa for easy forward-compatibility)
            try:
                sys.modules.setdefault(
                    "localstack.services.awslambda",
                    import_module("localstack.services.lambda_"),
                )
            except ModuleNotFoundError:
                sys.modules.setdefault(
                    "localstack.services.lambda_",
                    import_module("localstack.services.awslambda"),
                )

        try:
            service.accept_state_visitor(LoadStateVisitor())
            # Do NOT call service.lifecycle_hook.on_after_state_load(), as that would prematurely start the service
        except:
            LOG.exception("Error while loading state of service %s", entry.name)

    def _save_service_state(self, service_name: str):
        LOG.info("Persisting state of service %s...", service_name)

        service = SERVICE_PLUGINS.get_service(service_name)
        if not service:
            LOG.error("No service %s found in service manager", service_name)
            return

        try:
            service.lifecycle_hook.on_before_state_save()
            service.accept_state_visitor(SaveStateVisitor())
            service.lifecycle_hook.on_after_state_save()
        except:
            LOG.exception("Error while persisting state of service %s", service_name)


STATE_TRACKER = StateTracker()
