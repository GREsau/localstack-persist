from typing import cast
from localstack.services.stores import AccountRegionBundle
from moto.s3.models import S3BackendDict, S3Backend, FakeKey
from localstack.services.s3.v3.models import S3Store, S3Bucket, S3Object
from localstack.services.s3.utils import get_owner_for_account_id, get_canned_acl
from localstack.aws.api.s3 import BucketCannedACL, StorageClass
import io

from .storage import PersistedS3ObjectStore


def migrate_to_v3(
    backends: S3BackendDict,
) -> AccountRegionBundle[S3Store]:
    account_region_bundle = AccountRegionBundle[S3Store]("s3", S3Store)
    objects = PersistedS3ObjectStore()

    for account_id, account_backend in backends.items():
        region_bundle = account_region_bundle[account_id]

        if "global" not in account_backend:
            continue

        backend: S3Backend = account_backend["global"]

        for fake_bucket in backend.buckets.values():
            store = region_bundle[fake_bucket.region_name]

            owner = get_owner_for_account_id(account_id)
            acl = get_canned_acl(
                cast(BucketCannedACL, BucketCannedACL.private), owner=owner
            )

            s3_bucket = S3Bucket(
                name=fake_bucket.name,
                account_id=account_id,
                bucket_region=fake_bucket.region_name,
                owner=owner,
                acl=acl,
            )

            store.buckets[fake_bucket.name] = s3_bucket
            store.global_bucket_map[fake_bucket.name] = s3_bucket.bucket_account_id

            objects.create_bucket(fake_bucket.name)

            for fake_key in fake_bucket.keys.values():
                if not isinstance(fake_key, FakeKey):
                    continue

                acl = get_canned_acl(
                    cast(BucketCannedACL, BucketCannedACL.private),
                    owner=s3_bucket.owner,
                )
                s3_object = S3Object(
                    key=fake_key.name,
                    version_id=fake_key.version_id,
                    storage_class=cast(StorageClass, fake_key.storage_class),
                    expires=fake_key._expiry,
                    system_metadata={
                        k.replace("-", ""): v
                        for k, v in fake_key.metadata.store.items()
                    },
                    acl=acl,
                    owner=s3_bucket.owner,
                )

                with objects.open(fake_bucket.name, s3_object) as s3_stored_object:
                    s3_stored_object.write(io.BytesIO(fake_key.value))

                s3_bucket.objects.set(fake_key.name, s3_object)

    return account_region_bundle
