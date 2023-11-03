from queue import PriorityQueue, Full
from tempfile import SpooledTemporaryFile
from threading import Condition
from typing import cast
import datetime
import jsonpickle
import jsonpickle.tags
from jsonpickle.handlers import DatetimeHandler as DefaultDatetimeHandler
from moto.acm.models import CertBundle
from localstack.services.s3.v3.storage.ephemeral import (
    LockedSpooledTemporaryFile,
    S3_MAX_FILE_SIZE_BYTES,
)
from localstack.services.s3.v3.provider import DEFAULT_S3_TMP_DIR
from localstack.utils.files import mkdir
import base64
import os


class ConditionHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data: dict):
        data["lock"] = self.context.flatten(obj._lock, reset=False)
        return data

    def restore(self, data: dict):
        lock = self.context.restore(data["lock"], reset=False)
        return Condition(lock)


class PriorityQueueHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj: PriorityQueue, data: dict):
        data["maxsize"] = obj.maxsize
        data["queue"] = self.context.flatten(obj.queue, reset=False)
        return data

    def restore(self, data: dict):
        pq = PriorityQueue(data["maxsize"])
        for item in self.context.restore(data["queue"], reset=False):
            try:
                pq.put_nowait(item)
            except Full:
                break
        return pq


class CertBundleHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj: CertBundle, data: dict):
        data.update(
            {
                k: self.context.flatten(v, reset=False)
                for k, v in obj.__dict__.items()
                if k != "_cert" and k != "_key"
            }
        )
        return data

    def restore(self, data: dict):
        obj = cast(CertBundle, CertBundle.__new__(CertBundle))
        obj.__dict__.update(
            {
                k: self.context.restore(v, reset=False)
                for k, v in data.items()
                if k not in jsonpickle.tags.RESERVED
            }
        )
        obj._cert = obj.validate_certificate()
        obj._key = obj.validate_pk()
        return obj


class DatetimeHandler(jsonpickle.handlers.BaseHandler):
    def flatten(
        self, obj: datetime.datetime | datetime.time | datetime.date, data: dict
    ):
        data["isoformat"] = obj.isoformat()
        return data

    def restore(self, data: dict):
        if "isoformat" not in data:
            # handle backward-compatibility
            return DefaultDatetimeHandler(self.context).restore(data)

        cls_name: str = data[jsonpickle.tags.OBJECT]
        if cls_name.endswith("datetime"):
            cls = datetime.datetime
        elif cls_name.endswith("date"):
            cls = datetime.date
        elif cls_name.endswith("time"):
            cls = datetime.time
        else:
            raise TypeError("DatetimeHandler: unexpected object type " + cls_name)

        return cls.fromisoformat(data["isoformat"])


def get_dir(temp_file: SpooledTemporaryFile):
    if (args := getattr(temp_file, "_TemporaryFileArgs", None)) and "dir" in args:
        return args["dir"]

    if filename := getattr(getattr(temp_file._file, "file", None), "name", None):
        return os.path.dirname(filename)

    return None


class LockedSpooledTemporaryFileHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj: LockedSpooledTemporaryFile, data: dict):
        data["pos"] = pos = obj.tell()
        obj.seek(0)
        contents: bytes = obj.read()
        obj.seek(pos)
        try:
            data["text"] = contents.decode("ascii")
        except:
            data["b64"] = base64.b64encode(contents).decode()

        if dir := get_dir(obj):
            data["dir"] = dir

        return data

    def restore(self, data: dict):
        dir = data.get("dir") or DEFAULT_S3_TMP_DIR
        mkdir(dir)
        obj = LockedSpooledTemporaryFile(dir=dir, max_size=S3_MAX_FILE_SIZE_BYTES)
        if "text" in data:
            obj.write(data["text"].encode())
        else:
            obj.write(base64.b64decode(data["b64"]))
        obj.seek(data["pos"])
        return obj


def register_handlers():
    CertBundleHandler.handles(CertBundle)
    ConditionHandler.handles(Condition)
    PriorityQueueHandler.handles(PriorityQueue)
    DatetimeHandler.handles(datetime.datetime)
    DatetimeHandler.handles(datetime.date)
    DatetimeHandler.handles(datetime.time)
    LockedSpooledTemporaryFileHandler.handles(LockedSpooledTemporaryFile)
