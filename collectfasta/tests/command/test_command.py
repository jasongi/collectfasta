import timeit
from unittest import TestCase
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings as override_django_settings
from django.test.utils import override_settings

from collectfasta.management.commands.collectstatic import Command
from collectfasta.tests.utils import clean_static_dir
from collectfasta.tests.utils import create_static_file
from collectfasta.tests.utils import live_test
from collectfasta.tests.utils import make_100_files
from collectfasta.tests.utils import make_test
from collectfasta.tests.utils import many
from collectfasta.tests.utils import override_setting
from collectfasta.tests.utils import override_storage_attr
from collectfasta.tests.utils import speed_test

from .utils import call_collectstatic

aws_backend_confs = {
    "boto3": override_django_settings(
        STORAGES={
            "staticfiles": {
                "BACKEND": "storages.backends.s3.S3Storage",
            },
        },
        COLLECTFASTA_STRATEGY="collectfasta.strategies.boto3.Boto3Strategy",
    ),
    "boto3manifest": override_django_settings(
        STORAGES={
            "staticfiles": {
                "BACKEND": "storages.backends.s3.S3ManifestStaticStorage",
            },
        },
        COLLECTFASTA_STRATEGY="collectfasta.strategies.boto3.Boto3Strategy",
    ),
    "boto3static": override_django_settings(
        STORAGES={
            "staticfiles": {
                "BACKEND": "storages.backends.s3.S3StaticStorage",
            },
        },
        COLLECTFASTA_STRATEGY="collectfasta.strategies.boto3.Boto3Strategy",
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

make_test_aws_backends = many(**aws_backend_confs)
make_test_all_backends = many(**all_backend_confs)
make_test_cloud_backends = many(**aws_backend_confs, **gcloud_backend_confs)


@make_test_all_backends
@live_test
def test_basics(case: TestCase) -> None:
    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_all_backends
@live_test
@override_setting("threads", 5)
def test_threads(case: TestCase) -> None:
    clean_static_dir()
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
    # file state should now be cached
    case.assertIn("0 static files copied.", call_collectstatic())


@make_test_cloud_backends
@live_test
@speed_test
def test_basics_cloud_speed(case: TestCase) -> None:
    clean_static_dir()
    make_100_files()

    case.assertIn("100 static files copied", call_collectstatic())

    def collectstatic_one():
        case.assertIn("1 static file copied", call_collectstatic())

    create_static_file()
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
        case.assertIn("1 static file copied", call_collectstatic())

    create_static_file()
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
    create_static_file()
    case.assertIn("1 static file copied.", call_collectstatic())
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
    path = create_static_file()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    post_copy_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)


@make_test_all_backends
@live_test
@mock.patch("collectfasta.strategies.base.Strategy.on_skip_hook", autospec=True)
def test_calls_on_skip_hook(_case: TestCase, on_skip_hook: mock.MagicMock) -> None:
    clean_static_dir()
    path = create_static_file()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_not_called()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_called_once_with(mock.ANY, path.name, path.name, mock.ANY)
