import jsonpickle
import logging, os

from localstack.services.stores import AccountRegionBundle
from localstack.state import AssetDirectory, StateContainer, StateVisitor
from moto.core import BackendDict

from .config import BASE_DIR

LOG = logging.getLogger(__name__)


def get_file_path(state_container: StateContainer):
    ty: type = type(state_container)

    if ty == BackendDict or ty == AccountRegionBundle:
        return os.path.join(
            BASE_DIR, state_container.service_name, ty.__name__ + ".json"
        )

    if ty == AssetDirectory:
        return

    LOG.warning("Unexpected state_container type: %s", ty)


class LoadStateVisitor(StateVisitor):
    def visit(self, state_container: StateContainer):
        file_path = get_file_path(state_container)
        if file_path and os.path.exists(file_path):
            self._load_json(state_container, file_path)

    def _load_json(self, state_container: StateContainer, file_path: str):
        with open(file_path) as file:
            json = file.read()

        deserialised = jsonpickle.decode(json, keys=True, safe=True)

        state_container.update(deserialised)
        state_container.__dict__.update(deserialised.__dict__)


class SaveStateVisitor(StateVisitor):
    def visit(self, state_container: StateContainer):
        file_path = get_file_path(state_container)
        if file_path:
            self._save_json(state_container, file_path)

    def _save_json(self, state_container: dict, file_path: str):
        json = jsonpickle.encode(state_container, keys=True, warn=True)
        if json:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as file:
                file.write(json)
