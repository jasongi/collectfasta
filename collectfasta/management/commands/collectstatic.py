from concurrent.futures import ThreadPoolExecutor
from typing import Any
from typing import Dict
from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type

from django.conf import settings as django_settings
from django.contrib.staticfiles.management.commands import collectstatic
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import Storage
from django.core.management.base import CommandParser

from collectfasta import __version__
from collectfasta import settings
from collectfasta.strategies import DisabledStrategy
from collectfasta.strategies import Strategy
from collectfasta.strategies import load_strategy

Task = Tuple[str, str, Storage]


def collect_from_folder(
    storage: Storage, path: str = ""
) -> Generator[tuple[str, str], str, None]:
    folders, files = storage.listdir(path)
    for thefile in files:
        if path:
            prefixed = f"{path}/{thefile}"
        else:
            prefixed = thefile
        yield prefixed, prefixed
    for folder in folders:
        if path:
            folder = f"{path}/{folder}"
        yield from collect_from_folder(storage, folder)


class Command(collectstatic.Command):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.num_copied_files = 0
        self.tasks: List[Task] = []
        self.collectfasta_enabled = settings.enabled
        self.strategy: Strategy = DisabledStrategy(Storage())
        self.found_files: Dict[str, Tuple[Storage, str]] = {}

    @staticmethod
    def _load_strategy() -> Type[Strategy[Storage]]:
        strategy_str = getattr(django_settings, "COLLECTFASTA_STRATEGY", None)
        if strategy_str is not None:
            return load_strategy(strategy_str)

        raise ImproperlyConfigured(
            "No strategy configured, please make sure COLLECTFASTA_STRATEGY is set."
        )

    def get_version(self) -> str:
        return __version__

    def add_arguments(self, parser: CommandParser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "--disable-collectfasta",
            action="store_true",
            dest="disable_collectfasta",
            default=False,
            help="Disable Collectfasta.",
        )

    def set_options(self, **options: Any) -> None:
        self.collectfasta_enabled = self.collectfasta_enabled and not options.pop(
            "disable_collectfasta"
        )
        if self.collectfasta_enabled:
            self.strategy = self._load_strategy()(self.storage)
            self.storage = self.strategy.wrap_storage(self.storage)
        super().set_options(**options)

    def second_pass(self, stats: Dict[str, List[str]]) -> Dict[str, List[str]]:
        second_pass_strategy = self.strategy.second_pass_strategy()
        if self.collectfasta_enabled and second_pass_strategy:
            self.copied_files = []
            self.symlinked_files = []
            self.unmodified_files = []
            self.deleted_files: list[str] = []
            self.skipped_files: list[str] = []
            self.num_copied_files = 0
            source_storage = self.storage
            self.storage = second_pass_strategy.wrap_storage(self.storage)
            self.strategy = second_pass_strategy
            self.log(f"Running second pass with {self.strategy.__class__.__name__}...")
            if settings.threads and settings.threads > 1:
                tasks = [
                    (f, prefixed, source_storage)
                    for f, prefixed in collect_from_folder(source_storage)
                ]
                with ThreadPoolExecutor(settings.threads) as pool:
                    pool.map(self.maybe_copy_file, tasks)
            else:
                for f, prefixed in collect_from_folder(source_storage):
                    self.maybe_copy_file((f, prefixed, source_storage))
            return {
                "modified": self.copied_files + self.symlinked_files,
                "unmodified": self.unmodified_files,
                "post_processed": self.post_processed_files,
                "deleted": self.deleted_files,
                "skipped": self.skipped_files,
            }

        return stats

    def _check_cache_size(self, num_files: int) -> None:
        """
        Check if the number of static files exceeds the cache MAX_ENTRIES setting
        and print a warning if so.
        """
        if not self.collectfasta_enabled:
            return

        try:
            cache_settings = getattr(django_settings, "CACHES", {}).get(
                settings.cache, {}
            )
            max_entries = cache_settings.get("OPTIONS", {}).get("MAX_ENTRIES", 300)

            if max_entries is not None and num_files > max_entries:
                self.log(
                    f"Warning: You have {num_files} static files, but your cache "
                    f"MAX_ENTRIES is set to {max_entries}. This will make collectstatic slow. "
                    f"To fix, set MAX_ENTRIES to {num_files} or higher. ",
                    level=1,
                )
        except Exception:
            # Don't fail collection if we can't check cache settings
            pass

    def collect(self) -> Dict[str, List[str]]:
        """
        Override collect to copy files concurrently. The tasks are populated by
        Command.copy_file() which is called by super().collect().
        """
        if not self.collectfasta_enabled or not settings.threads:
            result = super().collect()
            # For non-threaded mode, check the number of found files
            second_pass_result = self.second_pass(result)
            self._check_cache_size(len(self.found_files))
            return second_pass_result

        # Store original value of post_process in super_post_process and always
        # set the value to False to prevent the default behavior from
        # interfering when using threads. See maybe_post_process().
        super_post_process = self.post_process
        self.post_process = False

        return_value = super().collect()

        # Check if the number of files exceeds cache MAX_ENTRIES
        self._check_cache_size(len(self.tasks))

        with ThreadPoolExecutor(settings.threads) as pool:
            pool.map(self.maybe_copy_file, self.tasks)

        self.maybe_post_process(super_post_process)
        return_value["post_processed"] = self.post_processed_files
        second_pass_result = self.second_pass(return_value)
        self._check_cache_size(len(self.found_files))

        return second_pass_result

    def handle(self, *args: Any, **options: Any) -> Optional[str]:
        """Override handle to suppress summary output."""
        ret = super().handle(**options)
        if not self.collectfasta_enabled:
            return ret
        plural = "" if self.num_copied_files == 1 else "s"
        return f"{self.num_copied_files} static file{plural} copied."

    def maybe_copy_file(self, args: Task) -> None:
        """Determine if file should be copied or not and handle exceptions."""
        path, prefixed_path, source_storage = self.strategy.copy_args_hook(args)
        # Build up found_files to look identical to how it's created in the
        # builtin command's collect() method so that we can run post_process
        # after all parallel uploads finish.
        self.found_files[prefixed_path] = (source_storage, path)

        if self.collectfasta_enabled and not self.dry_run:
            self.strategy.pre_should_copy_hook()

            if not self.strategy.should_copy_file(path, prefixed_path, source_storage):
                self.log(f"Skipping '{path}'")
                self.strategy.on_skip_hook(path, prefixed_path, source_storage)
                return

        self.num_copied_files += 1

        existed = prefixed_path in self.copied_files
        super().copy_file(path, prefixed_path, source_storage)
        copied = not existed and prefixed_path in self.copied_files
        if copied:
            self.strategy.post_copy_hook(path, prefixed_path, source_storage)
        else:
            self.strategy.on_skip_hook(path, prefixed_path, source_storage)

    def copy_file(self, path: str, prefixed_path: str, source_storage: Storage) -> None:
        """
        Append path to task queue if threads are enabled, otherwise copy the
        file with a blocking call.
        """
        args = (path, prefixed_path, source_storage)
        if settings.threads and self.collectfasta_enabled:
            self.tasks.append(args)
        else:
            self.maybe_copy_file(args)

    def delete_file(
        self, path: str, prefixed_path: str, source_storage: Storage
    ) -> bool:
        """Override delete_file to skip modified time and exists lookups."""
        if not self.collectfasta_enabled:
            return super().delete_file(path, prefixed_path, source_storage)

        if self.dry_run:
            self.log(f"Pretending to delete '{path}'")
            return True

        self.log(f"Deleting '{path}' on remote storage")

        try:
            self.storage.delete(prefixed_path)
        except self.strategy.delete_not_found_exception:
            pass

        return True

    def maybe_post_process(self, super_post_process: bool) -> None:
        # This method is extracted and modified from the collect() method of the
        # builtin collectstatic command.
        # https://github.com/django/django/blob/5320ba98f3d253afcaa76b4b388a8982f87d4f1a/django/contrib/staticfiles/management/commands/collectstatic.py#L124

        if not super_post_process or not hasattr(self.storage, "post_process"):
            return

        processor = self.storage.post_process(self.found_files, dry_run=self.dry_run)

        for original_path, processed_path, processed in processor:
            if isinstance(processed, Exception):
                self.stderr.write("Post-processing '%s' failed!" % original_path)
                # Add a blank line before the traceback, otherwise it's
                # too easy to miss the relevant part of the error message.
                self.stderr.write("")
                raise processed
            if processed:
                self.log(
                    f"Post-processed '{original_path}' as '{processed_path}'",
                    level=2,
                )
                self.post_processed_files.append(original_path)
            else:
                self.log("Skipped post-processing '%s'" % original_path)
