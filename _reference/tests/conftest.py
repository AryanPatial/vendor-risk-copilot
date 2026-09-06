import pytest


def pytest_addoption(parser):
    parser.addoption("--run-db", action="store_true", help="run tests that need Postgres")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-db"):
        return
    skip = pytest.mark.skip(reason="needs Postgres; pass --run-db")
    for item in items:
        if "needs_db" in item.keywords:
            item.add_marker(skip)
