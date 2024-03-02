import base64
import os
import pathlib
import sys
import tempfile

# import python and django versions
from django import get_version
from google.cloud import storage
from google.oauth2 import service_account

base_path = pathlib.Path.cwd()

# Set USE_TZ to True to work around bug in django-storages
USE_TZ = True

SECRET_KEY = "nonsense"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-collectfasta",
    }
}
TEMPLATE_LOADERS = (
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
    "django.template.loaders.eggs.Loader",
)
TEMPLATE_DIRS = [str(base_path / "collectfasta/templates")]
INSTALLED_APPS = ("collectfasta", "django.contrib.staticfiles")
STATIC_URL = "/staticfiles/"
# python then django version
AWS_LOCATION = sys.version.split(" ")[0] + "-" + get_version()
GS_LOCATION = sys.version.split(" ")[0] + "-" + get_version()
STATIC_ROOT = str(base_path / "static_root")
MEDIA_ROOT = str(base_path / "fs_remote")
STATICFILES_DIRS = [str(base_path / "static")]
STORAGES = {
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
}
COLLECTFASTA_STRATEGY = "collectfasta.strategies.boto3.Boto3Strategy"
COLLECTFASTA_DEBUG = True

GZIP_CONTENT_TYPES = ("text/plain",)
AWS_IS_GZIPPED = False
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = None
S3_USE_SIGV4 = True
AWS_S3_SIGNATURE_VERSION = "s3v4"

# AWS
AWS_STORAGE_BUCKET_NAME = "collectfasta"

FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", default=FAKE_AWS_ACCESS_KEY_ID)
AWS_SECRET_ACCESS_KEY = os.environ.get(
    "AWS_SECRET_ACCESS_KEY",
    default=FAKE_AWS_SECRET_ACCESS_KEY,
)
AWS_S3_REGION_NAME = "ap-southeast-2"
if AWS_ACCESS_KEY_ID == FAKE_AWS_ACCESS_KEY_ID:
    AWS_ENDPOINT_URL = "http://localhost.localstack.cloud:4567"
    AWS_S3_ENDPOINT_URL = "http://localhost.localstack.cloud:4567"

GCLOUD_API_CREDENTIALS_BASE64 = os.environ.get(
    "GCLOUD_API_CREDENTIALS_BASE64", default=None
)
# Google Cloud
if GCLOUD_API_CREDENTIALS_BASE64:
    # live test
    GS_CUSTOM_ENDPOINT = None
    with tempfile.NamedTemporaryFile() as file:
        gcloud_credentials_json = base64.b64decode(GCLOUD_API_CREDENTIALS_BASE64)
        file.write(gcloud_credentials_json)
        file.read()
        GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
            file.name
        )
else:
    GS_CUSTOM_ENDPOINT = "http://127.0.0.1:5050"
    try:
        storage.Client(
            client_options={"api_endpoint": GS_CUSTOM_ENDPOINT},
            use_auth_w_custom_endpoint=False,
        ).create_bucket("collectfasta")
    except Exception:
        pass
GS_BUCKET_NAME = "collectfasta"
