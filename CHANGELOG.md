# Changelog

## [2.2.1] - 2023-08-13

_Based on [LocalStack 2.2.0](https://github.com/localstack/localstack/releases/tag/v2.2.0)_

### Fixed:

- Lambda functions restored from persisted state can now be invoked

### Changed

- Performance improvement - don't trigger persisting of service state in response to a side-effect-free API request (e.g. GET requests, Describe... operations, List... operations)
- Update (and pin) jsonpickle to v3.0.2

## [2.2.0] - 2023-08-06

_Based on [LocalStack 2.2.0](https://github.com/localstack/localstack/releases/tag/v2.2.0)_

**🎉 Initial release! 🎉**
