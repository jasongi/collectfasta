def pytest_addoption(parser):
    parser.addoption(
        "--speedtest",
        action="store_true",
        dest="speedtest",
        default=False,
        help="run the test on many files (not for live environments",
    )
