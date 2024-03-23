import string

from django.core.files.storage import FileSystemStorage
from pytest_mock import MockerFixture

from collectfasta import settings
from collectfasta.strategies.base import CachingHashStrategy

hash_characters = string.ascii_letters + string.digits


class Strategy(CachingHashStrategy[FileSystemStorage]):
    def __init__(self) -> None:
        super().__init__(FileSystemStorage())

    def get_remote_file_hash(self, prefixed_path: str) -> None:
        pass


def test_get_cache_key() -> None:
    strategy = Strategy()
    cache_key = strategy.get_cache_key("/some/random/path")
    prefix_len = len(settings.cache_key_prefix)
    # case.assertTrue(cache_key.startswith(settings.cache_key_prefix))
    assert cache_key.startswith(settings.cache_key_prefix)
    assert len(cache_key) == 32 + prefix_len
    expected_chars = hash_characters + "_"
    for c in cache_key:
        assert c in expected_chars


def test_gets_and_invalidates_hash(mocker: MockerFixture) -> None:
    strategy = Strategy()
    expected_hash = "hash"
    mocked = mocker.patch.object(
        strategy,
        "get_remote_file_hash",
        new=mocker.MagicMock(return_value=expected_hash),
    )
    # empty cache
    result_hash = strategy.get_cached_remote_file_hash("path", "prefixed_path")
    assert result_hash == expected_hash
    mocked.assert_called_once_with("prefixed_path")

    # populated cache
    mocked.reset_mock()
    result_hash = strategy.get_cached_remote_file_hash("path", "prefixed_path")
    assert result_hash == expected_hash
    mocked.assert_not_called()

    # test destroy_etag
    mocked.reset_mock()
    strategy.invalidate_cached_hash("path")
    result_hash = strategy.get_cached_remote_file_hash("path", "prefixed_path")
    assert result_hash == expected_hash
    mocked.assert_called_once_with("prefixed_path")


def test_post_copy_hook_primes_cache(mocker: MockerFixture) -> None:
    filename = "123abc"
    expected_hash = "abc123"
    strategy = Strategy()

    mocker.patch.object(
        strategy, "get_local_file_hash", return_value=expected_hash, autospec=True
    )
    strategy.post_copy_hook(filename, filename, strategy.remote_storage)

    assert strategy.get_cached_remote_file_hash(filename, filename) == expected_hash
