import os
import shutil

import jsonpickle
import logging

import localstack.config
from localstack.services.stores import AccountRegionBundle
from localstack.state import AssetDirectory, StateContainer, StateVisitor
from moto.core import BackendDict

from .config import BASE_DIR

LOG = logging.getLogger(__name__)


def get_file_path(state_container: StateContainer):
    ty: type = type(state_container)

    if issubclass(ty, (BackendDict, AccountRegionBundle)):
        return os.path.join(
            BASE_DIR, state_container.service_name, ty.__name__ + ".json"
        )

    if ty == AssetDirectory:
        return

    LOG.warning("Unexpected state_container type: %s", ty)


def get_json_file_path(state_container: BackendDict | AccountRegionBundle):
    type_name = type(state_container).__name__

    return os.path.join(BASE_DIR, state_container.service_name, type_name + ".json")


def get_asset_dir_path(state_container: AssetDirectory):
    assert state_container.path.startswith(localstack.config.dirs.data)
    relpath = os.path.relpath(state_container.path, localstack.config.dirs.data)

    return os.path.join(BASE_DIR, relpath)


class LoadStateVisitor(StateVisitor):
    def visit(self, state_container: StateContainer):
        if isinstance(state_container, (BackendDict, AccountRegionBundle)):
            file_path = get_json_file_path(state_container)
            if os.path.isfile(file_path):
                self._load_json(state_container, file_path)
        elif isinstance(state_container, AssetDirectory):
            dir_path = get_asset_dir_path(state_container)
            if os.path.isdir(dir_path):
                shutil.copytree(dir_path, state_container.path, dirs_exist_ok=True)
        else:
            LOG.warning("Unexpected state_container type: %s", type(state_container))

    def _load_json(self, state_container: StateContainer, file_path: str):
        with open(file_path) as file:
            json = file.read()

        deserialised = jsonpickle.decode(json, keys=True, safe=True)

        state_container.update(deserialised)
        state_container.__dict__.update(deserialised.__dict__)


class SaveStateVisitor(StateVisitor):
    def visit(self, state_container: StateContainer):
        if isinstance(state_container, (BackendDict, AccountRegionBundle)):
            file_path = get_json_file_path(state_container)
            self._save_json(state_container, file_path)
        elif isinstance(state_container, AssetDirectory):
            dir_path = get_asset_dir_path(state_container)
            # TODO should this delete files from dir_path that aren't in state_container.path?
            if os.path.isdir(state_container.path):
                shutil.copytree(state_container.path, dir_path, dirs_exist_ok=True)
        else:
            LOG.warning("Unexpected state_container type: %s", type(state_container))

    def _save_json(self, state_container: dict, file_path: str):
        json = jsonpickle.encode(state_container, keys=True, warn=True)
        if json:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as file:
                file.write(json)
