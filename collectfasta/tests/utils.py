import functools
import os
import pathlib
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from typing import Callable
from typing import TypeVar
from typing import cast

from django.conf import settings as django_settings
from django.utils.module_loading import import_string
from storages.backends.azure_storage import AzureStorage
from storages.backends.gcloud import GoogleCloudStorage
from storages.backends.s3boto3 import S3ManifestStaticStorage
from typing_extensions import Final

from collectfasta import settings

static_dir: Final = pathlib.Path(django_settings.STATICFILES_DIRS[0])

F = TypeVar("F", bound=Callable[..., Any])


def make_100_files():
    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in range(50):
            executor.submit(create_big_referenced_static_file)
        executor.shutdown(wait=True)


def get_fake_client():
    from google.api_core.client_options import ClientOptions
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import storage

    client = storage.Client(
        credentials=AnonymousCredentials(),
        project="test",
        client_options=ClientOptions(api_endpoint=django_settings.GS_CUSTOM_ENDPOINT),
    )
    return client


class GoogleCloudStorageTest(GoogleCloudStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if django_settings.GS_CUSTOM_ENDPOINT:
            # Use the fake client if we are using the fake endpoint
            self._client = get_fake_client()


class AzureBlobStorageTest(AzureStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.create_container()

    def create_container(self):
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import BlobServiceClient

        connection_string = django_settings.AZURE_CONNECTION_STRING
        continer_name = django_settings.AZURE_CONTAINER

        client = BlobServiceClient.from_connection_string(connection_string)

        try:
            client.create_container(continer_name)
        except ResourceExistsError:
            # recreate orphaned containers
            client.delete_container(continer_name)
            client.create_container(continer_name)


class S3ManifestCustomStaticStorage(S3ManifestStaticStorage):
    location = "prefix"
    manifest_name = "prefixfiles.json"


def create_two_referenced_static_files() -> tuple[pathlib.Path, pathlib.Path]:
    """Create a static file, then another file with a reference to the file"""
    path = create_static_file()
    folder_path = static_dir / (path.stem + "_folder")
    folder_path.mkdir()
    reference_path = folder_path / f"{uuid.uuid4().hex}.html"
    reference_path.write_text(f"{{% static '../{path.name}' %}}")
    return (path, reference_path)


def create_static_file() -> pathlib.Path:
    """Write random characters to a file in the static directory."""
    path = static_dir / f"{uuid.uuid4().hex}.html"
    path.write_text("".join(chr(random.randint(0, 64)) for _ in range(500)))
    return path


def create_big_referenced_static_file() -> tuple[pathlib.Path, pathlib.Path]:
    """Create a big static file, then another file with a reference to the file"""
    path = create_big_static_file()
    reference_path = static_dir / f"{uuid.uuid4().hex}.html"
    reference_path.write_text(f"{{% static '{path.name}' %}}")
    return (path, reference_path)


def create_big_static_file() -> pathlib.Path:
    """Write random characters to a file in the static directory."""
    path = static_dir / f"{uuid.uuid4().hex}.html"
    path.write_text("".join(chr(random.randint(0, 64)) for _ in range(100000)))
    return path


def create_larger_than_4mb_referenced_static_file() -> tuple[
    pathlib.Path, pathlib.Path
]:
    """Create a larger than 4mb static file, then another file with a reference to the file"""
    path = create_larger_than_4mb_file()
    reference_path = static_dir / f"{uuid.uuid4().hex}.html"
    reference_path.write_text(f"{{% static '{path.name}' %}}")
    return (path, reference_path)


def create_larger_than_4mb_file() -> pathlib.Path:
    """Write random characters to a file larger than 4mb in the static directory."""
    size_bytes = 4 * 1024 * 1024 + 1  # 4MB + 1 byte
    path = static_dir / f"{uuid.uuid4().hex}.html"
    path.write_text("".join(chr(random.randint(0, 64)) for _ in range(size_bytes)))
    return path


def clean_static_dir() -> None:
    clean_static_dir_recurse(static_dir.as_posix())
    clean_static_dir_recurse(django_settings.AWS_LOCATION)
    clean_static_dir_recurse(S3ManifestCustomStaticStorage.location)


def clean_static_dir_recurse(location: str) -> None:
    try:
        for filename in os.listdir(location):
            file = pathlib.Path(location) / filename
            # don't accidentally wipe the whole drive if someone puts / as location.
            if (
                "collectfasta" in str(file.absolute())
                and ".." not in str(file.as_posix())
                and len(list(filter(lambda x: x == "/", str(file.absolute())))) > 2
            ):
                if file.is_file():
                    file.unlink()
                elif file.is_dir():
                    clean_static_dir_recurse(file.as_posix())
                    file.rmdir()
    except FileNotFoundError:
        pass


def override_setting(name: str, value: Any) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            original = getattr(settings, name)
            setattr(settings, name, value)
            try:
                return fn(*args, **kwargs)
            finally:
                setattr(settings, name, original)

        return cast(F, wrapper)

    return decorator


def override_storage_attr(name: str, value: Any) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            storage = import_string(django_settings.STORAGES["staticfiles"]["BACKEND"])
            if hasattr(storage, name):
                original = getattr(storage, name)
            else:
                original = None
            setattr(storage, name, value)
            try:
                return fn(*args, **kwargs)
            finally:
                setattr(storage, name, original)

        return cast(F, wrapper)

    return decorator
