"""텍스트를 장·조·항·호·목 같은 계층 트리로 파싱합니다."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .markers import Marker, is_page_number, match_heading, match_item

# 쪽마다 되풀이되는 머리글·꼬리글로 볼 기준: 마커가 없는 짧은 줄이 이만큼 이상 똑같이 나옴
_RUNNING_HEADER_MIN_REPEATS = 3
_RUNNING_HEADER_MAX_CHARS = 40


@dataclass(eq=False)
class Node:
    """문서 구조의 한 노드.

    ``source[start:end]`` 가 이 노드와 모든 하위 노드의 원문입니다.
    ``source[start:own_end]`` 는 첫 하위 노드 전까지의 자기 본문(제목 줄 포함)입니다.
    """

    kind: str  # "document" | "heading" | "item"
    type: str
    label: str
    start: int
    body_start: int  # 마커 다음, 본문이 시작하는 위치
    rank: int = 0
    ordinal: int | None = None
    content_end: int = 0  # 자기 본문 마지막 줄의 끝
    children: list[Node] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)

    @property
    def end(self) -> int:
        return self.children[-1].end if self.children else self.content_end

    @property
    def own_end(self) -> int:
        return self.children[0].start if self.children else self.content_end

    def walk(self) -> Iterator[Node]:
        """자기 자신과 모든 하위 노드를 문서 순서로 돌려줍니다."""
        yield self
        for child in self.children:
            yield from child.walk()

    def to_dict(self, source: str | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {
            "kind": self.kind,
            "type": self.type,
            "label": self.label,
            "start": self.start,
            "end": self.end,
        }
        if source is not None:
            d["own_text"] = source[self.start : self.own_end].strip()
        if self.children:
            d["children"] = [c.to_dict(source) for c in self.children]
        return d


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.root = Node("document", "document", "", 0, 0)
        self.stack: list[Node] = [self.root]
        self.last_article = 0

    def parse(self) -> Node:
        lines = self.text.splitlines(keepends=True)
        noise = _running_headers(lines)
        pos = 0
        for raw in lines:
            line_start = pos
            pos += len(raw)
            content = raw.rstrip("\r\n")
            stripped = content.lstrip()
            # 쪽 번호와 머리글은 구조로 보지 않고, 노드 본문의 끝을 늘리지도 않습니다.
            # (청크는 원문 구간이므로, 노드 사이에 끼어 있으면 청크 안에는 남을 수 있습니다.)
            if not stripped or is_page_number(stripped.rstrip()) or stripped.rstrip() in noise:
                continue
            offset = line_start + len(content) - len(stripped)
            line_end = line_start + len(content)
            self._line(stripped, offset, line_end)
        return self.root

    def _line(self, s: str, offset: int, line_end: int) -> None:
        heading = match_heading(s, self.last_article)
        if heading is not None:
            node = self._push_heading(heading, offset)
            node.content_end = line_end
            rest = s[heading.end :]
            body = rest.lstrip()
            if body:
                body_offset = offset + heading.end + len(rest) - len(body)
                node.body_start = body_offset
                # "제3조(적용 범위) ① 이 법은 ..." 처럼 같은 줄에서 항이 시작하는 경우
                self._item_or_text(body, body_offset, line_end, allow_text=False)
            return
        self._item_or_text(s, offset, line_end, allow_text=True)

    def _push_heading(self, m: Marker, offset: int) -> Node:
        while len(self.stack) > 1 and (
            self.stack[-1].kind == "item" or self.stack[-1].rank >= m.rank
        ):
            self.stack.pop()
        if m.type in ("addenda", "appendix"):
            self.last_article = 0
        elif m.type == "article" and m.ordinal is not None:
            self.last_article = m.ordinal
        node = Node(
            "heading", m.type, m.label, offset, offset + m.end, rank=m.rank, ordinal=m.ordinal
        )
        self._attach(node)
        return node

    def _item_or_text(self, s: str, offset: int, line_end: int, *, allow_text: bool) -> None:
        m = match_item(s)
        if m is not None and self._push_item(m, offset):
            self.stack[-1].content_end = line_end
            return
        if allow_text:
            self.stack[-1].content_end = line_end

    def _push_item(self, m: Marker, offset: int) -> bool:
        sibling_at = None
        for i in range(len(self.stack) - 1, 0, -1):
            n = self.stack[i]
            if n.kind == "heading":
                break
            if n.type == m.type:
                sibling_at = i
                break
        if sibling_at is not None:
            del self.stack[sibling_at:]
        elif m.ordinal is not None and m.ordinal != 1:
            # 처음 보는 종류의 순번 항목은 1(①, 가)부터 시작해야 목록으로 인정
            return False
        node = Node("item", m.type, m.label, offset, offset + m.end, ordinal=m.ordinal)
        self._attach(node)
        return True

    def _attach(self, node: Node) -> None:
        parent = self.stack[-1]
        node.parent = parent
        parent.children.append(node)
        self.stack.append(node)


def _running_headers(lines: list[str]) -> set[str]:
    """여러 번 똑같이 나오는, 마커 없는 짧은 줄(쪽 머리글·꼬리글)을 찾습니다."""
    counts: dict[str, int] = {}
    for raw in lines:
        s = raw.strip()
        if s and len(s) <= _RUNNING_HEADER_MAX_CHARS:
            counts[s] = counts.get(s, 0) + 1
    return {
        s
        for s, n in counts.items()
        if n >= _RUNNING_HEADER_MIN_REPEATS
        and match_heading(s, 0) is None
        and match_item(s) is None
        and not s.endswith(("다.", ">", "]"))  # 반복되는 문장·개정 표시는 본문으로 둠
    }


def parse(text: str) -> Node:
    """텍스트를 구조 트리로 파싱합니다. 루트는 ``kind == "document"`` 노드입니다."""
    root = _Parser(text).parse()
    if not root.children and root.content_end == 0:
        root.content_end = len(text.rstrip())
    return root
