import os
from .jsonpickle.serializer import JsonPickleSerializer, JsonPickleDeserializer
from .pickle.serializer import PickleSerializer, PickleDeserializer
from ..config import PERSIST_FORMAT, SerializationFormat

make_serializer = {
    SerializationFormat.JSON: lambda path: JsonPickleSerializer(path + ".json"),
    SerializationFormat.BINARY: lambda path: PickleSerializer(path + ".pkl"),
}


def get_serializers(file_path_base: str):
    formats = PERSIST_FORMAT or [SerializationFormat.JSON]
    return [make_serializer[f](file_path_base) for f in formats]


def get_deserializer(file_path_base: str):
    json_file_path = file_path_base + ".json"
    try:
        json_mtime = os.path.getmtime(json_file_path)
    except:
        json_mtime = 0

    pkl_file_path = file_path_base + ".pkl"
    try:
        pkl_mtime = os.path.getmtime(pkl_file_path)
    except:
        pkl_mtime = 0

    if not json_mtime and not pkl_mtime:
        return None

    if json_mtime > pkl_mtime:
        return JsonPickleDeserializer(json_file_path)

    return PickleDeserializer(pkl_file_path)
