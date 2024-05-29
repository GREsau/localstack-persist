import logging

from localstack.runtime import hooks
from moto.core.common_models import CloudFormationModel

from .state import STATE_TRACKER

LOG = logging.getLogger(__name__)


@hooks.on_infra_start(priority=1)
def on_infra_start():
    # HACK for "global" models that were persisted without a `partition` field
    setattr(CloudFormationModel, "partition", "aws")

    STATE_TRACKER.load_all_services_state()
    STATE_TRACKER.start()


@hooks.on_infra_shutdown()
def on_infra_shutdown():
    STATE_TRACKER.stop()
