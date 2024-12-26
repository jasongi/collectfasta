# Changelog
## 3.2.1
- change minimum django-storages version
- support for Django 5.1 and python 3.13

## 3.2.0
- Add support for custom S3ManifestStaticStorage subclasses with location set.
- Fix edge case where location is in the filename

## 3.1.3
- fixed 2-pass to copy subdirectories

## 3.1.2
- fix types to work with python 3.12

## 3.1.1
- removed type ignores, updated tests

## 3.1.0
- add new strategies for two-pass collectstatic where the first pass is file or memory based

## 3.0.1
- Refactor boto3 strategy to wrap the storage classes to re-introduce preloading of metadata

## 3.0.0

- Rename to collectfasta with new maintainer/repo
- Remove some deprecated settings
- Ability to run live tests against localstack/fake GCP instead of the real APIs
- refactor tests to use the STORAGES config
- implement preloading of S3 metadata for boto3 strategy as it was removed by django-storages
- dropped support for Python 3.6-3.8
- dropped support for Django < 4.2

## 2.2.0

- Add `post_copy_hook` and `on_skip_hook` to
  `collectfasta.strategies.base.Strategy`.
- Add `collectfasta.strategies.filesystem.CachingFileSystemStrategy`.
- Fix a bug where files weren't properly closed when read for hashing.
- Fix a bug where gzip compression level was inconsistent with S3.


## 2.1.0

- Use `concurrent.futures.ThreadPoolExecutor` instead of
  `multiprocessing.dummy.Pool` for parallel uploads.
- Support `post_process()`.

## 2.0.1

- Fix and add regression test for #178 (wrong type for `COLLECTFAST_THREADS`).
- Add tests for strictly typed settings.

## 2.0.0

- Drop support for Python 3.5.
- Drop support for Django 1.11.
- Drop support for `storages.backends.s3boto.S3BotoStorage` (remove
  `collectfasta.strategies.boto.BotoStrategy`).
- Drop support for guessing strategies, e.g. require
  `COLLECTFASTA_STRATEGY` to be set.
- Package type hints.
- Support django-storages 1.9+.
- Validate types of settings.

## Previous versions

For changes in previous versions see [releases on Github][releases].

[releases]: https://github.com/jasongi/collectfasta/releases
