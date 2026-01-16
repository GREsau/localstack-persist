from queue import PriorityQueue, Full
from threading import Condition
from typing import Any, Callable, cast
import datetime
import jsonpickle
import jsonpickle.tags
import jsonpickle.util
from jsonpickle.handlers import DatetimeHandler as DefaultDatetimeHandler
from moto.acm.models import CertBundle
from localstack.utils.patch import patch
from localstack.services.cloudformation.engine.v2.change_set_model import NothingType

from localstack_persist.utils import once
from ..utils import compat_module_path


@once
def register_handlers():
    CertBundleHandler.handles(CertBundle)
    ConditionHandler.handles(Condition)
    PriorityQueueHandler.handles(PriorityQueue)
    DatetimeHandler.handles(datetime.datetime)
    DatetimeHandler.handles(datetime.date)
    DatetimeHandler.handles(datetime.time)
    NothingTypeHandler.handles(NothingType)

    # jsonpickle doesn't expose a hook like Unpickler.find_class(),
    # so we patch untranslate_module_name for the same effect.
    @patch(jsonpickle.util.untranslate_module_name)
    def patched_untranslate_module_name(orig: Callable[[str], str], module: str) -> str:
        return orig(compat_module_path(module))


class ConditionHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data: dict):
        data["lock"] = self.context.flatten(obj._lock, reset=False)
        return data

    def restore(self, obj: dict):
        lock = self.context.restore(obj["lock"], reset=False)
        return Condition(lock)


class PriorityQueueHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj: PriorityQueue, data: dict):
        data["maxsize"] = obj.maxsize
        data["queue"] = self.context.flatten(obj.queue, reset=False)
        return data

    def restore(self, obj: dict):
        pq = PriorityQueue[Any](obj["maxsize"])
        for item in self.context.restore(obj["queue"], reset=False):
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

    def restore(self, obj: dict):
        bundle = cast(CertBundle, CertBundle.__new__(CertBundle))
        bundle.__dict__.update(
            {
                k: self.context.restore(v, reset=False)
                for k, v in obj.items()
                if k not in jsonpickle.tags.RESERVED
            }
        )
        bundle._cert = bundle.validate_certificate()
        bundle._key = bundle.validate_pk()
        return bundle


class DatetimeHandler(jsonpickle.handlers.BaseHandler):
    def flatten(
        self, obj: datetime.datetime | datetime.time | datetime.date, data: dict
    ):
        data["isoformat"] = obj.isoformat()
        return data

    def restore(self, obj: dict):
        if "isoformat" not in obj:
            # handle backward-compatibility
            return DefaultDatetimeHandler(self.context).restore(obj)

        cls_name: str = obj[jsonpickle.tags.OBJECT]
        cls: type[datetime.datetime | datetime.date | datetime.time]
        if cls_name.endswith("datetime"):
            cls = datetime.datetime
        elif cls_name.endswith("date"):
            cls = datetime.date
        elif cls_name.endswith("time"):
            cls = datetime.time
        else:
            raise TypeError("DatetimeHandler: unexpected object type " + cls_name)

        return cls.fromisoformat(obj["isoformat"])

class NothingTypeHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        # Store a marker, no state needed
        return {'__nothingtype__': True}

    def restore(self, data):
        # Always return the singleton instance
        return NothingType
