"""긴 본문을 문장 단위로 나누는 분리기.

분리기는 ``(text, start, end) -> [(s, e), ...]`` 형태로, ``text[start:end]`` 구간을 원문 위치
그대로 문장 구간 목록으로 돌려줍니다.
"""

from __future__ import annotations

import re
from collections.abc import Callable

SentenceSplitter = Callable[[str, int, int], list[tuple[int, int]]]

_SENT_END = re.compile(r"[.!?…]+[\"'”’)\]」』]*(?=\s)|\n")


def regex_splitter(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """마침표·물음표·느낌표 뒤 공백, 또는 줄바꿈에서 나눕니다. 의존성이 없습니다."""
    spans: list[tuple[int, int]] = []
    cur = start
    for m in _SENT_END.finditer(text, start, end):
        if text[cur : m.end()].strip():
            spans.append((cur, m.end()))
            cur = m.end()
    if text[cur:end].strip():
        spans.append((cur, end))
    return spans


def kiwi_splitter() -> SentenceSplitter:
    """Kiwi 형태소 분석기로 문장을 나눕니다. ``pip install jogak[kiwi]`` 가 필요합니다."""
    try:
        from kiwipiepy import Kiwi
    except ImportError as e:  # pragma: no cover - 설치 여부에 따라 다름
        raise ImportError("kiwi splitter needs kiwipiepy: pip install 'jogak[kiwi]'") from e
    kiwi = Kiwi()

    def split(text: str, start: int, end: int) -> list[tuple[int, int]]:
        return [(start + s.start, start + s.end) for s in kiwi.split_into_sents(text[start:end])]

    return split


def resolve_splitter(spec: str | SentenceSplitter) -> SentenceSplitter:
    if callable(spec):
        return spec
    if spec == "regex":
        return regex_splitter
    if spec == "kiwi":
        return kiwi_splitter()
    raise ValueError(f"unknown sentence splitter: {spec!r} (use 'regex', 'kiwi' or a callable)")
