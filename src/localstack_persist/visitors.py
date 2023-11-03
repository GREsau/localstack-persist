import json
import os
import shutil
from typing import Optional, Any

import jsonpickle
import logging

import localstack.config
from localstack.services.stores import AccountRegionBundle
from localstack.state import AssetDirectory, StateContainer, StateVisitor
from localstack.services.s3.v3.storage.ephemeral import EphemeralS3ObjectStore
from localstack.services.s3.v3.provider import DEFAULT_S3_TMP_DIR
from localstack.services.s3.v3.models import S3Store as V3S3Store
from localstack.services.s3.models import S3Store as LegacyS3Store

from moto.core import BackendDict
from moto.s3.models import s3_backends

from .config import BASE_DIR
from . import s3_migration

JsonSerializableState = BackendDict | AccountRegionBundle | EphemeralS3ObjectStore

LOG = logging.getLogger(__name__)

# Track version for future handling of backward (or forward) incompatible changes.
# This is the "serialisation format" version, which is different to the localstack-persist version.
SER_VERSION_KEY = "v"
SER_VERSION = 1

DATA_KEY = "data"


def get_json_file_path(
    state_container: JsonSerializableState,
):
    if isinstance(state_container, EphemeralS3ObjectStore):
        return os.path.join(BASE_DIR, "s3", "objects.json")

    file_name = "backend" if isinstance(state_container, BackendDict) else "store"

    return os.path.join(BASE_DIR, state_container.service_name, file_name + ".json")


def get_asset_dir_path(state_container: AssetDirectory):
    if state_container.path == DEFAULT_S3_TMP_DIR:
        # Skip this directory - we'll later persist it to JSON via the EphemeralS3ObjectStore
        return None

    assert state_container.path.startswith(localstack.config.dirs.data)
    relpath = os.path.relpath(state_container.path, localstack.config.dirs.data)

    return os.path.join(BASE_DIR, relpath, "assets")


def rmrf(entry: os.DirEntry):
    if entry.is_dir(follow_symlinks=False):
        shutil.rmtree(entry)
    else:
        os.remove(entry)


def state_type(state: Any) -> type:
    return (
        AccountRegionBundle[state.store]
        if isinstance(state, AccountRegionBundle)
        else type(state)
    )


def are_same_type(t1: type, t2: type) -> bool:
    return t1 == t2 or (
        t1.__name__ == t2.__name__
        and str(t1).replace("awslambda", "lambda_")
        == str(t2).replace("awslambda", "lambda_")
    )


class LoadStateVisitor(StateVisitor):
    _s3_objects: Optional[EphemeralS3ObjectStore]

    def visit(self, state_container: StateContainer | EphemeralS3ObjectStore):
        if isinstance(state_container, JsonSerializableState):
            self._load_json(state_container)
        elif isinstance(state_container, AssetDirectory):
            dir_path = get_asset_dir_path(state_container)
            if dir_path and os.path.isdir(dir_path):
                shutil.copytree(dir_path, state_container.path, dirs_exist_ok=True)
        else:
            LOG.warning("Unexpected state_container type: %s", type(state_container))

    def _load_json(self, state_container: JsonSerializableState):
        file_path = get_json_file_path(state_container)
        if not os.path.isfile(file_path):
            # Are we trying to load an S3ObjectStore for the V3 provider which we just migrated to?
            if getattr(self, "_s3_objects", None) and type(state_container) == type(
                self._s3_objects
            ):
                state_container.__dict__.update(self._s3_objects.__dict__)
            return

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

        state_container_type = state_type(state_container)
        deserialised_type = state_type(deserialised)

        if (
            state_container_type == AccountRegionBundle[V3S3Store]
            and deserialised_type == AccountRegionBundle[LegacyS3Store]
        ):
            try:
                LOG.info("Migrating S3 state to V3 provider...")
                self._load_json(s3_backends)
                (deserialised, self._s3_objects) = s3_migration.migrate(s3_backends)
            except:
                LOG.exception("Error migrating S3 state to V3 provider")
                return
        elif not are_same_type(state_container_type, deserialised_type):
            LOG.warning(
                "Unexpected deserialised state_container type: %s, expected %s",
                deserialised_type,
                state_container_type,
            )
            return

        if isinstance(state_container, dict) and isinstance(deserialised, dict):
            state_container.update(deserialised)
        state_container.__dict__.update(deserialised.__dict__)


class SaveStateVisitor(StateVisitor):
    json_encoder = json.JSONEncoder(check_circular=False, separators=(",", ":"))

    def visit(self, state_container: StateContainer | EphemeralS3ObjectStore):
        if isinstance(state_container, JsonSerializableState):
            self._save_json(state_container)
        elif isinstance(state_container, AssetDirectory):
            dir_path = get_asset_dir_path(state_container)
            if dir_path and os.path.isdir(state_container.path):
                self._sync_directories(state_container.path, dir_path)
        else:
            LOG.warning("Unexpected state_container type: %s", type(state_container))

    def _save_json(self, state_container: JsonSerializableState):
        file_path = get_json_file_path(state_container)
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
