# type: ignore
import logging
import os
import tempfile
from typing import Any
from typing import Optional

import botocore.exceptions
from boto3.s3.transfer import TransferConfig
from django.contrib.staticfiles.storage import ManifestFilesMixin
from django.utils.timezone import make_naive
from storages.backends.s3boto3 import S3Boto3Storage
from storages.backends.s3boto3 import S3ManifestStaticStorage
from storages.backends.s3boto3 import S3StaticStorage
from storages.utils import clean_name
from storages.utils import is_seekable
from storages.utils import safe_join
from storages.utils import setting

from collectfasta import settings

from .base import CachingHashStrategy

logger = logging.getLogger(__name__)


class S3StorageWrapperMixin:
    def __init__(self, original: S3Boto3Storage) -> None:
        default_settings = original.get_default_settings()
        for name in default_settings.keys():
            if not hasattr(self, name) and hasattr(original, name):
                setattr(self, name, getattr(original, name))
        for arg in [
            "_bucket",
            "_connections",
            "access_key",
            "secret_key",
            "security_token",
            "config",
            "_transfer_config",
        ]:
            if hasattr(original, arg):
                setattr(self, arg, getattr(original, arg))
        if not hasattr(self, "_transfer_config"):
            # not sure why, but the original doesn't have this attribute
            self._transfer_config = TransferConfig(use_threads=self.use_threads)

        self.preload_metadata = True
        self._entries = {}

    # restores the "preload_metadata" method that was removed in django-storages 1.10
    def _save(self, name, content):
        content.seek(0)
        with tempfile.SpooledTemporaryFile() as tmp:
            tmp.write(content.read())
            cleaned_name = clean_name(name)
            name = self._normalize_name(cleaned_name)
            params = self._get_write_parameters(name, content)

            if is_seekable(content):
                content.seek(0, os.SEEK_SET)
            if (
                self.gzip
                and params["ContentType"] in self.gzip_content_types
                and "ContentEncoding" not in params
            ):
                content = self._compress_content(content)
                params["ContentEncoding"] = "gzip"

            obj = self.bucket.Object(name)
            if self.preload_metadata:
                self._entries[name] = obj
            obj.upload_fileobj(content, ExtraArgs=params, Config=self._transfer_config)
            return cleaned_name

    @property
    def entries(self):
        if self.preload_metadata and not self._entries:
            self._entries = {
                entry.key: entry
                for entry in self.bucket.objects.filter(Prefix=self.location)
            }
        return self._entries

    def delete(self, name):
        super().delete(name)
        if name in self._entries:
            del self._entries[name]

    def exists(self, name):
        cleaned_name = self._normalize_name(clean_name(name))
        if self.entries:
            return cleaned_name in self.entries
        return super().exists(name)

    def size(self, name):
        cleaned_name = self._normalize_name(clean_name(name))
        if self.entries:
            entry = self.entries.get(cleaned_name)
            if entry:
                return entry.size if hasattr(entry, "size") else entry.content_length
            return 0
        return super().size(name)

    def get_modified_time(self, name):
        """
        Returns an (aware) datetime object containing the last modified time if
        USE_TZ is True, otherwise returns a naive datetime in the local timezone.
        """
        name = self._normalize_name(clean_name(name))
        entry = self.entries.get(name)
        if entry is None:
            entry = self.bucket.Object(name)
        if setting("USE_TZ"):
            # boto3 returns TZ aware timestamps
            return entry.last_modified
        else:
            return make_naive(entry.last_modified)


class ManifestFilesWrapperMixin:
    def __init__(self, original: ManifestFilesMixin) -> None:
        super().__init__(original)
        if original.manifest_storage == original:
            self.manifest_storage = self
        else:
            self.manifest_storage = original.manifest_storage
        for arg in [
            "hashed_files",
            "manifest_hash",
            "support_js_module_import_aggregation",
            "patterns",
            "_patterns",
            "hashed_files",
        ]:
            if hasattr(original, arg):
                setattr(self, arg, getattr(original, arg))


class S3StorageWrapper(S3StorageWrapperMixin, S3Boto3Storage):
    pass


class S3StaticStorageWrapper(S3StorageWrapperMixin, S3StaticStorage):
    pass


class S3ManifestStaticStorageWrapper(
    ManifestFilesWrapperMixin, S3StorageWrapperMixin, S3ManifestStaticStorage
):
    pass


class Boto3Strategy(CachingHashStrategy[S3Boto3Storage]):
    def __init__(self, remote_storage: S3Boto3Storage) -> None:
        self.remote_storage = self.wrapped_storage(remote_storage)
        super().__init__(self.remote_storage)
        self.use_gzip = settings.aws_is_gzipped
        self._entries: Optional[dict[str, Any]] = None

    def wrapped_storage(self, remote_storage: S3Boto3Storage) -> S3Boto3Storage:
        if isinstance(remote_storage, S3ManifestStaticStorage):
            return S3ManifestStaticStorageWrapper(remote_storage)
        elif isinstance(remote_storage, S3StaticStorage):
            return S3StaticStorageWrapper(remote_storage)
        elif isinstance(remote_storage, S3Boto3Storage):
            return S3StorageWrapper(remote_storage)
        return remote_storage

    def wrap_storage(self, remote_storage: S3Boto3Storage) -> S3Boto3Storage:
        return self.remote_storage

    def _normalize_path(self, prefixed_path: str) -> str:
        path = str(safe_join(self.remote_storage.location, prefixed_path))
        return path.replace("\\", "")

    @staticmethod
    def _clean_hash(quoted_hash: Optional[str]) -> Optional[str]:
        """boto returns hashes wrapped in quotes that need to be stripped."""
        if quoted_hash is None:
            return None
        assert quoted_hash[0] == quoted_hash[-1] == '"'
        return quoted_hash[1:-1]

    def get_remote_file_hash(self, prefixed_path: str) -> Optional[str]:
        normalized_path = self._normalize_path(prefixed_path)
        logger.debug("Getting file hash", extra={"normalized_path": normalized_path})
        try:
            hash_: str
            if normalized_path in self.remote_storage.entries:
                hash_ = self.remote_storage.entries[normalized_path].e_tag
            else:
                hash_ = self.remote_storage.bucket.Object(normalized_path).e_tag
        except botocore.exceptions.ClientError:
            logger.debug("Error on remote hash request", exc_info=True)
            return None
        return self._clean_hash(hash_)

    def pre_should_copy_hook(self) -> None:
        if settings.threads:
            logger.info("Resetting connection")
            self.remote_storage._connection = None
