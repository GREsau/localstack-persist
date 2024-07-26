# For back-compat, replace "old" module paths with their newer equivalents
path_replacements = {
    "localstack.services.awslambda": "localstack.services.lambda_",
    "localstack.services.s3.v3": "localstack.services.s3",
}


def compat_module_path(path: str):
    for old, new in path_replacements.items():
        path = path.replace(old, new)
    return path
