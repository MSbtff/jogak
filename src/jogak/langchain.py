"""LangChain 연동. ``pip install 'jogak[langchain]'`` 가 필요합니다.

>>> from jogak.langchain import JogakTextSplitter      # doctest: +SKIP
>>> splitter = JogakTextSplitter(max_size=500)          # doctest: +SKIP
>>> docs = splitter.create_documents([text], metadatas=[{"source": "규정.txt"}])  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

try:
    from langchain_core.documents import Document
    from langchain_text_splitters import TextSplitter
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "jogak.langchain needs langchain-text-splitters: pip install 'jogak[langchain]'"
    ) from e

from .chunker import Chunker, LengthFn
from .sentences import SentenceSplitter


class JogakTextSplitter(TextSplitter):
    """jogak 청커를 LangChain ``TextSplitter`` 로 감쌉니다.

    ``create_documents`` 는 각 문서 metadata 에 ``jogak_path`` (상위 구조 목록),
    ``start_index``, ``end_index`` 를 추가합니다.
    """

    def __init__(
        self,
        max_size: int = 800,
        *,
        length_function: LengthFn = len,
        merge: bool = True,
        sentence_splitter: str | SentenceSplitter = "regex",
        item_label_chars: int = 20,
        add_context: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            add_context: True면 ``page_content`` 첫 줄에 상위 구조 경로를 붙입니다
                (임베딩 검색 정확도에 도움이 됩니다).
        """
        kwargs.setdefault("chunk_overlap", 0)
        super().__init__(chunk_size=max_size, length_function=length_function, **kwargs)
        self._chunker = Chunker(
            max_size,
            length_fn=length_function,
            merge=merge,
            sentence_splitter=sentence_splitter,
            item_label_chars=item_label_chars,
        )
        self._add_context = add_context

    def split_text(self, text: str) -> list[str]:
        return [self._content(c) for c in self._chunker.chunk(text)]

    def create_documents(
        self, texts: list[str], metadatas: list[dict[Any, Any]] | None = None
    ) -> list[Document]:
        metas = metadatas or [{}] * len(texts)
        docs: list[Document] = []
        for text, meta in zip(texts, metas, strict=True):
            for c in self._chunker.chunk(text):
                docs.append(
                    Document(
                        page_content=self._content(c),
                        metadata={
                            **meta,
                            "jogak_path": list(c.path),
                            "start_index": c.start,
                            "end_index": c.end,
                        },
                    )
                )
        return docs

    def split_documents(self, documents: Iterable[Document]) -> list[Document]:
        docs: Sequence[Document] = list(documents)
        return self.create_documents(
            [d.page_content for d in docs], metadatas=[dict(d.metadata) for d in docs]
        )

    def _content(self, c: Any) -> str:
        return c.embed_text if self._add_context else c.text
