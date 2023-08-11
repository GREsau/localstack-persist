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
from .jsonpickle import fix_dict_pickling, unfix_dict_pickling

LOG = logging.getLogger(__name__)


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
        if context.service and context.service.service_name:
            with self.cond:
                if (
                    context.service.service_name == "lambda"
                    and "lambda" not in self.loaded_services
                    and should_persist("lambda")
                ):
                    unfix_dict_pickling()
                    try:
                        self._setup_lambda_compatibility()
                        self._load_service_state("lambda", invoke_hooks=True)
                    finally:
                        fix_dict_pickling()
                self.affected_services.add(context.service.service_name)

    def load_all_services_state(self):
        LOG.info("Loading persisted state of all services...")
        if not os.path.exists(BASE_DIR):
            return

        with os.scandir(BASE_DIR) as it:
            for entry in it:
                if should_persist(entry.name) and entry.name != "lambda":
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
                if should_persist(service_name):
                    self._save_service_state(service_name)

            self.affected_services.clear()

    def _run(self):
        while self.is_running:
            with self.cond:
                self.save_all_services_state()
                self.cond.wait(10)

    def _load_service_state(self, service_name: str, invoke_hooks=False):
        LOG.info("Loading persisted state of service %s...", service_name)
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
            service.accept_state_visitor(LoadStateVisitor())
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
            service.accept_state_visitor(SaveStateVisitor())
            service.lifecycle_hook.on_after_state_save()
        except:
            LOG.exception("Error while persisting state of service %s", service_name)

    @staticmethod
    def _setup_lambda_compatibility():
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


STATE_TRACKER = StateTracker()
