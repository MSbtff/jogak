"""선택 의존성(kiwipiepy, tiktoken, langchain) 연동 테스트. 설치되어 있지 않으면 건너뜁니다."""

import pytest

from jogak import Chunker, regex_splitter


def test_regex_splitter_offsets():
    text = "첫 문장입니다. 두 번째인가요? 네!\n줄바꿈 뒤 문장"
    spans = regex_splitter(text, 0, len(text))
    assert [text[s:e].strip() for s, e in spans] == [
        "첫 문장입니다.",
        "두 번째인가요?",
        "네!",
        "줄바꿈 뒤 문장",
    ]


def test_kiwi_splitter():
    pytest.importorskip("kiwipiepy")
    from jogak import kiwi_splitter

    split = kiwi_splitter()
    text = "앞부분 제외. 회의는 3시에 시작했다 그리고 4시에 끝났다 다음 회의는 내일이다"
    spans = split(text, 7, len(text))
    assert len(spans) >= 2
    assert all(7 <= s < e <= len(text) for s, e in spans)
    chunks = Chunker(25, sentence_splitter="kiwi").chunk(text)
    assert all(text[c.start : c.end] == c.text for c in chunks)


def test_tiktoken_length(law):
    pytest.importorskip("tiktoken")
    from jogak import tiktoken_length

    try:
        n_tokens = tiktoken_length("cl100k_base")
    except Exception as e:  # 인코딩 파일을 내려받지 못하는 환경
        pytest.skip(f"tiktoken encoding unavailable: {e}")
    chunks = Chunker(60, length_fn=n_tokens).chunk(law)
    assert all(n_tokens(c.text) <= 60 for c in chunks)


def test_langchain_splitter(law):
    pytest.importorskip("langchain_text_splitters")
    from jogak.langchain import JogakTextSplitter

    splitter = JogakTextSplitter(max_size=80)
    texts = splitter.split_text(law)
    assert any(t.startswith("제2장 보안 조직 > 제4조(정보보호책임자)\n②") for t in texts)

    docs = splitter.create_documents([law], metadatas=[{"source": "규정.txt"}])
    assert len(docs) == len(texts)
    d = next(d for d in docs if d.page_content.endswith("보안사고의 조사 및 대응"))
    assert d.metadata["source"] == "규정.txt"
    assert d.metadata["jogak_path"][-1].startswith("②")
    assert law[d.metadata["start_index"] : d.metadata["end_index"]] == "3. 보안사고의 조사 및 대응"

    from langchain_core.documents import Document

    plain = JogakTextSplitter(max_size=80, add_context=False)
    split_docs = plain.split_documents([Document(page_content=law, metadata={"source": "a"})])
    assert [d.page_content for d in split_docs] == [c.text for c in Chunker(80).chunk(law)]
    assert all(d.metadata["source"] == "a" for d in split_docs)
