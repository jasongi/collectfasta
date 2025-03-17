import binascii
import hashlib
from functools import lru_cache
from azure.core.exceptions import ResourceNotFoundError
from django.core.files.storage import Storage
from storages.backends.azure_storage import AzureStorage

from .base import CachingHashStrategy


class AzureBlobStrategy(CachingHashStrategy[AzureStorage]):
    delete_not_found_exception = (ResourceNotFoundError,)

    def get_remote_file_hash(self, prefixed_path: str) -> str | None:
        normalized_path = prefixed_path.replace("\\", "/")

        blob_client = self.remote_storage.service_client.get_blob_client(
            container=self.remote_storage.azure_container,
            blob=normalized_path
        )

        try:
            properties = blob_client.get_blob_properties()

            # If content_md5 is available (<4MiB), use it
            if properties.content_settings.content_md5:
                return binascii.hexlify(properties.content_settings.content_md5).decode()

            # For larger files, create a hash from size and path
            size = properties.size

            return self._create_composite_hash(normalized_path, size)

        except ResourceNotFoundError:
            return None

    def _create_composite_hash(self, path: str, size: int) -> str:
        hash_components = f"{path}|{size}"
        return hashlib.md5(hash_components.encode()).hexdigest()

    @lru_cache(maxsize=None)
    def get_local_file_hash(self, path: str, local_storage: Storage) -> str:
        stat = (local_storage.base_location / path).stat()
        file_size = stat.st_size

        # For smaller files (<4MiB), use MD5 of content
        # https://learn.microsoft.com/en-us/rest/api/storageservices/get-blob?tabs=microsoft-entra-id#response-headers
        if file_size < 4 * 1024 * 1024:  # 4MiB
            return super().get_local_file_hash(path, local_storage)

        # For larger files, create a composite hash using only size and path
        return self._create_composite_hash(path, file_size)
