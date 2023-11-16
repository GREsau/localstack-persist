import json
import os
import shutil
from typing import Dict, Optional, Any

import jsonpickle
import logging

import localstack.config
from localstack.services.stores import AccountRegionBundle
from localstack.state import AssetDirectory, StateContainer, StateVisitor
from localstack.services.s3.v3.storage.ephemeral import EphemeralS3ObjectStore
from localstack.services.s3.v3.provider import DEFAULT_S3_TMP_DIR
from localstack.services.s3.v3.models import S3Store as V3S3Store
from localstack.services.s3.models import S3Store as LegacyS3Store
from localstack.services.opensearch.models import OpenSearchStore
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.events import FileSystemEventHandler

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

    if relpath.startswith(state_container.service_name):
        return os.path.join(BASE_DIR, relpath, "assets")
    else:
        return os.path.join(BASE_DIR, state_container.service_name, relpath, "assets")


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
        and str(t1).replace(".awslambda.", ".lambda_.")
        == str(t2).replace(".awslambda.", ".lambda_.")
    )


class LoadStateVisitor(StateVisitor):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name
        self._s3_objects: Optional[EphemeralS3ObjectStore] = None

    def visit(self, state_container: StateContainer | EphemeralS3ObjectStore):
        if isinstance(state_container, JsonSerializableState):
            self._load_json(state_container)
        elif isinstance(state_container, AssetDirectory):
            dir_path = get_asset_dir_path(state_container)
            if not dir_path:
                return
            if os.path.isdir(dir_path):
                shutil.copytree(dir_path, state_container.path, dirs_exist_ok=True)
            os.makedirs(state_container.path, exist_ok=True)
            start_watcher(self.service_name, state_container.path)

        else:
            LOG.warning("Unexpected state_container type: %s", type(state_container))

    def _load_json(self, state_container: JsonSerializableState):
        file_path = get_json_file_path(state_container)
        if not os.path.isfile(file_path):
            # Are we trying to load an S3ObjectStore for the V3 provider which we just migrated to?
            if self._s3_objects and type(state_container) == EphemeralS3ObjectStore:
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

        # Set Processing because after loading state, it will take some time for opensearch/elasticsearch to start.
        if deserialised_type == AccountRegionBundle[OpenSearchStore]:
            for region_bundle in deserialised.values():  # type: ignore
                store: OpenSearchStore
                for store in region_bundle.values():
                    for domain in store.opensearch_domains.values():
                        domain["Processing"] = True

        if isinstance(state_container, dict) and isinstance(deserialised, dict):
            state_container.update(deserialised)
        state_container.__dict__.update(deserialised.__dict__)


class SaveStateVisitor(StateVisitor):
    json_encoder = json.JSONEncoder(check_circular=False, separators=(",", ":"))

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def visit(self, state_container: StateContainer | EphemeralS3ObjectStore):
        if isinstance(state_container, JsonSerializableState):
            self._save_json(state_container)
        elif isinstance(state_container, AssetDirectory):
            dir_path = get_asset_dir_path(state_container)
            if not dir_path:
                return
            if os.path.isdir(state_container.path):
                self._sync_directories(state_container.path, dir_path)
            else:
                os.makedirs(state_container.path, exist_ok=True)
            start_watcher(self.service_name, state_container.path)
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


class AffectedServiceHandler(FileSystemEventHandler):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def on_created(self, event):
        self._handle_event()

    def on_deleted(self, event):
        self._handle_event()

    def on_modified(self, event):
        self._handle_event()

    def on_moved(self, event):
        self._handle_event()

    def _handle_event(self):
        # circular dependency :(
        from .state import STATE_TRACKER

        STATE_TRACKER.add_affected_service(self.service_name)


path_watchers: Dict[str, AffectedServiceHandler] = {}
observer: Optional[BaseObserver] = None


def start_watcher(service_name: str, path: str):
    if path in path_watchers:
        return

    global observer
    old_observer = observer
    observer = Observer()

    path_watchers[path] = AffectedServiceHandler(service_name)

    for watcher_path, watcher in path_watchers.items():
        observer.schedule(watcher, watcher_path, True)

    observer.start()
    if old_observer:
        old_observer.stop()
