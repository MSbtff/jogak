"""문서 구조를 따라 크기 제한에 맞춰 자르는 청커."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .parser import Node, parse
from .sentences import SentenceSplitter, resolve_splitter

LengthFn = Callable[[str], int]


@dataclass(frozen=True, slots=True)
class Chunk:
    """청크 한 개.

    Attributes:
        text: 원문 그대로의 청크 본문. 항상 ``source[start:end]`` 와 같습니다.
        start, end: 원문에서의 위치.
        path: 이 청크를 감싸는 상위 구조 (예: ``("제2장 보안 조직", "제4조(정보보호책임자)")``).
        index: 문서 안에서 몇 번째 청크인지 (0부터).
    """

    text: str
    start: int
    end: int
    path: tuple[str, ...]
    index: int

    @property
    def context(self) -> str:
        """상위 구조를 ``" > "`` 로 이은 문자열."""
        return " > ".join(self.path)

    @property
    def embed_text(self) -> str:
        """임베딩용 텍스트: 상위 구조 경로를 첫 줄에 붙인 본문."""
        return f"{self.context}\n{self.text}" if self.path else self.text

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "path": list(self.path),
        }


class Chunker:
    """한국어 규정·법령·공문서의 구조를 지키며 청크를 만듭니다.

    >>> chunker = Chunker(max_size=60)
    >>> doc = "제1조(목적) 이 규정은 목적을 정한다.\\n제2조(정의) ① 첫째 항이다.\\n② 둘째 항이다."
    >>> [c.text for c in chunker.chunk(doc)]
    ['제1조(목적) 이 규정은 목적을 정한다.\\n제2조(정의) ① 첫째 항이다.\\n② 둘째 항이다.']
    >>> for c in Chunker(max_size=25).chunk(doc):
    ...     print(f"[{c.context}] {c.text!r}")
    [] '제1조(목적) 이 규정은 목적을 정한다.'
    [] '제2조(정의) ① 첫째 항이다.'
    [제2조(정의)] '② 둘째 항이다.'
    """

    def __init__(
        self,
        max_size: int = 800,
        *,
        length_fn: LengthFn = len,
        merge: bool = True,
        sentence_splitter: str | SentenceSplitter = "regex",
        item_label_chars: int = 20,
    ) -> None:
        """
        Args:
            max_size: 청크 최대 크기. 단위는 ``length_fn`` 이 정합니다 (기본은 글자 수).
            length_fn: 텍스트 크기를 재는 함수. 토큰 수로 맞추려면
                :func:`jogak.tiktoken_length` 등을 넘기세요.
            merge: True면 크기 안에서 이웃한 조문·항목을 한 청크로 묶습니다.
                False면 구조 단위(예: 조문 하나)마다 따로 청크를 만듭니다.
            sentence_splitter: 구조 단위 하나가 너무 길 때 쓸 문장 분리기.
                ``"regex"`` (기본), ``"kiwi"``, 또는 함수.
            item_label_chars: 경로에 항목(1., 가. 등)을 표시할 때 붙일 본문 글자 수.
        """
        if max_size < 1:
            raise ValueError("max_size must be positive")
        self.max_size = max_size
        self.length_fn = length_fn
        self.merge = merge
        self.item_label_chars = item_label_chars
        self._split_sentences = resolve_splitter(sentence_splitter)

    def chunk(self, text: str, *, title: str | None = None) -> list[Chunk]:
        """텍스트를 청크로 나눕니다. ``title`` 을 주면 모든 청크 경로의 맨 앞에 붙습니다."""
        root = parse(text)
        spans: list[tuple[int, int, tuple[str, ...]]] = []
        self._emit(root, text, (title,) if title else (), spans)
        chunks: list[Chunk] = []
        for s, e, path in spans:
            s, e = _trim(text, s, e)
            if s < e:
                chunks.append(Chunk(text[s:e], s, e, path, len(chunks)))
        return chunks

    # --- 내부 --------------------------------------------------------------

    def _size(self, src: str, s: int, e: int) -> int:
        return self.length_fn(src[s:e].strip())

    def _fits(self, src: str, s: int, e: int) -> bool:
        return self._size(src, s, e) <= self.max_size

    def _label(self, node: Node, src: str) -> str:
        if node.kind != "item" or self.item_label_chars <= 0:
            return node.label
        body = " ".join(src[node.body_start : node.own_end].split())
        if not body:
            return node.label
        n = self.item_label_chars
        return f"{node.label} {body if len(body) <= n else body[:n] + '…'}"

    def _emit(self, node: Node, src: str, path: tuple[str, ...], out: list) -> None:
        has_heading_child = any(c.kind == "heading" for c in node.children)
        if (self.merge or not has_heading_child) and self._fits(src, node.start, node.end):
            out.append((node.start, node.end, path))
            return

        inner = path if node.kind == "document" else (*path, self._label(node, src))
        own_s, own_e = node.start, node.own_end
        # 자기 본문이 하위 청크의 경로 표시에 이미 다 들어가면, 본문만 따로 청크로 만들지 않음
        own_body = " ".join(src[node.body_start : own_e].split())
        header_only = bool(node.children) and (
            (node.kind == "heading" and not own_body)
            or (node.kind == "item" and len(own_body) <= self.item_label_chars)
        )

        units: list[tuple[int, int, Node | None]] = []
        if src[own_s:own_e].strip():
            units.append((own_s, own_e, None))
        units += [(c.start, c.end, c) for c in node.children]

        # [start, end, has_own, only_header, mergeable]
        group: list[Any] | None = None

        def flush() -> None:
            nonlocal group
            if group is not None:
                gs, ge, has_own, only_header, _ = group
                if not only_header:  # 제목 줄만 있는 그룹은 경로에 이미 있으므로 버림
                    out.append((gs, ge, path if has_own else inner))
                group = None

        for us, ue, child in units:
            is_own = child is None
            must_descend = (
                child is not None
                and not self.merge
                and any(g.kind == "heading" for g in child.children)
            )
            if must_descend or not self._fits(src, us, ue):
                flush()
                if is_own:
                    self._split_long(src, us, ue, inner, out)
                else:
                    self._emit(child, src, inner, out)
                continue
            # merge=False 에서는 제목(장·조) 단위끼리 묶지 않고, 본문과 항목만 함께 둠
            mergeable = self.merge or is_own or child.kind == "item"
            if group is not None and mergeable and group[4] and self._fits(src, group[0], ue):
                group[1] = ue
                group[3] = False
                continue
            flush()
            group = [us, ue, is_own, is_own and header_only, mergeable]
        flush()

    def _split_long(self, src: str, s: int, e: int, path: tuple[str, ...], out: list) -> None:
        """구조로 더 나눌 수 없는 긴 본문을 문장 단위로 묶어 자릅니다."""
        cur: list[int] | None = None
        for ss, se in self._split_sentences(src, s, e):
            if cur is not None and self._fits(src, cur[0], se):
                cur[1] = se
                continue
            if cur is not None:
                out.append((cur[0], cur[1], path))
                cur = None
            if self._fits(src, ss, se):
                cur = [ss, se]
            else:
                for hs, he in self._hard_split(src, ss, se):
                    out.append((hs, he, path))
        if cur is not None:
            out.append((cur[0], cur[1], path))

    def _hard_split(self, src: str, s: int, e: int) -> list[tuple[int, int]]:
        """문장 하나가 너무 길면 크기 안에서 최대한 길게, 가능하면 공백에서 자릅니다."""
        pieces: list[tuple[int, int]] = []
        while s < e:
            if self._fits(src, s, e):
                pieces.append((s, e))
                break
            lo, hi = s + 1, e  # fits(s, lo) 이 참인 가장 큰 lo 를 찾음
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if self._fits(src, s, mid):
                    lo = mid
                else:
                    hi = mid - 1
            cut = lo
            space = src.rfind(" ", s + 1, cut)
            if space > s + (cut - s) * 4 // 5:
                cut = space
            pieces.append((s, cut))
            s = cut
        return pieces


def _trim(src: str, s: int, e: int) -> tuple[int, int]:
    while s < e and src[s].isspace():
        s += 1
    while e > s and src[e - 1].isspace():
        e -= 1
    return s, e


def chunk(text: str, max_size: int = 800, **kwargs: Any) -> list[Chunk]:
    """``Chunker(max_size, **kwargs).chunk(text)`` 의 줄임."""
    title = kwargs.pop("title", None)
    return Chunker(max_size, **kwargs).chunk(text, title=title)
