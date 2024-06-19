from importlib import import_module
import os
import sys
from localstack.services.plugins import SERVICE_PLUGINS

from .config import BASE_DIR
from .utils import once


def prepare_service(service_name: str):
    if service_name == "lambda":
        prepare_lambda()
    elif service_name == "s3":
        prepare_s3()


@once
def prepare_lambda():
    # Define localstack.services.awslambda as a backward-compatible alias for localstack.services.lambda_
    sys.modules.setdefault(
        "localstack.services.awslambda",
        import_module("localstack.services.lambda_"),
    )
    sys.modules.setdefault(
        "localstack.services.awslambda.invocation.lambda_models",
        import_module("localstack.services.lambda_.invocation.lambda_models"),
    )
    sys.modules.setdefault(
        "localstack.services.awslambda.invocation.models",
        import_module("localstack.services.lambda_.invocation.models"),
    )


@once
def prepare_s3():
    # Define localstack.services.s3.v3.models as a backward-compatible alias for localstack.services.s3.models
    try:
        import_module("localstack.services.s3.v3")
    except ModuleNotFoundError:
        sys.modules.setdefault(
            "localstack.services.s3.v3",
            import_module("localstack.services.s3"),
        )
        sys.modules.setdefault(
            "localstack.services.s3.v3.models",
            import_module("localstack.services.s3.models"),
        )

    from .s3.storage import PersistedS3ObjectStore

    service = SERVICE_PLUGINS.get_service("s3")
    store = PersistedS3ObjectStore()
    service._provider._storage_backend = store  # type: ignore

    # localstack-persist 3.0.0 persisted S3 objects in a JSON file - migrate that file to new format if necessary
    old_objects_path = os.path.join(BASE_DIR, "s3", "objects.json")
    if not os.path.exists(store.root_directory) and os.path.isfile(old_objects_path):
        from .s3.migrate_ephemeral_object_store import migrate_ephemeral_object_store

        migrate_ephemeral_object_store(old_objects_path, store)
