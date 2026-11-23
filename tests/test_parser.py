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


def test_wrapped_citation_is_not_article():
    # PDF 에서 줄이 바뀌어 본문 속 인용 "제3조 및 …" 이 줄 머리에 온 경우
    text = (
        "제2조(정의) 이 법의 적용 범위는\n"
        "제3조 및 제4조에서 정하는 바에 따른다.\n"
        "제3조(적용 범위) 이 법은 모든 사업장에 적용한다."
    )
    assert outline(text) == ["제2조(정의)", "제3조(적용 범위)"]
    art2 = parse(text).children[0]
    assert text[art2.start : art2.end].endswith("정하는 바에 따른다.")


def test_omitted_article_ranges_in_addenda():
    text = "부칙\n제1조(시행일) 이 법은 공포한 날부터 시행한다.\n제2조 부터 제5조까지 생략"
    assert outline(text) == ["부칙", "  제1조(시행일)", "  제2조"]


def test_page_numbers_and_running_headers_are_not_structure():
    page = "정보보안 관리 규정\n"
    text = (
        page
        + "제5조(의무) ① 사업주는 다음 각 호를 지켜야 한다.\n1. 안전 교육\n- 3 -\n"
        + page
        + "2. 보건 관리\n② 위반 시 제재한다.\n- 4 -\n"
        + page
        + "제6조(벌칙) 벌금에 처한다."
    )
    assert outline(text) == ["제5조(의무)", "  ①", "    1.", "    2.", "  ②", "제6조(벌칙)"]
    item2 = next(n for n in parse(text).walk() if n.label == "2.")
    assert text[item2.start : item2.end] == "2. 보건 관리"
    item1 = next(n for n in parse(text).walk() if n.label == "1.")
    assert text[item1.start : item1.end] == "1. 안전 교육"


def test_repeated_sentence_lines_are_kept():
    text = "1. 첫째\n해당 사항 없다.\n2. 둘째\n해당 사항 없다.\n3. 셋째\n해당 사항 없다."
    third = parse(text).children[2]
    assert text[third.start : third.end] == "3. 셋째\n해당 사항 없다."


def test_report_outline_roman_decimal_bullets():
    text = (
        "Ⅰ. 추진 배경\n 1. 현황\n  ◦ 시스템 노후화\n  ◦ 보안 취약\n"
        "Ⅱ. 추진 계획\n1.1 목적\n1.2 범위\n1.2.1 세부 범위\n1.3 일정\n"
        "Ⅲ. 기대 효과"
    )
    assert outline(text) == [
        "Ⅰ.",
        "  1.",
        "    ◦",
        "    ◦",
        "Ⅱ.",
        "  1.1",
        "  1.2",
        "    1.2.1",
        "  1.3",
        "Ⅲ.",
    ]


def test_decimal_numbering_nests_under_num_dot():
    text = "1. 개요\n1.1 목적\n1.2 범위\n2. 절차\n2.1 신청"
    assert outline(text) == ["1.", "  1.1", "  1.2", "2.", "  2.1"]


def test_to_dict(law):
    d = parse(law).to_dict(law)
    assert d["kind"] == "document"
    assert d["children"][0]["label"] == "제1장 총칙"
    assert d["children"][0]["children"][0]["own_text"].startswith("제1조(목적)")
