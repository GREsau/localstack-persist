# localstack-persist

[LocalStack](https://github.com/localstack/localstack) Community Edition with support for persisted resources.

[![Docker pulls](https://img.shields.io/docker/pulls/gresau/localstack-persist?logo=docker)](https://hub.docker.com/r/gresau/localstack-persist)
[![CI Build](https://github.com/GREsau/localstack-persist/actions/workflows/test.yml/badge.svg)](https://github.com/GREsau/localstack-persist/actions/workflows/test.yml)

## Overview

As of LocalStack 1.0, [persistence](https://docs.localstack.cloud/references/persistence-mechanism/) is a pro-only feature, so is unavailable when using Community Edition. [Community Cloud Pods](https://docs.localstack.cloud/user-guide/tools/cloud-pods/community/) are available, but these require manual saving/restoring of state. localstack-persist adds out-of-the-box persistence, which is saved whenever a resource is modified, and automatically restored on container startup.

## Usage

localstack-persist is distributed as a docker image, made to be a drop-in replacement for the official [LocalStack Community Edition docker image](https://hub.docker.com/r/localstack/localstack). For example, to use it with docker-compose, you could use a `docker-compose.yml` file like:

```yaml
version: "3.8"
services:
  localstack:
    image: gresau/localstack-persist # instead of localstack/localstack
    ports:
      - "4566:4566"
    volumes:
      - "./my-localstack-data:/persisted-data"
```

This will use the `latest` image, which is built daily from the `main` branch, and based on `localstack/localstack:latest` (the nightly LocalStack image). For other available tags, see the list on [Docker Hub](https://hub.docker.com/r/gresau/localstack-persist/tags) or the [GitHub releases](https://github.com/GREsau/localstack-persist/releases). The Major.Minor version of a localstack-persist image's tag will track the version of LocalStack that the image is based on - e.g. `gresau/localstack-persist:2.2.X` will always be based on `localstack/localstack:2.2.Y` (where X and Y may be different numbers).

Persisted data is saved inside the container at `/persisted-data`, so you'll typically want to mount a volume at that path - the example compose file above will keep persisted data in the `my-localstack-data` on the host.

## Configuration

By default, all services will persist their resources to disk. To disable persistence for a particular service, set the container's `PERSIST_[SERVICE]` environment variable to 0 (e.g. `PERSIST_CLOUDWATCH=0`). Or to enable persistence for only specific services, set `PERSIST_DEFAULT=0` and `PERSIST_[SERVICE]=1`. For example, to enable persistence for only DynamoDB and S3, you could use the `docker-compose.yml` file:

```yaml
    ...
    image: gresau/localstack-persist
    ports:
      - "4566:4566"
    volumes:
      - "./my-localstack-data:/persisted-data"
    environment:
      - PERSIST_DEFAULT=0
      - PERSIST_DYNAMODB=1
      - PERSIST_S3=1
```

You can still set any of [LocalStack's configuration options](https://docs.localstack.cloud/references/configuration/) in the usual way - however, you do NOT need to set `PERSISTENCE=1`, as that just controls LocalStack's built-in persistence which does not function in Community Edition.

## Supported Services

localstack-persist uses largely the same hooks as the official persistence mechanism, so all (non-pro) services supported by official persistence should work with localstack-persist - [see the list here](https://docs.localstack.cloud/references/persistence-mechanism/#supported--tested).

The following services have basic save/restore functionality verified by automated tests:

- ACM
- DynamoDB
- Elasticsearch
- IAM
- Lambda
- SQS
- S3

## License

localstack-persist is released under the [Apache License 2.0](LICENSE). LocalStack is used under the [Apache License 2.0](https://github.com/localstack/localstack/blob/master/LICENSE.txt).
