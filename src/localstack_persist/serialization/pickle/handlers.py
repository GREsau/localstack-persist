from queue import Queue, PriorityQueue, LifoQueue
from threading import RLock, Lock
from typing import cast
from moto.acm.models import CertBundle
import pickle
import dill
import copyreg

# This module, and all of the unpickle_* functions in it, must not be moved/renamed,
# because pickle-serialized data must be able to load them.


def unpickle_lock():
    return Lock()


def reduce_lock(_: Lock):
    return unpickle_lock, ()


def unpickle_rlock():
    return RLock()


def reduce_rlock(_: RLock):
    return unpickle_rlock, ()


def reduce_queue(queue: Queue | PriorityQueue | LifoQueue):
    return type(queue), (queue.maxsize,), {"queue": queue.queue}


def reduce_cert_bundle(bundle: CertBundle):
    items = {k: v for k, v in bundle.__dict__.items() if k != "_cert" and k != "_key"}
    return unpickle_cert_bundle, (items,)


def unpickle_cert_bundle(state: dict) -> CertBundle:
    obj = cast(CertBundle, CertBundle.__new__(CertBundle))
    obj.__dict__.update(state)
    obj._cert = obj.validate_certificate()
    obj._key = obj.validate_pk()
    return obj


custom_dispatch_table = {
    type(Lock()): reduce_lock,
    type(RLock()): reduce_rlock,
    Queue: reduce_queue,
    PriorityQueue: reduce_queue,
    LifoQueue: reduce_queue,
    CertBundle: reduce_cert_bundle,
}

custom_dispatch = type(dill.Pickler.dispatch)(
    {k: v for k, v in dill.Pickler.dispatch.items() if k not in custom_dispatch_table}
)


class CustomDillPickler(dill.Pickler):
    dispatch_table = copyreg.dispatch_table | custom_dispatch_table
    dispatch = custom_dispatch


class CustomPickler(pickle.Pickler):
    dispatch_table = copyreg.dispatch_table | custom_dispatch_table
