import logging

from localstack.runtime import hooks

from .jsonpickle import fix_dict_pickling
from .state import STATE_TRACKER

LOG = logging.getLogger(__name__)


@hooks.on_infra_start()
def on_infra_start():
    STATE_TRACKER.load_all_services_state()
    fix_dict_pickling()
    STATE_TRACKER.start()


@hooks.on_infra_shutdown()
def on_infra_shutdown():
    STATE_TRACKER.stop()
