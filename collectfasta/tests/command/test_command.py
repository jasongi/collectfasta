import timeit
from typing import Callable
from typing import Iterator
from unittest import TestCase
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings as override_django_settings
from django.test.utils import override_settings

from collectfasta.management.commands.collectstatic import Command
from collectfasta.tests.utils import assert_static_file_number
from collectfasta.tests.utils import clean_static_dir
from collectfasta.tests.utils import create_static_file
from collectfasta.tests.utils import create_two_referenced_static_files
from collectfasta.tests.utils import live_test
from collectfasta.tests.utils import make_100_files
from collectfasta.tests.utils import make_test
from collectfasta.tests.utils import many
from collectfasta.tests.utils import override_setting
from collectfasta.tests.utils import override_storage_attr
from collectfasta.tests.utils import speed_test

from .utils import call_collectstatic


def generate_storage_variations(
    storages: dict, strategies: dict
) -> Iterator[tuple[str, override_settings]]:
    for storage_name, storage_settings in storages.items():
        for strategy_name, strategy_settings in strategies.items():
            yield (
                f"{storage_name}_{strategy_name}",
                override_django_settings(
                    STORAGES={"staticfiles": {"BACKEND": storage_settings}},
                    COLLECTFASTA_STRATEGY=strategy_settings,
                ),
            )


aws_backend_confs = {
    **dict(
        generate_storage_variations(
            {
                "boto3": "storages.backends.s3.S3Storage",
                "boto3static": "storages.backends.s3.S3StaticStorage",
            },
            {
                "base": "collectfasta.strategies.boto3.Boto3Strategy",
            },
        )
    ),
    **dict(
        generate_storage_variations(
            {
                "boto3manifest": "storages.backends.s3.S3ManifestStaticStorage",
            },
            {
                "base": "collectfasta.strategies.boto3.Boto3Strategy",
                "memory_2pass": "collectfasta.strategies.boto3.Boto3ManifestMemoryStrategy",  # noqa E501
                "file_2pass": "collectfasta.strategies.boto3.Boto3ManifestFileSystemStrategy",  # noqa E501
            },
        )
    ),
}


gcloud_backend_confs = {
    "gcloud": override_django_settings(
        STORAGES={
            "staticfiles": {
                "BACKEND": "collectfasta.tests.utils.GoogleCloudStorageTest",
            },
        },
        COLLECTFASTA_STRATEGY="collectfasta.strategies.gcloud.GoogleCloudStrategy",
    ),
}
filesystem_backend_confs = {
    "filesystem": override_django_settings(
        STORAGES={
            "staticfiles": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
        },
        COLLECTFASTA_STRATEGY="collectfasta.strategies.filesystem.FileSystemStrategy",
    ),
    "cachingfilesystem": override_django_settings(
        STORAGES={
            "staticfiles": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
        },
        COLLECTFASTA_STRATEGY=(
            "collectfasta.strategies.filesystem.CachingFileSystemStrategy"
        ),
    ),
}
all_backend_confs = {
    **aws_backend_confs,
    **gcloud_backend_confs,
    **filesystem_backend_confs,
}

make_test_aws_backends: Callable = many(**aws_backend_confs)
make_test_all_backends: Callable = many(**all_backend_confs)
make_test_cloud_backends: Callable = many(**aws_backend_confs, **gcloud_backend_confs)


@make_test_all_backends
@live_test
def test_basics(case: TestCase) -> None:
    clean_static_dir()
    create_two_referenced_static_files()
    assert_static_file_number(2, call_collectstatic(), case)
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_all_backends
@live_test
def test_only_copies_new(case: TestCase) -> None:
    clean_static_dir()
    create_two_referenced_static_files()
    assert_static_file_number(2, call_collectstatic(), case)
    create_two_referenced_static_files()
    assert_static_file_number(2, call_collectstatic(), case)


@make_test_all_backends
@live_test
@override_setting("threads", 5)
def test_threads(case: TestCase) -> None:
    clean_static_dir()
    create_two_referenced_static_files()
    assert_static_file_number(2, call_collectstatic(), case)
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_cloud_backends
@live_test
@speed_test
def test_basics_cloud_speed(case: TestCase) -> None:
    clean_static_dir()
    make_100_files()
    assert_static_file_number(100, call_collectstatic(), case)

    def collectstatic_one():
        assert_static_file_number(2, call_collectstatic(), case)

    create_two_referenced_static_files()
    ittook = timeit.timeit(collectstatic_one, number=1)
    print(f"it took {ittook} seconds")


@make_test_cloud_backends
@live_test
@speed_test
@override_settings(
    INSTALLED_APPS=["django.contrib.staticfiles"], COLLECTFASTA_STRATEGY=None
)
def test_no_collectfasta_cloud_speed(case: TestCase) -> None:
    clean_static_dir()
    make_100_files()

    case.assertIn("100 static files copied", call_collectstatic())

    def collectstatic_one():
        case.assertIn("2 static files copied", call_collectstatic())

    create_two_referenced_static_files()
    ittook = timeit.timeit(collectstatic_one, number=1)
    print(f"it took {ittook} seconds")


@make_test
def test_dry_run(case: TestCase) -> None:
    clean_static_dir()
    create_static_file()
    result = call_collectstatic(dry_run=True)
    case.assertIn("1 static file copied.", result)
    case.assertTrue("Pretending to copy", result)
    result = call_collectstatic(dry_run=True)
    case.assertIn("1 static file copied.", result)
    case.assertTrue("Pretending to copy", result)
    case.assertTrue("Pretending to delete", result)


@make_test_aws_backends
@live_test
@override_storage_attr("gzip", True)
@override_setting("aws_is_gzipped", True)
def test_aws_is_gzipped(case: TestCase) -> None:
    clean_static_dir()
    create_two_referenced_static_files()
    assert_static_file_number(2, call_collectstatic(), case)

    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test
@override_django_settings(STORAGES={}, COLLECTFASTA_STRATEGY=None)
def test_raises_for_no_configured_strategy(case: TestCase) -> None:
    with case.assertRaises(ImproperlyConfigured):
        Command._load_strategy()


@make_test_all_backends
@live_test
@mock.patch("collectfasta.strategies.base.Strategy.post_copy_hook", autospec=True)
def test_calls_post_copy_hook(_case: TestCase, post_copy_hook: mock.MagicMock) -> None:
    clean_static_dir()
    (path_one, path_two) = create_two_referenced_static_files()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    post_copy_hook.assert_has_calls(
        [
            mock.call(mock.ANY, path_one.name, path_one.name, mock.ANY),
            mock.call(mock.ANY, path_two.name, path_two.name, mock.ANY),
        ],
        any_order=True,
    )


@make_test_all_backends
@live_test
@mock.patch("collectfasta.strategies.base.Strategy.on_skip_hook", autospec=True)
def test_calls_on_skip_hook(_case: TestCase, on_skip_hook: mock.MagicMock) -> None:
    clean_static_dir()
    (path_one, path_two) = create_two_referenced_static_files()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_not_called()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])

    on_skip_hook.assert_has_calls(
        [
            mock.call(mock.ANY, path_one.name, path_one.name, mock.ANY),
            mock.call(mock.ANY, path_two.name, path_two.name, mock.ANY),
        ],
        any_order=True,
    )
