# Collectfasta

A faster collectstatic command. This is a fork of the archived collectfast by @antonagestam and a drop-in replacement - you must not have both installed at the same time.

[![Test Suite](https://github.com/jasongi/collectfasta/workflows/Test%20Suite/badge.svg)](https://github.com/jasongi/collectfasta/actions?query=workflow%3A%22Test+Suite%22+branch%3Amaster)
[![Static analysis](https://github.com/jasongi/collectfasta/workflows/Static%20analysis/badge.svg?branch=master)](https://github.com/jasongi/collectfasta/actions?query=workflow%3A%22Static+analysis%22+branch%3Amaster)

**Features**

- Efficiently decide what files to upload using cached checksums
- Parallel file uploads

**Supported Storage Backends**

- `storages.backends.s3boto3.S3Boto3Storage`
- `storages.backends.gcloud.GoogleCloudStorage`
- `django.core.files.storage.FileSystemStorage`

Running Django's `collectstatic` command can become painfully slow as more and
more files are added to a project, especially when heavy libraries such as
jQuery UI are included in source code. Collectfasta customizes the builtin
`collectstatic` command, adding different optimizations to make uploading large
amounts of files much faster.


## Installation

Install the app using pip:

```bash
$ python3 -m pip install Collectfasta
```

Make sure you have this in your settings file and add `'collectfasta'` to your
`INSTALLED_APPS`, before `'django.contrib.staticfiles'`:

```python
STORAGES = (
    {
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
        },
    },
)
COLLECTFASTA_STRATEGY = "collectfasta.strategies.boto3.Boto3Strategy"
INSTALLED_APPS = (
    # ...
    "collectfasta",
)
```

**Note:** `'collectfasta'` must come before `'django.contrib.staticfiles'` in
`INSTALLED_APPS`.

##### Upload Strategies

Collectfasta Strategy|Storage Backend
---|---
collectfasta.strategies.boto3.Boto3Strategy|storages.backends.s3.S3Storage
collectfasta.strategies.gcloud.GoogleCloudStrategy|storages.backends.gcloud.GoogleCloudStorage
collectfasta.strategies.filesystem.FileSystemStrategy|django.core.files.storage.FileSystemStorage

Custom strategies can also be made for backends not listed above by
implementing the `collectfasta.strategies.Strategy` ABC.


## Usage

Collectfasta overrides Django's builtin `collectstatic` command so just run
`python manage.py collectstatic` as normal.

You can disable Collectfasta by using the `--disable-collectfasta` option or by
setting `COLLECTFASTA_ENABLED = False` in your settings file.

### Setting Up a Dedicated Cache Backend

It's recommended to setup a dedicated cache backend for Collectfasta. Every time
Collectfasta does not find a lookup for a file in the cache it will trigger a
lookup to the storage backend, so it's recommended to have a fairly high
`TIMEOUT` setting.

Configure your dedicated cache with the `COLLECTFASTA_CACHE` setting:

```python
CACHES = {
    "default": {
        # Your default cache
    },
    "collectfasta": {
        # Your dedicated Collectfasta cache
    },
}

COLLECTFASTA_CACHE = "collectfasta"
```

If `COLLECTFASTA_CACHE` isn't set, the `default` cache will be used.

**Note:** Collectfasta will never clean the cache of obsolete files. To clean
out the entire cache, use `cache.clear()`. [See docs for Django's cache
framework][django-cache].

**Note:** We recommend you to set the `MAX_ENTRIES` setting if you have more
than 300 static files, see [#47][issue-47].

[django-cache]: https://docs.djangoproject.com/en/stable/topics/cache/
[issue-47]: https://github.com/antonagestam/collectfast/issues/47

### Enable Parallel Uploads

The parallelization feature enables parallel file uploads using Python's
`concurrent.futures` module. Enable it by setting the `COLLECTFASTA_THREADS`
setting.

To enable parallel uploads, a dedicated cache backend must be setup and it must
use a backend that is thread-safe, i.e. something other than Django's default
LocMemCache.

```python
COLLECTFASTA_THREADS = 20
```


## Debugging

By default, Collectfasta will suppress any exceptions that happens when copying
and let Django's `collectstatic` handle it. To debug those suppressed errors
you can set `COLLECTFASTA_DEBUG = True` in your Django settings file.


## Contribution

Please feel free to contribute by using issues and pull requests. Discussion is
open and welcome.

### Testing

The test suite is built to run against localstack / fake-gcs-server OR live S3 and GCloud buckets.
To run live tests locally you need to provide API credentials to test against as environment variables.

```bash
export AWS_ACCESS_KEY_ID='...'
export AWS_SECRET_ACCESS_KEY='...'
export GCLOUD_API_CREDENTIALS_BASE64='{...}'  # Google Cloud credentials as Base64'd json
```

Install test dependencies and target Django version:

```bash
python3 -m pip install -r test-requirements.txt
python3 -m pip install django==5.0.2
```

Run test suite:

```bash
make test
```

Run test against localstack/fake-gcs-server:

```bash
make test-docker
```

Code quality tools are broken out from test requirements because some of them
only install on Python >= 3.7.

```bash
python3 -m pip install -r lint-requirements.txt
```

Run linters and static type check:

```bash
make lint
```


## License

Collectfasta is licensed under the MIT License, see LICENSE file for more
information.
