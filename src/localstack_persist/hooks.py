import logging

from localstack.runtime import hooks

from .state import STATE_TRACKER
from .jsonpickle import register_handlers

LOG = logging.getLogger(__name__)


@hooks.on_infra_start(priority=1)
def on_infra_start():
    register_handlers()
    STATE_TRACKER.load_all_services_state()
    STATE_TRACKER.start()


@hooks.on_infra_shutdown()
def on_infra_shutdown():
    STATE_TRACKER.stop()
