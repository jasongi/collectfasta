from typing import Optional
from typing import Type

from django.contrib.staticfiles.storage import ManifestFilesMixin
from django.core.files.storage import FileSystemStorage
from django.core.files.storage import Storage
from django.core.files.storage.memory import InMemoryStorage

from .base import HashStrategy
from .base import Strategy
from .base import _RemoteStorage


class InMemoryManifestFilesStorage(ManifestFilesMixin, InMemoryStorage):  # type: ignore
    pass


class FileSystemManifestFilesStorage(ManifestFilesMixin, FileSystemStorage):  # type: ignore
    pass


class HashingTwoPassStrategy(HashStrategy[Storage]):
    """
    Hashing strategies interact a lot with the remote storage as a part of post-processing
    This strategy will instead run the hashing strategy using InMemoryStorage first, then copy
    the files to the remote storage
    """

    first_manifest_storage: Optional[Type[ManifestFilesMixin]] = None
    second_strategy: Optional[Type[Strategy]] = None

    def __init__(self, remote_storage: _RemoteStorage) -> None:
        self.first_pass = True
        self.original_storage = remote_storage
        self.memory_storage = self._get_tmp_storage()
        self.remote_storage = self.memory_storage
        super().__init__(self.memory_storage)

    def _get_tmp_storage(self) -> Storage:
        if isinstance(self.original_storage, ManifestFilesMixin):
            return self.first_manifest_storage(location=self.original_storage.location)  # type: ignore
        else:
            raise ValueError(
                "HashingMemoryStrategy can only be used with subclasses of ManifestFilesMixin"
            )

    def wrap_storage(self, remote_storage: Storage) -> Storage:
        return self.remote_storage

    def get_remote_file_hash(self, prefixed_path: str) -> Optional[str]:
        try:
            return super().get_local_file_hash(prefixed_path, self.remote_storage)
        except FileNotFoundError:
            return None

    def second_pass_strategy(self):
        """
        Strategy that is used after the first pass of hashing is done - to copy the files
        to the remote destination.
        """
        if self.second_strategy is None:
            raise NotImplementedError(
                "second_strategy must be set to a valid strategy class"
            )
        else:
            return self.second_strategy(self.original_storage)


class WithoutPrefixMixin:
    def copy_args_hook(self, args):
        return (
            args[0].replace(self.remote_storage.location, ""),  # type: ignore
            args[1].replace(self.remote_storage.location, ""),  # type: ignore
            args[2],
        )


class TwoPassInMemoryStrategy(HashingTwoPassStrategy):
    first_manifest_storage = InMemoryManifestFilesStorage


class TwoPassFileSystemStrategy(HashingTwoPassStrategy):
    first_manifest_storage = FileSystemManifestFilesStorage
