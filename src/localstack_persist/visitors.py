import json
import os
import shutil
from typing import Dict, Optional, Any, TypeAlias

import logging

import localstack.config
from localstack.services.stores import AccountRegionBundle
from localstack.state import AssetDirectory, StateContainer, StateVisitor
from localstack.services.s3.v3.models import S3Store as V3S3Store
from localstack.services.s3.models import S3Store as LegacyS3Store
from localstack.services.opensearch.models import OpenSearchStore
from localstack.services.lambda_.invocation.models import LambdaStore
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.events import FileSystemEventHandler

from moto.core.base_backend import BackendDict
from moto.s3.models import s3_backends

from .serialization import get_deserializer, get_serializers
from .config import BASE_DIR, SerializationFormat, PERSIST_FORMATS

SerializableState: TypeAlias = BackendDict | AccountRegionBundle

logging.getLogger("watchdog").setLevel(logging.INFO)
LOG = logging.getLogger(__name__)


def get_state_file_path_base(
    state_container: SerializableState,
):
    file_name = "backend" if isinstance(state_container, BackendDict) else "store"

    return os.path.join(BASE_DIR, state_container.service_name, file_name)


def get_asset_dir_path(state_container: AssetDirectory):
    assert state_container.path.startswith(localstack.config.dirs.data)
    relpath = os.path.relpath(state_container.path, localstack.config.dirs.data)

    if relpath.startswith(state_container.service_name):
        return os.path.join(BASE_DIR, relpath, "assets")
    else:
        return os.path.join(BASE_DIR, state_container.service_name, relpath, "assets")


def state_type(state: Any) -> type:
    return (
        AccountRegionBundle[state.store]  # type: ignore[return-value]
        if isinstance(state, AccountRegionBundle)
        else type(state)
    )


class LoadStateVisitor(StateVisitor):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def visit(self, state_container: StateContainer):
        if isinstance(state_container, BackendDict | AccountRegionBundle):
            self._load_state(state_container)
        elif isinstance(state_container, AssetDirectory):
            if state_container.path.startswith(BASE_DIR):
                # nothing to do - assets are read directly from the volume
                return
            dir_path = get_asset_dir_path(state_container)
            if os.path.isdir(dir_path):
                shutil.copytree(
                    dir_path,
                    state_container.path,
                    dirs_exist_ok=True,
                    copy_function=shutil.copy,
                )
            os.makedirs(state_container.path, exist_ok=True)
            start_watcher(self.service_name, state_container.path)

        else:
            LOG.warning("Unexpected state_container type: %s", type(state_container))

    def _load_state(self, state_container: SerializableState):
        state_container_type = state_type(state_container)

        file_path_base = get_state_file_path_base(state_container)
        deserializer = get_deserializer(state_container.service_name, file_path_base)
        if not deserializer:
            return

        deserialized = deserializer.deserialize()

        deserialized_type = state_type(deserialized)

        if (
            state_container_type == AccountRegionBundle[V3S3Store]
            and deserialized_type == AccountRegionBundle[LegacyS3Store]
        ):
            try:
                from .s3.migrate_to_v3 import migrate_to_v3

                LOG.info("Migrating S3 state to V3 provider...")
                self._load_state(s3_backends)
                deserialized = migrate_to_v3(s3_backends)
            except:
                LOG.exception("Error migrating S3 state to V3 provider")
                return
        elif state_container_type != deserialized_type:
            LOG.warning(
                "Unexpected deserialised state_container type: %s, expected %s",
                deserialized_type,
                state_container_type,
            )
            return

        # Set Processing because after loading state, it will take some time for opensearch/elasticsearch to start.
        if deserialized_type == AccountRegionBundle[OpenSearchStore]:
            for region_bundle in deserialized.values():
                os_store: OpenSearchStore
                for os_store in region_bundle.values():
                    for domain in os_store.opensearch_domains.values():
                        domain["Processing"] = True

        if deserialized_type == AccountRegionBundle[LambdaStore]:
            for region_bundle in deserialized.values():
                lambda_store: LambdaStore
                for lambda_store in region_bundle.values():
                    for function in lambda_store.functions.values():
                        # Workarounds for restoring state of old lambda functions
                        # 1. Call `__post_init__()` to populate `instance_id` field. This is done by `__setstate__`, but that's
                        #    only called if the `Function` had a `__getstate__` when serialized, which was not always the case.
                        if hasattr(function, "__post_init__"):
                            function.__post_init__()  # type: ignore
                        # 2. Populate the required `logging_config` field with a default value in case the field wasn't present
                        #    when the `Function` was serialized.
                        for function_version in function.versions.values():
                            if not hasattr(function_version.config, "logging_config"):
                                object.__setattr__(
                                    function_version.config, "logging_config", {}
                                )

        if isinstance(state_container, dict) and isinstance(deserialized, dict):
            state_container.update(deserialized)
        state_container.__dict__.update(deserialized.__dict__)


class SaveStateVisitor(StateVisitor):
    json_encoder = json.JSONEncoder(check_circular=False, separators=(",", ":"))

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def visit(self, state_container: StateContainer):
        if isinstance(state_container, BackendDict | AccountRegionBundle):
            self._save_state(state_container)
        elif isinstance(state_container, AssetDirectory):
            if state_container.path.startswith(BASE_DIR):
                # nothing to do - assets are written directly to the volume
                return
            dir_path = get_asset_dir_path(state_container)
            if os.path.isdir(state_container.path):
                self._sync_directories(state_container.path, dir_path)
            else:
                os.makedirs(state_container.path, exist_ok=True)
            start_watcher(self.service_name, state_container.path)
        else:
            LOG.warning("Unexpected state_container type: %s", type(state_container))

    def _save_state(self, state_container: SerializableState):
        file_path_base = get_state_file_path_base(state_container)

        os.makedirs(os.path.dirname(file_path_base), exist_ok=True)

        serializers = get_serializers(state_container.service_name, file_path_base)
        for serializer in serializers:
            serializer.serialize(state_container)

        for disabled_format in set(SerializationFormat) - set(PERSIST_FORMATS):
            path = file_path_base + disabled_format.file_ext()
            if os.path.exists(path):
                os.remove(path)

    @staticmethod
    def _sync_directories(src: str, dst: str):
        def delete_extra_files(src: str, dst: str):
            desired_files = set(os.listdir(src))
            with os.scandir(dst) as it:
                dst_entries = list(it)

            for entry in dst_entries:
                should_delete = entry.name not in desired_files
                is_dir = entry.is_dir(follow_symlinks=False)
                if should_delete and is_dir:
                    shutil.rmtree(entry)
                elif should_delete:
                    os.remove(entry)
                elif is_dir:
                    delete_extra_files(os.path.join(src, entry.name), entry.path)

        shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=shutil.copy)
        delete_extra_files(src, dst)


# TODO copy changed files directly in this handler, instead of relying on SaveStateVisitor on syncing directories
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
