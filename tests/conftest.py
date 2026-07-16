"""프로젝트 공용 pytest 설정."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"
