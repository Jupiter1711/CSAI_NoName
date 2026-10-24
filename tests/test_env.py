import importlib
import sys

import pytest


@pytest.mark.parametrize("name", ["black", "flake8", "pytest_cov", "bloxorz"])
def test_module_importable(name):
    assert importlib.import_module(name) is not None


def test_python_version():
    assert sys.version_info[:2] == (3, 11)
