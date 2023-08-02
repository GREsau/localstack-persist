import os

import logging
from localstack import config

LOG = logging.getLogger(__name__)

BASE_DIR = os.path.join(config.dirs.data, "compere")


def normalise_service_name(n: str):
    return (
        n.strip()
        .lower()
        .replace(
            "_",
            "",
        )
        .replace(
            "-",
            "",
        )
    )


PERSISTED_SERVICES = {"default": True}

for k, v in os.environ.items():
    if not k.lower().startswith("persist_") or not v.strip():
        continue

    service_name = normalise_service_name(k[len("persist_") :])

    if v in config.TRUE_STRINGS:
        PERSISTED_SERVICES[service_name] = True
    elif v in config.FALSE_STRINGS:
        PERSISTED_SERVICES[service_name] = False
    else:
        LOG.warn(
            "Environment variable %s has invalid value '%s' - it will be ignored", k, v
        )


def should_persist(service_name: str):
    return PERSISTED_SERVICES.get(
        normalise_service_name(service_name), PERSISTED_SERVICES["default"]
    )
