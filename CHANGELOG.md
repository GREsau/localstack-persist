# Changelog

## [3.6.1] - 2024-08-28

_Based on [LocalStack 3.6.0](https://github.com/localstack/localstack/releases/tag/v3.6.0)_

### Fixed

- Fixed not being able to store S3 objects with keys longer than ~250 characters (https://github.com/GREsau/localstack-persist/issues/14)

## [3.6.0] - 2024-07-26

_Based on [LocalStack 3.6.0](https://github.com/localstack/localstack/releases/tag/v3.6.0)_

No changes are in this version other than update of localstack.

## [3.5.0] - 2024-06-13

_Based on [LocalStack 3.5.0](https://github.com/localstack/localstack/releases/tag/v3.5.0)_

### Changed

- Update versions of jsonpickle and watchdog

## [3.4.0] - 2024-04-27

_Based on [LocalStack 3.4.0](https://github.com/localstack/localstack/releases/tag/v3.4.0)_

### Fixed

- Fixed a race condition that could occur when a request is served while data is being persisted to disk (https://github.com/GREsau/localstack-persist/issues/11)

## [3.3.0] - 2024-04-03

_Based on [LocalStack 3.3.0](https://github.com/localstack/localstack/releases/tag/v3.3.0)_

No changes are in this version other than update of localstack.

## [3.2.0] - 2024-04-03

_Based on [LocalStack 3.2.0](https://github.com/localstack/localstack/releases/tag/v3.2.0)_

No changes are in this version other than update of localstack.

## [3.1.0] - 2024-01-26

_Based on [LocalStack 3.1.0](https://github.com/localstack/localstack/releases/tag/v3.1.0)_

No changes are in this version other than update of localstack.

## [3.0.3] - 2023-12-19

_Based on [LocalStack 3.0.2](https://github.com/localstack/localstack/releases/tag/v3.0.2)_

No changes are in this version other than update of localstack. This does, however, fix a bug which prevented persistence of SQS when sending requests with the legacy "query" protocol (https://github.com/GREsau/localstack-persist/issues/7).

## [3.0.2] - 2023-11-26

_Based on [LocalStack 3.0.1](https://github.com/localstack/localstack/releases/tag/v3.0.1)_

### Fixed

- Fixed a bug where, in rare cases, a service's state may be persisted after a request has been received but before the request has been processed - this would cause any state changes from the request to not be persisted
- Fixed overzealous locking which previously caused requests to be blocked while resources are being persisted to disk

### Added

- Docker images now include [OCI Image Format Specification](https://github.com/opencontainers/image-spec/blob/master/annotations.md) labels including metadata such as build-time and version
- _**Experimental**_: Files can now be persisted as a binary format instead of JSON, considerably improving performance. This is currently disabled by default, but can be enabled by setting the environment variable `PERSIST_FORMAT=binary`.

## [3.0.1] - 2023-11-21

_Based on [LocalStack 3.0.0](https://github.com/localstack/localstack/releases/tag/v3.0.0)_

### Fixed

- Excessive memory usage when persisting S3 objects (https://github.com/GREsau/localstack-persist/issues/1)

## [3.0.0] - 2023-11-16

_Based on [LocalStack 3.0.0](https://github.com/localstack/localstack/releases/tag/v3.0.0)_

No changes are in this version other than update of localstack, however please be aware of changes you may encounter due to the new native `v3` provider for S3 (available since localstack 2.3.0, and supported by localstack-persist since 2.3.2):

- The `v3` S3 provider is now used by default, which stores data in a different format than the previous `v2` provider. When first using the `v3` provider, any existing (`v2`-format) persisted S3 _objects_ will be automatically migrated to the new `v3` format. However, other S3 data (e.g. unfinished multipart uploads, CORS rules) will not be migrated and will be lost when switching to the `v3` provider. S3 data that was persisted using the `v3` provider cannot be loaded when using the `v2` provider. You can stay on the `v2` provider in 3.0.0+ by setting the config `PROVIDER_OVERRIDE_S3=v2`, but this is likely to be removed in a future major version of localstack.

## [2.3.3] - 2023-11-14

_Based on [LocalStack 2.3.2](https://github.com/localstack/localstack/releases/tag/v2.3.2)_

### Fixed

- Persistence of Elasticsearch (and Opensearch)
- Explicitly enabling persistence of a particular service will now also enable persistence for services that it depends on (unless they have persistence explicitly disabled)

## [2.3.2] - 2023-11-03

_Based on [LocalStack 2.3.2](https://github.com/localstack/localstack/releases/tag/v2.3.2)_

### Added

- Support for the new opt-in LocalStack-native S3 provider (`PROVIDER_OVERRIDE_S3=v3`). When using the V3 provider, any existing (pre-V3) persisted S3 objects will be automatically migrated to the new V3 format. Other S3 data (e.g. unfinished multipart uploads, CORS rules) will not be migrated and will be lost when switching to the V3 provider. Data saved in the V3 format cannot be loaded when using the default (pre-V3) S3 provider. In other words, you can safely switch from the default S3 provider to the V3 S3 provider without losing any persisted S3 objects, but you then won't be able to switch back again.

## [2.3.1] - 2023-10-22

_Based on [LocalStack 2.3.2](https://github.com/localstack/localstack/releases/tag/v2.3.2)_

No changes are in this version other than update of localstack

## [2.3.0] - 2023-09-30

_Based on [LocalStack 2.3.0](https://github.com/localstack/localstack/releases/tag/v2.3.0)_

No changes are in this version other than update of localstack

### Known issues

- localstack-persist is not compatible with the new opt-in LocalStack-native S3 provider (`PROVIDER_OVERRIDE_S3=v3`)

## [2.2.1] - 2023-08-13

_Based on [LocalStack 2.2.0](https://github.com/localstack/localstack/releases/tag/v2.2.0)_

### Fixed

- Lambda functions restored from persisted state can now be invoked

### Changed

- Performance improvement - don't trigger persisting of service state in response to a side-effect-free API request (e.g. GET requests, Describe... operations, List... operations)
- Update (and pin) jsonpickle to v3.0.2

## [2.2.0] - 2023-08-06

_Based on [LocalStack 2.2.0](https://github.com/localstack/localstack/releases/tag/v2.2.0)_

**🎉 Initial release! 🎉**
