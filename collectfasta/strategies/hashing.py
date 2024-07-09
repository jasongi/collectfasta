from typing import Any
from typing import Callable
from typing import Optional
from typing import Protocol
from typing import Tuple
from typing import Type
from typing import Union
from typing import cast
from typing import runtime_checkable

from django.contrib.staticfiles.storage import ManifestFilesMixin
from django.core.files.storage import FileSystemStorage
from django.core.files.storage import Storage
from django.core.files.storage.memory import InMemoryStorage
from django.utils.functional import LazyObject

from .base import HashStrategy
from .base import Strategy


@runtime_checkable
class LocationConstructorProtocol(Protocol):

    def __init__(self, location: Optional[str]) -> None: ...


@runtime_checkable
class HasLocationProtocol(Protocol):
    location: str


class InMemoryManifestFilesStorage(ManifestFilesMixin, InMemoryStorage):
    url: Callable[..., Any]


class FileSystemManifestFilesStorage(ManifestFilesMixin, FileSystemStorage):
    url: Callable[..., Any]


OriginalStorage = Union[
    LocationConstructorProtocol,
    HasLocationProtocol,
    Storage,
    ManifestFilesMixin,
    LazyObject,
]


class HashingTwoPassStrategy(HashStrategy[Storage]):
    """
    Hashing strategies interact a lot with the remote storage as a part of post-processing
    This strategy will instead run the hashing strategy using InMemoryStorage first, then copy
    the files to the remote storage
    """

    first_manifest_storage: Type[OriginalStorage]
    second_strategy: Type[Strategy[Storage]]
    original_storage: OriginalStorage
    memory_storage: OriginalStorage

    def __init__(self, remote_storage: OriginalStorage) -> None:
        assert issubclass(self.first_manifest_storage, ManifestFilesMixin)
        assert isinstance(remote_storage, ManifestFilesMixin)
        self.first_pass = True
        self.original_storage = remote_storage
        self.memory_storage = self._get_tmp_storage()
        assert isinstance(self.memory_storage, Storage)
        self.remote_storage = self.memory_storage
        super().__init__(self.memory_storage)

    def _get_tmp_storage(self) -> OriginalStorage:
        # python 3.12 freezes types at runtime, which does not play nicely with
        # LazyObject so we need to cast the type here
        location = cast(HasLocationProtocol, self.original_storage).location
        assert issubclass(self.first_manifest_storage, LocationConstructorProtocol)
        return cast(
            OriginalStorage,
            self.first_manifest_storage(location=location),
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
            assert isinstance(self.original_storage, Storage)
            return self.second_strategy(self.original_storage)


Task = Tuple[str, str, Storage]


class StrategyWithLocationProtocol:
    remote_storage: Any


class WithoutPrefixMixin(StrategyWithLocationProtocol):

    def copy_args_hook(self, args: Task) -> Task:
        assert isinstance(self.remote_storage, HasLocationProtocol)
        if self.remote_storage.location == "" or self.remote_storage.location.endswith(
            "/"
        ):
            location = self.remote_storage.location
        else:
            location = f"{self.remote_storage.location}/"
        return (
            args[0].replace(location, ""),
            args[1].replace(location, ""),
            args[2],
        )


class TwoPassInMemoryStrategy(HashingTwoPassStrategy):
    first_manifest_storage = InMemoryManifestFilesStorage


class TwoPassFileSystemStrategy(HashingTwoPassStrategy):
    first_manifest_storage = FileSystemManifestFilesStorage
