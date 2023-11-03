# Changelog

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
