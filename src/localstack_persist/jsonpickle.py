import copy
from queue import PriorityQueue, Full
from threading import Condition
import jsonpickle
from moto.acm.models import AWSCertificateManagerBackend, CertBundle


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


# this is really more of a CertBundle handler!
class AWSCertificateManagerBackendHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj: AWSCertificateManagerBackend, data: dict):
        def flatten_cert_bundle(cb: CertBundle):
            cb = copy.copy(cb)
            del cb._cert
            del cb._key
            return self.context.flatten(cb, reset=False)

        data["region_name"] = obj.region_name
        data["account_id"] = obj.account_id
        data["_certificates"] = {
            k: flatten_cert_bundle(v) for k, v in obj._certificates.items()
        }
        data["_idempotency_tokens"] = obj._idempotency_tokens

        return data

    def restore(self, data: dict):
        def restore_cert_bundle(cbd: dict):
            cb: CertBundle = self.context.restore(cbd, reset=False)
            cb._cert = cb.validate_certificate()
            cb._key = cb.validate_pk()
            return cb

        obj = AWSCertificateManagerBackend(data["region_name"], data["account_id"])
        obj._certificates = {
            k: restore_cert_bundle(v) for k, v in data["_certificates"].items()
        }
        obj._idempotency_tokens = data["_idempotency_tokens"]
        return obj


AWSCertificateManagerBackendHandler.handles(AWSCertificateManagerBackend)


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
