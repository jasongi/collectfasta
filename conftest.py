import os
import shutil

import pytest
from django.conf import settings


def pytest_addoption(parser):
    parser.addoption(
        "--speedtest",
        action="store_true",
        dest="speedtest",
        default=False,
        help="run the test on many files (not for live environments",
    )


@pytest.fixture(autouse=True)
def create_test_directories():
    paths = (settings.STATICFILES_DIRS[0], settings.STATIC_ROOT, settings.MEDIA_ROOT)
    for path in paths:
        if not os.path.exists(path):
            os.makedirs(path)
    try:
        yield
    finally:
        for path in paths:
            shutil.rmtree(path)
