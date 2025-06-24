import os
from typing import Optional
from localstack.services.plugins import SERVICE_PLUGINS

from .config import BASE_DIR
from .utils import once


def prepare_service(service_name: str):
    if service_name == "s3":
        prepare_s3()
    elif service_name == "acm":
        prepare_acm()
    elif service_name == "iam":
        prepare_iam()


@once
def prepare_s3():

    from .s3.storage import PersistedS3ObjectStore
    from localstack.services.s3.models import S3Object

    service = SERVICE_PLUGINS.get_service("s3")
    store = PersistedS3ObjectStore()
    service._provider._storage_backend = store  # type: ignore

    # localstack-persist 3.0.0 persisted S3 objects in a JSON file - migrate that file to new format if necessary
    old_objects_path = os.path.join(BASE_DIR, "s3", "objects.json")
    if not os.path.exists(store.root_directory) and os.path.isfile(old_objects_path):
        from .s3.migrate_ephemeral_object_store import migrate_ephemeral_object_store

        migrate_ephemeral_object_store(old_objects_path, store)

    # HACK for CertBundles that were persisted without the `internal_last_modified`/`sse_key_hash`/`precondition` properties
    setattr(S3Object, "internal_last_modified", None)
    setattr(S3Object, "sse_key_hash", None)
    setattr(S3Object, "precondition", None)


@once
def prepare_acm():
    from moto.acm.models import CertBundle

    # HACK for CertBundles that were persisted without the `cert_authority_arn` property
    setattr(CertBundle, "cert_authority_arn", None)


@once
def prepare_iam():
    from moto.iam.models import Role

    def set_permissions_boundary(self: Role, arn: Optional[str]):
        self.permissions_boundary_arn = arn

    # In moto <5.1.6 (localstack <4.5.0,) `Role` had a `permissions_boundary` attribute, but this
    # was renamed to `permissions_boundary_arn` in moto 5.1.6, and `permissions_boundary` remained
    # as a getter-only property.
    # So, we make it settable so that it can be restored from state that was peristed with
    # `permissions_boundary`:
    if (
        (permissions_boundary := getattr(Role, "permissions_boundary", None))
        and isinstance(permissions_boundary, property)
        and permissions_boundary.fset is None
    ):
        setattr(
            Role,
            "permissions_boundary",
            permissions_boundary.setter(set_permissions_boundary),
        )
