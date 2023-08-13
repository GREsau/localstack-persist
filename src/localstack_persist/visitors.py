import json
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

# Track version for future handling of backward (or forward) incompatible changes.
# This is the "serialisation format" version, which is different to the localstack-persist version.
SER_VERSION_KEY = "v"
SER_VERSION = 1

DATA_KEY = "data"


def get_json_file_path(state_container: BackendDict | AccountRegionBundle):
    file_name = "backend" if isinstance(state_container, BackendDict) else "store"

    return os.path.join(BASE_DIR, state_container.service_name, file_name + ".json")


def get_asset_dir_path(state_container: AssetDirectory):
    assert state_container.path.startswith(localstack.config.dirs.data)
    relpath = os.path.relpath(state_container.path, localstack.config.dirs.data)

    return os.path.join(BASE_DIR, relpath, "assets")


def rmrf(entry: os.DirEntry):
    if entry.is_dir(follow_symlinks=False):
        shutil.rmtree(entry)
    else:
        os.remove(entry)


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
            envelope: dict = json.load(file)

        version = envelope.get(SER_VERSION_KEY, None)
        if version != SER_VERSION:
            LOG.warning(
                "Persisted state at %s has unsupported version %s - trying to load it anyway...",
                file_path,
                version,
            )

        unpickler = jsonpickle.Unpickler(keys=True, safe=True, on_missing="error")
        deserialised = unpickler.restore(envelope[DATA_KEY])

        state_container.update(deserialised)
        state_container.__dict__.update(deserialised.__dict__)


class SaveStateVisitor(StateVisitor):
    json_encoder = json.JSONEncoder(check_circular=False, separators=(",", ":"))

    def visit(self, state_container: StateContainer):
        if isinstance(state_container, (BackendDict, AccountRegionBundle)):
            file_path = get_json_file_path(state_container)
            self._save_json(state_container, file_path)
        elif isinstance(state_container, AssetDirectory):
            dir_path = get_asset_dir_path(state_container)
            if os.path.isdir(state_container.path):
                self._sync_directories(state_container.path, dir_path)
        else:
            LOG.warning("Unexpected state_container type: %s", type(state_container))

    def _save_json(self, state_container: dict, file_path: str):
        pickler = jsonpickle.Pickler(keys=True, warn=True)
        flattened = pickler.flatten(state_container)

        envelope = {SER_VERSION_KEY: SER_VERSION, DATA_KEY: flattened}

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as file:
            for chunk in self.json_encoder.iterencode(envelope):
                file.write(chunk)

    @staticmethod
    def _sync_directories(src: str, dst: str):
        shutil.copytree(src, dst, dirs_exist_ok=True)

        desired_files = set(os.listdir(src))

        with os.scandir(dst) as it:
            for entry in it:
                if entry.name not in desired_files:
                    rmrf(entry)
