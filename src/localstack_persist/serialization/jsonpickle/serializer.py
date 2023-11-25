import json
import logging
from typing import Any
import jsonpickle.handlers
import jsonpickle.tags

from .handlers import register_handlers

# Track version for future handling of backward (or forward) incompatible changes.
# This is the "serialisation format" version, which is different to the localstack-persist version.
SER_VERSION_KEY = "v"
SER_VERSION = 1

DATA_KEY = "data"

LOG = logging.getLogger(__name__)


class JsonPickleSerializer:
    _json_encoder = json.JSONEncoder(check_circular=False, separators=(",", ":"))

    def serialize(self, file_path: str, data: Any):
        register_handlers()

        pickler = jsonpickle.Pickler(keys=True, warn=True)

        envelope = {SER_VERSION_KEY: SER_VERSION, DATA_KEY: pickler.flatten(data)}

        with open(file_path, "w") as file:
            for chunk in self._json_encoder.iterencode(envelope):
                file.write(chunk)

    def deserialize(self, file_path: str) -> Any:
        register_handlers()

        with open(file_path) as file:
            envelope: dict = json.load(file)

        version = envelope.get(SER_VERSION_KEY, None)
        if version != SER_VERSION:
            LOG.warning(
                "Persisted state at %s has unsupported version %s - trying to load it anyway...",
                file_path,
                version,
            )

        unpickler = jsonpickle.Unpickler(keys=True, safe=True, on_missing="error")
        return unpickler.restore(envelope[DATA_KEY])
