import os
from localstack.services.plugins import SERVICE_PLUGINS

from .config import BASE_DIR
from .utils import once


def prepare_service(service_name: str):
    if service_name == "s3":
        prepare_s3()


@once
def prepare_s3():

    from .s3.storage import PersistedS3ObjectStore

    service = SERVICE_PLUGINS.get_service("s3")
    store = PersistedS3ObjectStore()
    service._provider._storage_backend = store  # type: ignore

    # localstack-persist 3.0.0 persisted S3 objects in a JSON file - migrate that file to new format if necessary
    old_objects_path = os.path.join(BASE_DIR, "s3", "objects.json")
    if not os.path.exists(store.root_directory) and os.path.isfile(old_objects_path):
        from .s3.migrate_ephemeral_object_store import migrate_ephemeral_object_store

        migrate_ephemeral_object_store(old_objects_path, store)
