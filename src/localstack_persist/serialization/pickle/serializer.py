import json
import logging
import dill
import pickle
from typing import Any, Tuple

from .handlers import CustomPickler, CustomDillPickler

PICKLE_MARKER = b"p"
DILL_PICKLE_MARKER = b"d"

LOG = logging.getLogger(__name__)

DILL_TYPES = set[Tuple[str, type]]()


class PickleSerializer:
    def __init__(self, service_name: str, file_path: str):
        self.service_name = service_name
        self.file_path = file_path

    def serialize(self, data: Any):
        with open(self.file_path, "wb") as file:
            if (self.service_name, type(data)) in DILL_TYPES:
                file.write(DILL_PICKLE_MARKER)
                pickler = CustomDillPickler(file)
                pickler.dump(data)
            else:
                file.write(PICKLE_MARKER)
                pickler = CustomPickler(file)
                try:
                    pickler.dump(data)
                except:
                    LOG.warning(
                        "Error while pickling state %s, falling back to slower 'dill' pickler",
                        type(data),
                        exc_info=True,
                    )
                    DILL_TYPES.add((self.service_name, type(data)))
                    file.seek(0)
                    file.write(DILL_PICKLE_MARKER)
                    pickler = CustomDillPickler(file)
                    pickler.dump(data)
                    file.truncate()


class PickleDeserializer:
    def __init__(self, service_name: str, file_path: str) -> None:
        self.file_path = file_path

    def deserialize(self) -> Any:
        with open(self.file_path, "rb") as file:
            marker = file.read(1)
            if marker == PICKLE_MARKER:
                return pickle.load(file)
            elif marker == DILL_PICKLE_MARKER:
                return dill.load(file)
            else:
                LOG.warning(
                    "Persisted state at %s has unexpected marker %s - trying to load it anyway...",
                    self.file_path,
                    marker,
                )
            return dill.load(file)
