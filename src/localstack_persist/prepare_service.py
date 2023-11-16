from importlib import import_module
from collections.abc import Callable
from localstack.services.s3.v3.storage.ephemeral import EphemeralS3ObjectStore
from localstack.services.plugins import SERVICE_PLUGINS, ServiceLifecycleHook
import sys


def prepare_service(service_name: str):
    if service_name == "lambda":
        prepare_lambda()
    elif service_name == "s3":
        prepare_s3()


def once(f: Callable):
    has_run = False

    def wrapper(*args, **kwargs):
        nonlocal has_run
        if not has_run:
            has_run = True
            return f(*args, **kwargs)

    return wrapper


@once
def prepare_lambda():
    # Define localstack.services.awslambda as a backward-compatible alias for localstack.services.lambda_
    sys.modules.setdefault(
        "localstack.services.awslambda",
        import_module("localstack.services.lambda_"),
    )


@once
def prepare_s3():
    # The original implementation of _key_from_s3_object calls hash(), which is not stable between different
    # process executions, which breaks our persistence. To work-around this, we patch that function to instead
    # use a stable "hash" function. MD5/SHA etc. would be fine, but for simplicity and debuggability we just
    # use the identity function (i.e. don't hash it at all)
    EphemeralS3ObjectStore._key_from_s3_object = staticmethod(
        lambda s3_object: f"{s3_object.key}?{s3_object.version_id or 'null'}"
    )
