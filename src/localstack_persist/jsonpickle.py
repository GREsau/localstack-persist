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


def register_handlers():
    CertBundleHandler.handles(CertBundle)
    ConditionHandler.handles(Condition)
    PriorityQueueHandler.handles(PriorityQueue)
