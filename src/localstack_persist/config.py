import os

import logging
from localstack import config
from localstack.utils.bootstrap import resolve_apis

LOG = logging.getLogger(__name__)

BASE_DIR = "/persisted-data"


def normalise_service_name(n: str):
    service_name = (
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
    if service_name == "elasticsearch":
        return "es"
    return service_name


PERSISTED_SERVICES = {"default": True}

for k, v in os.environ.items():
    if not k.lower().startswith("persist_") or not v.strip():
        continue

    service_name = normalise_service_name(k[len("persist_") :])

    if v in config.TRUE_STRINGS:
        PERSISTED_SERVICES[service_name] = True
        for dependency in resolve_apis([service_name]):
            PERSISTED_SERVICES.setdefault(dependency, True)
    elif v in config.FALSE_STRINGS:
        PERSISTED_SERVICES[service_name] = False
    else:
        LOG.warning(
            "Environment variable %s has invalid value '%s' - it will be ignored", k, v
        )


def is_persistence_enabled(service_name: str):
    service_name = normalise_service_name(service_name)
    return PERSISTED_SERVICES.get(service_name, PERSISTED_SERVICES["default"])
