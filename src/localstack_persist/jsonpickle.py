from queue import PriorityQueue, Full
from threading import Condition
from typing import cast
import jsonpickle
import jsonpickle.tags
from moto.acm.models import CertBundle


class ConditionHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data: dict):
        data["lock"] = self.context.flatten(obj._lock, reset=False)
        return data

    def restore(self, data: dict):
        lock = self.context.restore(data["lock"], reset=False)
        return Condition(lock)


ConditionHandler.handles(Condition)


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


PriorityQueueHandler.handles(PriorityQueue)


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


CertBundleHandler.handles(CertBundle)


# workaround for https://github.com/jsonpickle/jsonpickle/issues/453
class DictHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        for k, v in obj.items():
            data[k] = self.context.flatten(v, reset=False)
        data["__dict__"] = self.context.flatten(obj.__dict__, reset=False)
        return data

    def restore(self, data):
        raise NotImplementedError("DictHandler can not be used for unpickling")


def fix_dict_pickling():
    jsonpickle.handlers.register(dict, DictHandler, base=True)
