from jogak import parse


def outline(text: str) -> list[str]:
    """트리를 '깊이*공백 + 라벨' 목록으로."""
    root = parse(text)
    lines: list[str] = []

    def walk(node, depth):
        for c in node.children:
            lines.append("  " * depth + c.label)
            walk(c, depth + 1)

    walk(root, 0)
    return lines


def test_law_outline(law):
    assert outline(law) == [
        "제1장 총칙",
        "  제1조(목적)",
        "  제2조(정의)",
        "    1.",
        "    2.",
        "      가.",
        "      나.",
        "    3.",
        "  제3조(적용 범위)",
        "    ①",
        "    ②",
        "제2장 보안 조직",
        "  제4조(정보보호책임자)",
        "    ①",
        "    ②",
        "      1.",
        "      2.",
        "      3.",
        "  제4조의2(보안위원회)",
        "  제5조",
        "제3장 보안 관리",
        "  제6조(접근 통제)",
        "    ①",
        "    ②",
        "  제7조(보안사고 대응)",
        "부칙 <제12호, 2025. 12. 15.>",
        "  제1조(시행일)",
        "  제2조(경과조치)",
    ]


def test_gongmun_outline(gongmun):
    assert outline(gongmun) == [
        "1.",
        "  가.",
        "  나.",
        "2.",
        "  가.",
        "    1)",
        "    2)",
        "  나.",
        "    1)",
        "      가)",
        "      나)",
        "    2)",
        "3.",
        "  □",
        "    ○",
        "      -",
        "    ○",
        "  □",
    ]


def test_offsets_are_nested_and_contiguous(law, gongmun):
    for text in (law, gongmun):
        root = parse(text)
        for node in root.walk():
            assert node.start <= node.body_start <= max(node.own_end, node.body_start)
            prev_end = node.own_end
            for child in node.children:
                assert node.start <= child.start and child.end <= node.end
                assert child.start >= prev_end
                prev_end = child.end
            assert (
                not text[node.own_end : node.children[0].start].strip() if node.children else True
            )


def test_inline_paragraph_after_article(law):
    root = parse(law)
    art3 = next(n for n in root.walk() if n.label == "제3조(적용 범위)")
    first = art3.children[0]
    assert law[first.start : first.start + 1] == "①"
    assert law[art3.start : first.start].strip() == "제3조(적용 범위)"


def test_list_must_start_at_first_ordinal():
    text = "보고서\n3. 이 숫자는 목록이 아님\n1. 진짜 목록\n2. 둘째"
    assert outline(text) == ["1.", "2."]
    root = parse(text)
    assert "3. 이 숫자는" in text[root.start : root.own_end]


def test_continuation_lines_stay_with_item():
    text = "1. 첫째 항목\n   이어지는 설명\n2. 둘째 항목"
    root = parse(text)
    first = root.children[0]
    assert text[first.start : first.end] == "1. 첫째 항목\n   이어지는 설명"


def test_heading_closes_open_lists():
    text = "제1조(가) ① 하나\n1. 호\n가. 목\n제2조(나) 본문\n① 새 항"
    assert outline(text) == ["제1조(가)", "  ①", "    1.", "      가.", "제2조(나)", "  ①"]


def test_markdown_headings_and_lists():
    text = "# 규정\n## 목적\n본문\n## 절차\n1. 신청\n   - 서류 제출\n2. 승인"
    assert outline(text) == ["규정", "  목적", "  절차", "    1.", "      -", "    2."]


def test_empty_and_plain_text():
    assert parse("").children == []
    root = parse("그냥 문단입니다.\n다음 줄.")
    assert root.children == []
    assert root.end == len("그냥 문단입니다.\n다음 줄.")


def test_to_dict(law):
    d = parse(law).to_dict(law)
    assert d["kind"] == "document"
    assert d["children"][0]["label"] == "제1장 총칙"
    assert d["children"][0]["children"][0]["own_text"].startswith("제1조(목적)")
