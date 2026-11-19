import pytest

from jogak import Chunker, chunk, regex_splitter

SIZES = [20, 35, 50, 80, 120, 200, 400, 2000]


def check_invariants(text, chunks, max_size, length_fn=len):
    prev_end = 0
    covered = []
    for i, c in enumerate(chunks):
        assert c.index == i
        assert text[c.start : c.end] == c.text
        assert c.text == c.text.strip() and c.text
        assert length_fn(c.text) <= max_size
        assert c.start >= prev_end
        prev_end = c.end
        covered.append((c.start, c.end))
    # 청크에 들어가지 않은 텍스트는 공백이거나, 뒤 청크 경로에 그대로 남아 있어야 함
    contexts = " | ".join(" ".join(" ".join(c.path).split()) for c in chunks)
    pos = 0
    for s, e in [*covered, (len(text), len(text))]:
        gap = " ".join(text[pos:s].split())
        if gap:
            assert gap.rstrip("…") in contexts or gap[:20] in contexts, gap
        pos = e


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("merge", [True, False])
def test_invariants(law, gongmun, size, merge):
    for text in (law, gongmun):
        check_invariants(text, Chunker(size, merge=merge).chunk(text), size)


def test_big_budget_single_chunk(law):
    chunks = Chunker(10_000).chunk(law)
    assert len(chunks) == 1
    assert chunks[0].text == law.strip()
    assert chunks[0].path == ()


def test_paths_for_small_budget(law):
    chunks = Chunker(80).chunk(law)

    def context_of(prefix):
        return next(c.context for c in chunks if c.text.startswith(prefix))

    assert context_of("② 정보보호책임자는") == "제2장 보안 조직 > 제4조(정보보호책임자)"
    assert context_of("가. 성명") == (
        '제1장 총칙 > 제2조(정의) > 2. "개인정보"란 살아 있는 개인에 관한…'
    )


def test_title_prefix(law):
    chunks = Chunker(80).chunk(law, title="정보보안 관리 규정")
    assert all(c.path[0] == "정보보안 관리 규정" for c in chunks)
    assert chunks[-1].embed_text.startswith("정보보안 관리 규정 > 부칙")


def test_merge_false_one_article_per_chunk(law):
    chunks = Chunker(10_000, merge=False).chunk(law)
    firsts = [c.text.split()[0] for c in chunks]
    assert firsts == [
        "정보보안",
        "제1조(목적)",
        "제2조(정의)",
        "제3조(적용",
        "제4조(정보보호책임자)",
        "제4조의2(보안위원회)",
        "제5조",
        "제6조(접근",
        "제7조(보안사고",
        "제1조(시행일)",
        "제2조(경과조치)",
    ]
    assert chunks[3].context == "제1장 총칙"
    assert chunks[9].context == "부칙 <제12호, 2025. 12. 15.>"


def test_merge_packs_small_siblings():
    text = "\n".join(f"제{i}조(조문{i}) 짧은 본문이다." for i in range(1, 7))
    chunks = Chunker(60).chunk(text)
    assert [c.text.count("제") for c in chunks] == [3, 3]


def test_long_paragraph_split_by_sentences():
    body = " ".join(f"이것은 {i}번째 문장입니다." for i in range(1, 21))
    text = f"제1조(긴 조문) {body}"
    chunks = Chunker(60).chunk(text)
    check_invariants(text, chunks, 60)
    assert len(chunks) > 3
    assert all(c.text.endswith("다.") for c in chunks)
    assert all(c.path == ("제1조(긴 조문)",) for c in chunks)


def test_hard_split_prefers_spaces():
    text = "가나다라마 " * 40  # 문장 부호 없는 긴 줄
    chunks = Chunker(50).chunk(text)
    check_invariants(text, chunks, 50)
    assert all(c.text.endswith("가나다라마") for c in chunks)


def test_hard_split_without_spaces():
    text = "가" * 130
    chunks = Chunker(50).chunk(text)
    assert [len(c.text) for c in chunks] == [50, 50, 30]


def test_custom_length_fn(law):
    words = lambda t: len(t.split())  # noqa: E731
    chunks = Chunker(15, length_fn=words).chunk(law)
    check_invariants(law, chunks, 15, length_fn=words)


def test_custom_sentence_splitter():
    calls = []

    def splitter(text, start, end):
        calls.append((start, end))
        return regex_splitter(text, start, end)

    Chunker(30, sentence_splitter=splitter).chunk("문장 하나입니다. " * 10)
    assert calls


def test_item_label_chars(law):
    chunks = Chunker(80, item_label_chars=0).chunk(law)
    assert any(c.context.endswith("> 2.") for c in chunks)


def test_chunk_helper_and_to_dict(law):
    chunks = chunk(law, 80, title="규정")
    d = chunks[0].to_dict()
    assert set(d) == {"index", "text", "start", "end", "path"}
    assert d["path"][0] == "규정"


def test_embed_text_without_path():
    c = Chunker(100).chunk("짧은 문서")[0]
    assert c.embed_text == "짧은 문서"
    assert c.context == ""


def test_bad_arguments():
    with pytest.raises(ValueError):
        Chunker(0)
    with pytest.raises(ValueError, match="unknown sentence splitter"):
        Chunker(100, sentence_splitter="nope")


def test_empty_text():
    assert Chunker(100).chunk("") == []
    assert Chunker(100).chunk("  \n\n ") == []
