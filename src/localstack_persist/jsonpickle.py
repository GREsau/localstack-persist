from threading import Condition
import jsonpickle


class ConditionHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        data["lock"] = self.context.flatten(obj._lock, reset=False)
        return data

    def restore(self, data):
        lock = self.context.restore(data["lock"], reset=False)
        return Condition(lock)


ConditionHandler.handles(Condition)


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
