import os
from typing import Any, Protocol
from .jsonpickle.serializer import JsonPickleSerializer, JsonPickleDeserializer
from .pickle.serializer import PickleSerializer, PickleDeserializer
from ..config import SerializationFormat, PERSIST_FORMATS


class Serializer(Protocol):
    def __init__(self, file_path: str):
        ...

    def serialize(self, data: Any):
        ...


class Deserializer(Protocol):
    def __init__(self, file_path: str):
        ...

    def deserialize(self) -> Any:
        ...


serializer_types: dict[SerializationFormat, type[Serializer]] = {
    SerializationFormat.JSON: JsonPickleSerializer,
    SerializationFormat.BINARY: PickleSerializer,
}

deserializer_types: dict[SerializationFormat, type[Deserializer]] = {
    SerializationFormat.JSON: JsonPickleDeserializer,
    SerializationFormat.BINARY: PickleDeserializer,
}


def get_serializers(file_path_base: str):
    return [
        serializer_types[format](file_path_base + format.file_ext())
        for format in PERSIST_FORMATS
    ]


def get_deserializer(file_path_base: str):
    def get_score(format: SerializationFormat) -> list[float]:
        try:
            # Prefer most-recently updated file
            mtime = os.path.getmtime(file_path_base + format.file_ext())
        except:
            return []

        try:
            # For files with identical mtime, prefer deserializer for enabled format.
            # With multiple enabled formats, prefer last one (which typically gets written last).
            return [mtime, PERSIST_FORMATS.index(format)]
        except ValueError:
            return [mtime]

    best_score = []
    best_format = None

    for format in SerializationFormat:
        score = get_score(format)
        if score > best_score:
            best_score = score
            best_format = format

    if not best_format:
        return None

    return deserializer_types[best_format](file_path_base + best_format.file_ext())
