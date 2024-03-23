from django.test import override_settings as override_django_settings
from pytest_mock import MockerFixture

from collectfasta.tests.conftest import StrategyFixture
from collectfasta.tests.conftest import live_test
from collectfasta.tests.utils import clean_static_dir
from collectfasta.tests.utils import create_static_file
from collectfasta.tests.utils import override_setting

from .utils import call_collectstatic


@override_django_settings(
    STORAGES={
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    },
)
def test_disable_collectfasta_with_default_storage() -> None:
    clean_static_dir()
    create_static_file()
    assert "1 static file copied" in call_collectstatic(disable_collectfasta=True)


@live_test
def test_disable_collectfasta(strategy: StrategyFixture) -> None:
    clean_static_dir()
    create_static_file()
    assert "1 static file copied" in call_collectstatic(disable_collectfasta=True)


@override_setting("enabled", False)
def test_no_load_with_disable_setting(mocker: MockerFixture) -> None:
    mocked_load_strategy = mocker.patch(
        "collectfasta.management.commands.collectstatic.Command._load_strategy"
    )
    clean_static_dir()
    call_collectstatic()
    mocked_load_strategy.assert_not_called()


def test_no_load_with_disable_flag(mocker: MockerFixture) -> None:
    mocked_load_strategy = mocker.patch(
        "collectfasta.management.commands.collectstatic.Command._load_strategy"
    )
    clean_static_dir()
    call_collectstatic(disable_collectfasta=True)
    mocked_load_strategy.assert_not_called()
