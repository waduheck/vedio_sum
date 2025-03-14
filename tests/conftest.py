#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pytest配置文件
"""
import pytest
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture 