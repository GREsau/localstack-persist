import logging

from localstack.runtime import hooks
from localstack.utils.tagging import TaggingService
from moto.core.common_models import CloudFormationModel

from .state import STATE_TRACKER

LOG = logging.getLogger(__name__)


@hooks.on_infra_start(priority=1)
def on_infra_start():
    # HACK for "global" models that were persisted without a `partition` field
    setattr(CloudFormationModel, "partition", "aws")
    # HACK for TaggingServices that were persisted without the `key_field`/`value_field` properties
    setattr(TaggingService, "key_field", "Key")
    setattr(TaggingService, "value_field", "Value")

    STATE_TRACKER.load_all_services_state()
    STATE_TRACKER.start()


@hooks.on_infra_shutdown()
def on_infra_shutdown():
    STATE_TRACKER.stop()
