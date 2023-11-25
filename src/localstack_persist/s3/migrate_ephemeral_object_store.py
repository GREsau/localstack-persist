import base64
from typing import cast
import jsonpickle

from localstack.services.s3.v3.models import S3Object, S3Multipart, S3Part
from localstack.services.s3.v3.storage.ephemeral import (
    EphemeralS3ObjectStore,
    LockedSpooledTemporaryFile,
)
from localstack.utils.files import mkdir

from .storage import PersistedS3ObjectStore
from ..serialization.jsonpickle.serializer import JsonPickleSerializer


class LockedSpooledTemporaryFileHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        raise NotImplementedError(
            "LockedSpooledTemporaryFile should no longer be persisted"
        )

    def restore(self, data: dict):
        obj = LockedSpooledTemporaryFile()
        if "text" in data:
            obj.write(data["text"].encode())
        else:
            obj.write(base64.b64decode(data["b64"]))
        obj.seek(0)
        return obj


class StubS3Multipart:
    def __init__(self, id: str) -> None:
        self.id = str


def migrate_ephemeral_object_store(file_path: str, store: PersistedS3ObjectStore):
    jsonpickle.register(LockedSpooledTemporaryFile, LockedSpooledTemporaryFileHandler)
    serializer = JsonPickleSerializer()
    ephemeral_store: EphemeralS3ObjectStore = serializer.deserialize(file_path)

    if not ephemeral_store._filesystem:
        # create the root directory to avoid trying to re-migrate empty store again in future
        mkdir(store.root_directory)
        return

    for bucket, files in ephemeral_store._filesystem.items():
        store.create_bucket(bucket)
        for key, obj_data in files["keys"].items():
            [key, version] = key.rsplit("?", 1)
            with store.open(bucket, S3Object(key, version_id=version)) as new_object:
                new_object.write(obj_data)

        for id, multipart in files["multiparts"].items():
            new_multipart = store.get_multipart(
                bucket, cast(S3Multipart, StubS3Multipart(id))
            )
            for part_number, part_data in multipart.parts.items():
                with new_multipart.open(S3Part(part_number)) as new_part:
                    new_part.write(part_data)
