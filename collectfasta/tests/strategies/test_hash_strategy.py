import re
import tempfile

from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.files.storage import FileSystemStorage
from pytest_mock import MockerFixture

from collectfasta.strategies.base import HashStrategy


class Strategy(HashStrategy[FileSystemStorage]):
    def __init__(self) -> None:
        super().__init__(FileSystemStorage())

    def get_remote_file_hash(self, prefixed_path: str) -> None:
        pass


def test_get_file_hash() -> None:
    strategy = Strategy()
    local_storage = StaticFilesStorage()

    with tempfile.NamedTemporaryFile(dir=local_storage.base_location) as f:
        f.write(b"spam")
        hash_ = strategy.get_local_file_hash(f.name, local_storage)
    assert re.fullmatch(r"^[A-z0-9]{32}$", hash_) is not None


def test_should_copy_file(mocker: MockerFixture) -> None:
    strategy = Strategy()
    local_storage = StaticFilesStorage()
    remote_hash = "foo"
    mocker.patch.object(
        strategy, "get_remote_file_hash", mocker.MagicMock(return_value=remote_hash)
    )
    mocker.patch.object(
        strategy, "get_local_file_hash", mocker.MagicMock(return_value=remote_hash)
    )
    assert not strategy.should_copy_file("path", "prefixed_path", local_storage)
    mocker.patch.object(
        strategy, "get_local_file_hash", mocker.MagicMock(return_value="bar")
    )
    assert strategy.should_copy_file("path", "prefixed_path", local_storage)
