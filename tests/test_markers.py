import pytest

from jogak.markers import match_heading, match_item


@pytest.mark.parametrize(
    ("line", "last", "type_", "label"),
    [
        ("제1조(목적) 이 규정은 ...", 0, "article", "제1조(목적)"),
        ("제 12 조 (정의) 이 법에서", 11, "article", "제12조(정의)"),
        ("제4조의2(보안위원회) 정보보안에", 4, "article", "제4조의2(보안위원회)"),
        ("제5조 삭제 <2025. 12. 15.>", 4, "article", "제5조"),
        ("제3조(적용 범위) ① 이 규정은", 2, "article", "제3조(적용 범위)"),
        ("제7조", 3, "article", "제7조"),
        ("제7조 ① 항 내용", 3, "article", "제7조"),
        ("제1장 총칙", 0, "chapter", "제1장 총칙"),
        ("제2편 각칙", 0, "part", "제2편 각칙"),
        ("제3절 보칙", 0, "section", "제3절 보칙"),
        ("제1관 통칙", 0, "subsection", "제1관 통칙"),
        ("부칙 <제12호, 2025. 12. 15.>", 0, "addenda", "부칙 <제12호, 2025. 12. 15.>"),
        ("부 칙", 0, "addenda", "부 칙"),
        ("[별표 1] 수수료 기준", 0, "appendix", "[별표 1] 수수료 기준"),
        ("## 운영 방안", 0, "md2", "운영 방안"),
    ],
)
def test_headings(line, last, type_, label):
    m = match_heading(line, last)
    assert m is not None
    assert (m.type, m.label) == (type_, label)


@pytest.mark.parametrize(
    ("line", "last"),
    [
        ("제3조에 따라 처리한다.", 2),
        ("제3조제1항에 따른 직원", 2),
        ("제3조 및 제4조의 규정은 준용한다.", 9),  # 제목 괄호 없고 순번도 안 맞음 → 인용
        ("제2장에서 정한 바에 따른다.", 0),
        ("제2장 각 조의 규정은 이 장에 준용한다.", 0),  # "다."로 끝나는 문장
        ("부칙에서 정한다", 0),
        ("별표 1에 따른 수수료", 0),
        ("#해시태그", 0),
        ("일반 문장입니다.", 0),
    ],
)
def test_not_headings(line, last):
    assert match_heading(line, last) is None


@pytest.mark.parametrize(
    ("line", "type_", "ordinal", "body"),
    [
        ("1. 정보자산", "num_dot", 1, "정보자산"),
        ("12. 열두째", "num_dot", 12, "열두째"),
        ("가. 성명", "han_dot", 1, "성명"),
        ("하. 마지막", "han_dot", 14, "마지막"),
        ("1) 대상", "num_paren", 1, "대상"),
        ("나) 예외", "han_paren", 2, "예외"),
        ("(3) 셋째", "num_pparen", 3, "셋째"),
        ("(다) 셋째", "han_pparen", 3, "셋째"),
        ("① 이 규정은", "circled", 1, "이 규정은"),
        ("⑳이 규정은", "circled", 20, "이 규정은"),
        ("㉯ 둘째", "circled_han", 2, "둘째"),
        ("□ 점검", "bullet:□", None, "점검"),
        ("○ 조사", "bullet:○", None, "조사"),
        ("- 기간", "bullet:-", None, "기간"),
        ("ㅇ 추진배경", "bullet:ㅇ", None, "추진배경"),
    ],
)
def test_items(line, type_, ordinal, body):
    m = match_item(line)
    assert m is not None
    assert (m.type, m.ordinal, line[m.end :]) == (type_, ordinal, body)


@pytest.mark.parametrize(
    ("line", "type_", "label", "ordinal", "body"),
    [
        ("1의2. 가명처리", "num_dot", "1의2.", 1, "가명처리"),
        ("가의3. 세목", "han_dot", "가의3.", 1, "세목"),
        # 마크다운으로 변환된 법령 (legalize-kr 등)
        ("**①** 개인정보처리자는", "circled", "①", 1, "개인정보처리자는"),
        ("1\\. 정의", "num_dot", "1.", 1, "정의"),
        ("가\\. 성명", "han_dot", "가.", 1, "성명"),
        ("**2\\.** 굵은 호", "num_dot", "2.", 2, "굵은 호"),
        ("\\- 이스케이프 글머리", "bullet:-", "-", None, "이스케이프 글머리"),
    ],
)
def test_items_extended(line, type_, label, ordinal, body):
    m = match_item(line)
    assert m is not None
    assert (m.type, m.label, m.ordinal, line[m.end :]) == (type_, label, ordinal, body)


def test_markdown_article_heading_label_normalized():
    m = match_heading("##### 제7조의2 (보호위원회의 구성 등)", 0)
    assert (m.type, m.label, m.rank) == ("md5", "제7조의2(보호위원회의 구성 등)", 5)
    assert match_heading("## 제1장 총칙", 0).label == "제1장 총칙"


@pytest.mark.parametrize(
    "line",
    ["1.5배 증가", "2024. 1. 1. 시행", "거. 서수 아님", "-5도", "가나다라", "(주)회사", "100. 백"],
)
def test_not_items(line):
    assert match_item(line) is None
