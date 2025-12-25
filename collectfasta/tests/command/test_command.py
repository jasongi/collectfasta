import timeit

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings as override_django_settings
from django.test.utils import override_settings
from pytest_mock import MockerFixture

from collectfasta.management.commands.collectstatic import Command
from collectfasta.tests.conftest import StrategyFixture
from collectfasta.tests.conftest import aws_backends_only
from collectfasta.tests.conftest import azure_backends_only
from collectfasta.tests.conftest import cloud_backends_only
from collectfasta.tests.conftest import exclude_two_pass
from collectfasta.tests.conftest import live_test
from collectfasta.tests.conftest import speed_test
from collectfasta.tests.conftest import two_pass_only
from collectfasta.tests.utils import clean_static_dir
from collectfasta.tests.utils import create_larger_than_4mb_referenced_static_file
from collectfasta.tests.utils import create_static_file
from collectfasta.tests.utils import create_two_referenced_static_files
from collectfasta.tests.utils import make_100_files
from collectfasta.tests.utils import override_setting
from collectfasta.tests.utils import override_storage_attr

from .utils import call_collectstatic


@live_test
def test_basics(strategy: StrategyFixture) -> None:
    clean_static_dir()
    create_two_referenced_static_files()
    assert (
        f"{strategy.expected_copied_files(2)} static files copied."
        in call_collectstatic()
    )
    # file state should now be cached
    assert "0 static files copied." in call_collectstatic()


@live_test
def test_only_copies_new(strategy: StrategyFixture) -> None:
    clean_static_dir()
    create_two_referenced_static_files()
    assert (
        f"{strategy.expected_copied_files(2)} static files copied."
        in call_collectstatic()
    )
    create_two_referenced_static_files()
    # Since the files were already created and are expected to be cached/not copied again,
    # we expect 0 new files to be copied.
    assert (
        f"{strategy.expected_copied_files(2)} static files copied."
        in call_collectstatic()
    )


@live_test
@override_setting("threads", 5)
def test_threads(strategy: StrategyFixture) -> None:
    clean_static_dir()
    create_two_referenced_static_files()
    assert (
        f"{strategy.expected_copied_files(2)} static files copied."
        in call_collectstatic()
    )
    # file state should now be cached
    assert "0 static files copied." in call_collectstatic()


@cloud_backends_only
@speed_test
def test_basics_cloud_speed(strategy: StrategyFixture) -> None:
    clean_static_dir()
    make_100_files()
    assert (
        f"{strategy.expected_copied_files(100)} static files copied."
        in call_collectstatic()
    )

    def collectstatic_one():
        assert (
            f"{strategy.expected_copied_files(2)} static files copied."
            in call_collectstatic()
        )

    create_two_referenced_static_files()
    ittook = timeit.timeit(collectstatic_one, number=1)
    print(f"it took {ittook} seconds")


@cloud_backends_only
@speed_test
@override_settings(
    INSTALLED_APPS=["django.contrib.staticfiles"], COLLECTFASTA_STRATEGY=None
)
def test_no_collectfasta_cloud_speed(strategy: StrategyFixture) -> None:
    clean_static_dir()
    make_100_files()
    assert "100 static files copied" in call_collectstatic()

    def collectstatic_one():
        assert "2 static files copied" in call_collectstatic()

    create_two_referenced_static_files()
    ittook = timeit.timeit(collectstatic_one, number=1)
    print(f"it took {ittook} seconds")


@exclude_two_pass
def test_dry_run(strategy: StrategyFixture) -> None:
    clean_static_dir()
    create_static_file()
    result = call_collectstatic(dry_run=True)
    assert "1 static file copied." in result
    assert "Pretending to copy" in result
    result = call_collectstatic(dry_run=True)
    assert "1 static file copied." in result
    assert "Pretending to copy" in result
    assert "Pretending to delete" in result


@two_pass_only
def test_dry_run_two_pass(strategy: StrategyFixture) -> None:
    clean_static_dir()
    create_static_file()
    result = call_collectstatic(dry_run=True)
    assert "0 static files copied." in result
    assert "Pretending to copy" in result
    result = call_collectstatic(dry_run=True)
    assert "0 static files copied." in result
    assert "Pretending to copy" in result
    assert "Pretending to delete" in result


@aws_backends_only
@live_test
@override_storage_attr("gzip", True)
@override_setting("aws_is_gzipped", True)
def test_aws_is_gzipped(strategy: StrategyFixture) -> None:
    clean_static_dir()
    create_two_referenced_static_files()
    assert (
        f"{strategy.expected_copied_files(2)} static files copied."
        in call_collectstatic()
    )

    # file state should now be cached
    assert "0 static files copied." in call_collectstatic()


@override_django_settings(STORAGES={}, COLLECTFASTA_STRATEGY=None)
def test_raises_for_no_configured_strategy() -> None:
    with pytest.raises(ImproperlyConfigured):
        Command._load_strategy()


@live_test
def test_calls_post_copy_hook(strategy: StrategyFixture, mocker: MockerFixture) -> None:
    post_copy_hook = mocker.patch(
        "collectfasta.strategies.base.Strategy.post_copy_hook", autospec=True
    )
    clean_static_dir()
    (path_one, path_two) = create_two_referenced_static_files()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    post_copy_hook.assert_has_calls(
        [
            mocker.call(mocker.ANY, path_one.name, path_one.name, mocker.ANY),
            mocker.call(
                mocker.ANY,
                f"{path_one.name.replace('.html','')}_folder/{path_two.name}",
                f"{path_one.name.replace('.html','')}_folder/{path_two.name}",
                mocker.ANY,
            ),
        ],
        any_order=True,
    )


@live_test
def test_calls_on_skip_hook(strategy: StrategyFixture, mocker: MockerFixture) -> None:
    on_skip_hook = mocker.patch(
        "collectfasta.strategies.base.Strategy.on_skip_hook", autospec=True
    )
    clean_static_dir()
    (path_one, path_two) = create_two_referenced_static_files()
    cmd = Command()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_not_called()
    cmd.run_from_argv(["manage.py", "collectstatic", "--noinput"])
    on_skip_hook.assert_has_calls(
        [
            mocker.call(mocker.ANY, path_one.name, path_one.name, mocker.ANY),
            mocker.call(
                mocker.ANY,
                f"{path_one.name.replace('.html','')}_folder/{path_two.name}",
                f"{path_one.name.replace('.html','')}_folder/{path_two.name}",
                mocker.ANY,
            ),
        ],
        any_order=True,
    )


@azure_backends_only
@live_test
def test_azure_large_file_hashing(
    strategy: StrategyFixture, mocker: MockerFixture
) -> None:
    from collectfasta.strategies.azure import AzureBlobStrategy

    create_composite_hash_spy = mocker.spy(AzureBlobStrategy, "_create_composite_hash")

    clean_static_dir()
    create_two_referenced_static_files()
    assert (
        f"{strategy.expected_copied_files(2)} static files copied."
        in call_collectstatic()
    )
    # files are < 4mb no composite hash should be created
    assert create_composite_hash_spy.call_count == 0

    create_larger_than_4mb_referenced_static_file()
    # the small files should be cached now
    assert (
        f"{strategy.expected_copied_files(2)} static files copied."
        in call_collectstatic()
    )
    # one file is > 4mb a composite hash should be created
    assert create_composite_hash_spy.call_count == 1
    # file state should now be cached
    assert "0 static files copied." in call_collectstatic()
    # again the the > 4mb file triggers a hash creation
    assert create_composite_hash_spy.call_count == 2


def test_check_cache_size_warning_when_exceeds_max_entries(
    mocker: MockerFixture,
) -> None:
    """Test that a warning is logged when number of files exceeds MAX_ENTRIES."""
    cmd = Command()
    cmd.collectfasta_enabled = True
    mock_log = mocker.patch.object(cmd, "log")

    # Test with MAX_ENTRIES set and exceeded
    with override_django_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "OPTIONS": {"MAX_ENTRIES": 10},
            }
        }
    ):
        cmd._check_cache_size(20)
        mock_log.assert_called_once()
        call_args = mock_log.call_args[0][0]
        assert "Warning: You have 20 static files" in call_args
        assert "MAX_ENTRIES is set to 10" in call_args
        assert "set MAX_ENTRIES to 20 or higher" in call_args


def test_check_cache_size_no_warning_when_under_max_entries(
    mocker: MockerFixture,
) -> None:
    """Test that no warning is logged when number of files is under MAX_ENTRIES."""
    cmd = Command()
    cmd.collectfasta_enabled = True
    mock_log = mocker.patch.object(cmd, "log")

    # Test with MAX_ENTRIES set but not exceeded
    with override_django_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "OPTIONS": {"MAX_ENTRIES": 100},
            }
        }
    ):
        cmd._check_cache_size(50)
        mock_log.assert_not_called()


def test_check_cache_size_warning_when_max_entries_default(
    mocker: MockerFixture,
) -> None:
    """Test that a warning is logged when MAX_ENTRIES uses default value of 300."""
    cmd = Command()
    cmd.collectfasta_enabled = True
    mock_log = mocker.patch.object(cmd, "log")

    # Test with no MAX_ENTRIES set (should use default of 300)
    with override_django_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    ):
        cmd._check_cache_size(500)
        mock_log.assert_called_once()
        call_args = mock_log.call_args[0][0]
        assert "Warning: You have 500 static files" in call_args
        assert "MAX_ENTRIES is set to 300" in call_args


def test_check_cache_size_no_warning_when_collectfasta_disabled(
    mocker: MockerFixture,
) -> None:
    """Test that no warning is logged when collectfasta is disabled."""
    cmd = Command()
    cmd.collectfasta_enabled = False
    mock_log = mocker.patch.object(cmd, "log")

    with override_django_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "OPTIONS": {"MAX_ENTRIES": 10},
            }
        }
    ):
        cmd._check_cache_size(100)
        mock_log.assert_not_called()
