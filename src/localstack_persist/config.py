from enum import Enum
import os
import logging
from localstack.utils.bootstrap import resolve_apis

LOG = logging.getLogger(__name__)

DEFAULT_BASE_DIR = "/persisted-data"
BASE_DIR = os.environ.get("LOCALSTACK_PERSIST_BASE_DIR", DEFAULT_BASE_DIR)


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


class SerializationFormat(Enum):
    JSON = 1
    BINARY = 2

    def file_ext(self):
        match self:
            case self.JSON:
                return ".json"
            case self.BINARY:
                return ".pkl"

    @classmethod
    def default(cls) -> list["SerializationFormat"]:
        return [cls.JSON]


PERSISTED_SERVICES = {"default": True}
PERSIST_FORMATS = SerializationFormat.default()
PERSIST_FREQUENCY = 10


def init():
    global PERSISTED_SERVICES
    global PERSIST_FORMATS
    global PERSIST_FREQUENCY

    for key, value in os.environ.items():
        if not key.lower().startswith("persist_") or not value.strip():
            continue

        if key.lower() == "persist_format":
            new_formats: list[SerializationFormat] = []
            for x in value.split(","):
                x = x.strip()
                try:
                    format = SerializationFormat[x.upper()]
                    if format not in new_formats:
                        new_formats.append(format)
                except:
                    LOG.warning(
                        "Environment variable %s has invalid value '%s' - it will be ignored",
                        key,
                        value,
                    )
            if new_formats:
                PERSIST_FORMATS = new_formats
            continue

        if key.lower() == "persist_frequency":
            try:
                PERSIST_FREQUENCY = float(value.strip())
            except:
                LOG.warning(
                    "Environment variable %s has invalid value '%s' - it will be ignored",
                    key,
                    value,
                )
            continue

        # assume that `key` is the name of service
        service_name = normalise_service_name(key[len("persist_") :])

        if value == "1" or value.lower() == "true":
            PERSISTED_SERVICES[service_name] = True
            for dependency in resolve_apis([service_name]):
                PERSISTED_SERVICES.setdefault(dependency, True)
        elif value == "0" or value.lower() == "false":
            PERSISTED_SERVICES[service_name] = False
        else:
            LOG.warning(
                "Environment variable %s has invalid value '%s' - it will be ignored",
                key,
                value,
            )


def is_persistence_enabled(service_name: str):
    service_name = normalise_service_name(service_name)
    return PERSISTED_SERVICES.get(service_name, PERSISTED_SERVICES["default"])


init()