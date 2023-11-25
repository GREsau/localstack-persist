import json
import logging
import dill
import pickle
from typing import Any

from .handlers import CustomPickler, CustomDillPickler

PICKLE_MARKER = b"p"
DILL_PICKLE_MARKER = b"d"


LOG = logging.getLogger(__name__)


class PickleSerializer:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def serialize(self, data: Any):
        with open(self.file_path, "wb") as file:
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
                file.seek(0)
                file.write(DILL_PICKLE_MARKER)
                pickler = CustomDillPickler(file)
                pickler.dump(data)
                file.truncate()


class PickleDeserializer:
    def __init__(self, file_path: str) -> None:
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
