from unittest.mock import MagicMock, patch

import pytest


class _SimpleMocker:
    def __init__(self):
        self._patchers = []
        self.MagicMock = MagicMock

    def patch(self, target, *args, **kwargs):
        patcher = patch(target, *args, **kwargs)
        mocked = patcher.start()
        self._patchers.append(patcher)
        return mocked

    def stopall(self):
        while self._patchers:
            self._patchers.pop().stop()


@pytest.fixture
def mocker():
    helper = _SimpleMocker()
    try:
        yield helper
    finally:
        helper.stopall()
