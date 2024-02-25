import logging
from typing import Optional

import botocore.exceptions
from storages.backends.s3boto3 import S3Boto3Storage
from storages.utils import safe_join

from collectfasta import settings

from .base import CachingHashStrategy
from botocore.exceptions import ClientError
from storages.utils import clean_name
from storages.backends.s3boto3 import S3Boto3Storage

logger = logging.getLogger(__name__)


class Boto3Strategy(CachingHashStrategy[S3Boto3Storage]):
    def __init__(self, remote_storage: S3Boto3Storage) -> None:
        super().__init__(remote_storage)
        self.wrap_remote()
        # self.remote_storage.preload_metadata = True
        self.use_gzip = settings.aws_is_gzipped
        self._entries = None

    def wrap_remote(self):
        if hasattr(self.remote_storage, "bucket"):
            self.original_exists = self.remote_storage.exists
            self.remote_storage.exists = (
                lambda name: name in self._entries or self.original_exists(name)
            )
            self.preload_metadata()

    def preload_metadata(self) -> None:
        try:
            self._entries = {
                entry.key: entry
                for entry in self.remote_storage.bucket.objects.filter(
                    Prefix=self.remote_storage.location
                )
            }
        except ClientError:
            logger.debug("Error on remote metadata request", exc_info=True)

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
            hash_: str = self.remote_storage.bucket.Object(normalized_path).e_tag
        except botocore.exceptions.ClientError:
            logger.debug("Error on remote hash request", exc_info=True)
            return None
        return self._clean_hash(hash_)

    def pre_should_copy_hook(self) -> None:
        if settings.threads:
            logger.info("Resetting connection")
            self.remote_storage._connection = None
