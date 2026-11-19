from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def law() -> str:
    return (FIXTURES / "law.txt").read_text(encoding="utf-8")


@pytest.fixture
def gongmun() -> str:
    return (FIXTURES / "gongmun.txt").read_text(encoding="utf-8")
