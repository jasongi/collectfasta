import functools
import os
import pathlib
import random
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from typing import Callable
from typing import Type
from typing import TypeVar
from typing import cast

import pytest
from django.conf import settings as django_settings
from django.utils.module_loading import import_string
from storages.backends.gcloud import GoogleCloudStorage
from typing_extensions import Final

from collectfasta import settings

live_test = pytest.mark.live_test

speed_test_mark = pytest.mark.speed_test
speed_test_option = pytest.mark.skipif("not config.getoption('speedtest')")


def speed_test(func):
    return speed_test_mark(speed_test_option(func))


static_dir: Final = pathlib.Path(django_settings.STATICFILES_DIRS[0])

F = TypeVar("F", bound=Callable[..., Any])


def make_100_files():
    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in range(100):
            executor.submit(create_big_static_file)
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


def make_test(func: F) -> Type[unittest.TestCase]:
    """
    Creates a class that inherits from `unittest.TestCase` with the decorated
    function as a method. Create tests like this:

    >>> fn = lambda x: 1337
    >>> @make_test
    ... def test_fn(case):
    ...     case.assertEqual(fn(), 1337)
    """
    case = type(func.__name__, (unittest.TestCase,), {func.__name__: func})
    case.__module__ = func.__module__
    return case


def many(**mutations: Callable[[F], F]) -> Callable[[F], Type[unittest.TestCase]]:
    def test(func: F) -> Type[unittest.TestCase]:
        """
        Creates a class that inherits from `unittest.TestCase` with the decorated
        function as a method. Create tests like this:

        >>> fn = lambda x: 1337
        >>> @make_test
        ... def test_fn(case):
        ...     case.assertEqual(fn(), 1337)
        """
        case_dict = {
            "test_%s" % mutation_name: mutation(func)
            for mutation_name, mutation in mutations.items()
        }

        case = type(func.__name__, (unittest.TestCase,), case_dict)
        case.__module__ = func.__module__
        return case

    return test


def create_static_file() -> pathlib.Path:
    """Write random characters to a file in the static directory."""
    path = static_dir / f"{uuid.uuid4().hex}.txt"
    path.write_text("".join(chr(random.randint(0, 64)) for _ in range(500)))
    return path


def create_big_static_file() -> pathlib.Path:
    """Write random characters to a file in the static directory."""
    path = static_dir / f"{uuid.uuid4().hex}.txt"
    path.write_text("".join(chr(random.randint(0, 64)) for _ in range(100000)))
    return path


def clean_static_dir() -> None:
    for filename in os.listdir(static_dir.as_posix()):
        file = static_dir / filename
        if file.is_file():
            file.unlink()


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
