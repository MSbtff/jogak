"""줄 머리의 구조 마커(제1장, 제3조, ①, 1., 가., □ 등)를 인식합니다."""

from __future__ import annotations

import re
from dataclasses import dataclass

HAN_ORDINALS = "가나다라마바사아자차카타파하"

# 제목 계층. 숫자가 작을수록 상위. 마크다운 제목은 #의 개수를 그대로 씁니다.
RANK_PART = 1  # 제1편, 부칙, [별표]
RANK_CHAPTER = 2  # 제1장
RANK_SECTION = 3  # 제1절
RANK_SUBSECTION = 4  # 제1관
RANK_ARTICLE = 5  # 제1조
_DIVISION_RANK = {"편": RANK_PART, "장": RANK_CHAPTER, "절": RANK_SECTION, "관": RANK_SUBSECTION}
_DIVISION_TYPE = {"편": "part", "장": "chapter", "절": "section", "관": "subsection"}


@dataclass(frozen=True, slots=True)
class Marker:
    """줄 머리에서 찾은 마커.

    Attributes:
        kind: ``"heading"`` (장·조·마크다운 제목 등) 또는 ``"item"`` (①, 1., 가., □ 등).
        type: 세부 종류. 같은 type 끼리 형제가 됩니다 (예: ``"article"``, ``"num_dot"``).
        label: 경로에 표시할 이름 (예: ``"제3조(적용 범위)"``, ``"①"``).
        end: 마커가 끝나는 위치 (본문 시작 위치, 줄 안의 상대 위치).
        rank: 제목 계층 (item 은 0).
        ordinal: 순번 (①=1, 가=1). 순번이 없는 글머리표는 None.
    """

    kind: str
    type: str
    label: str
    end: int
    rank: int = 0
    ordinal: int | None = None


# --- 제목 -------------------------------------------------------------------

_ARTICLE = re.compile(
    r"제\s*([0-9]+)\s*조(?:\s*의\s*([0-9]+))?(?:\s*\(([^()\n]{1,60})\))?(?=\s|$|[①-⑳])"
)
_DIVISION = re.compile(r"제\s*([0-9]+)\s*(편|장|절|관)(?:\s+(.+?))?\s*$")
_ADDENDA = re.compile(r"부\s*칙(?:\s*[<(\[].*)?\s*$")
_APPENDIX = re.compile(r"\[\s*별\s*(?:표|지)[^\]\n]{0,20}\](.*)$")
_MD_HEADING = re.compile(r"(#{1,6})\s+(.+?)\s*#*\s*$")
_CIRCLED_START = re.compile(r"\s*[①-⑳]")
# "제3조 및 제4조에서 …", "제3조, 제5조 …", "제3조 제2항에 따라 …" 처럼 조 번호 뒤가 인용을
# 잇는 말이면 조문이 아니라 본문 속 인용입니다. PDF 에서 줄이 바뀌어 줄 머리에 오는 경우가 많습니다.
_CITATION_TAIL = re.compile(
    r"\s*(?:[,、·ㆍ~∼]|(?:및|또는|내지|부터|까지|단서|본문|전단|후단)(?=\s|$)"
    r"|각\s*(?:호|항|목)|제\s*[0-9])"
)
# 다만 부칙의 "제2조 부터 제8조까지 생략", "제13조 및 제14조 삭제" 는 실제 조문 줄입니다.
_OMITTED_RANGE = re.compile(r".*(?:생략|삭제)\s*(?:<[^<>\n]*>)?\s*$")


def match_heading(line: str, last_article: int) -> Marker | None:
    """앞 공백을 제거한 한 줄에서 제목 마커를 찾습니다.

    ``last_article`` 은 직전 조 번호입니다. 제목 괄호가 없는 "제5조 ..." 줄이 본문 속 인용
    ("제3조 및 제4조의 ...")인지 실제 조문인지 가리는 데 씁니다.
    """
    if line.startswith("#"):
        m = _MD_HEADING.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2).replace("**", "").strip()
            a = _ARTICLE.match(text)
            if a and not text[a.end() :].strip():  # "##### 제1조 (목적)" → "제1조(목적)"
                text = _article_label(a)
            return Marker("heading", f"md{level}", text, len(line), rank=level)
        return None

    if line.startswith("제"):
        m = _DIVISION.match(line)
        if m:
            title = (m.group(3) or "").strip()
            if len(title) <= 50 and not title.endswith("다."):
                unit = m.group(2)
                label = f"제{m.group(1)}{unit}" + (f" {title}" if title else "")
                return Marker(
                    "heading", _DIVISION_TYPE[unit], label, len(line), _DIVISION_RANK[unit]
                )
        m = _ARTICLE.match(line)
        if m:
            num, sub, title = int(m.group(1)), m.group(2), m.group(3)
            rest = line[m.end() :]
            plausible = (
                title is not None
                or not rest.strip()
                or _CIRCLED_START.match(rest) is not None
                or (
                    (_CITATION_TAIL.match(rest) is None or _OMITTED_RANGE.match(rest) is not None)
                    and (
                        (sub is None and num == last_article + 1)
                        or (sub is not None and num == last_article)
                    )
                )
            )
            if plausible:
                return Marker(
                    "heading", "article", _article_label(m), m.end(), RANK_ARTICLE, ordinal=num
                )
        return None

    if line.startswith("부"):
        m = _ADDENDA.match(line)
        if m:
            return Marker("heading", "addenda", _shorten(line.strip(), 30), len(line), RANK_PART)
        return None

    if line.startswith("["):
        m = _APPENDIX.match(line)
        if m:
            return Marker("heading", "appendix", _shorten(line.strip(), 40), len(line), RANK_PART)
    return None


def _article_label(m: re.Match[str]) -> str:
    num, sub, title = m.group(1), m.group(2), m.group(3)
    return f"제{int(num)}조" + (f"의{sub}" if sub else "") + (f"({title.strip()})" if title else "")


# --- 항목 -------------------------------------------------------------------
# 마크다운으로 변환된 법령(예: legalize-kr)의 "**①**", "1\." 같은 표기도 받아들입니다.

_HAN = HAN_ORDINALS
_B = r"(?:\*\*|__)?"  # 굵게 표시
_SUB = r"(?:의[0-9]{1,2})?"  # 가지번호: "1의2."


def _item(core: str, tail: str = r"(?=\s|$)") -> re.Pattern[str]:
    return re.compile(_B + core + _B + tail)


_ROMAN_UNI = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10}

_ITEM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # 보고서·공문서의 로마숫자: "Ⅰ. 추진 배경", "Ⅱ 추진 계획", "IV. 결론"
    ("roman", _item(rf"([{_ROMAN_UNI}])\\?\.?")),
    ("roman", _item(r"([IVX]{1,4})\\?\.")),
    # 소수점 번호: "1.1 목적", "1.2.1. 세부 범위". 깊이(점 개수)마다 다른 종류로 봅니다.
    ("decimal", _item(r"([1-9][0-9]?(?:\.[0-9]{1,2}){1,4})\.?")),
    ("num_pparen", _item(r"\\?\(([0-9]{1,2})\\?\)")),
    ("han_pparen", _item(rf"\\?\(([{_HAN}])\\?\)")),
    ("num_dot", _item(rf"([0-9]{{1,2}}){_SUB}\\?\.")),
    ("han_dot", _item(rf"([{_HAN}]){_SUB}\\?\.")),
    ("num_paren", _item(r"([0-9]{1,2})\\?\)")),
    ("han_paren", _item(rf"([{_HAN}])\\?\)")),
    ("circled", _item(r"([①-⑳])", tail="")),
    ("circled_han", _item(r"([㉮-㉻])", tail="")),
    ("bullet", _item(r"\\?([□■▣○●◎◦◇◆◈▶▷►•·∙▪ㅇ※➢*\-–])", tail=r"(?=\s)")),
)
_SPACES = re.compile(r"\s*")
_MD_NOISE = re.compile(r"\*\*|__|\\")


def _roman_value(token: str) -> int:
    if token in _ROMAN_UNI:
        return _ROMAN_UNI.index(token) + 1
    total = 0
    for ch, nxt in zip(token, [*token[1:], ""], strict=True):
        v = _ROMAN_VALUES[ch]
        total += -v if nxt and _ROMAN_VALUES[nxt] > v else v
    return total


def _ordinal(type_: str, token: str) -> int | None:
    if type_ == "roman":
        return _roman_value(token)
    if type_.startswith("decimal"):
        return int(token.rsplit(".", 1)[1])
    if type_.startswith("num"):
        return int(token)
    if type_.startswith("han"):
        return HAN_ORDINALS.index(token) + 1
    if type_ == "circled":
        return ord(token) - 0x2460 + 1
    if type_ == "circled_han":
        return ord(token) - 0x326E + 1
    return None


def match_item(line: str) -> Marker | None:
    """앞 공백을 제거한 한 줄에서 항목 마커를 찾습니다."""
    for type_, pattern in _ITEM_PATTERNS:
        m = pattern.match(line)
        if m is None:
            continue
        token = m.group(1)
        if type_ == "bullet":
            type_ = f"bullet:{token}"
        elif type_ == "decimal":
            type_ = f"decimal{token.count('.') + 1}"
        end = _SPACES.match(line, m.end()).end()
        label = _MD_NOISE.sub("", m.group(0))
        return Marker("item", type_, label, end, ordinal=_ordinal(type_, token))
    return None


# --- 잡음 -------------------------------------------------------------------

_PAGE_NUMBER = re.compile(
    r"[-–—]\s*[0-9]{1,4}\s*[-–—]"  # - 3 -
    r"|[0-9]{1,4}\s*/\s*[0-9]{1,4}"  # 3 / 20
    r"|[0-9]{1,4}\s*(?:쪽|페이지)"
    r"|(?:p\.|page)\s*[0-9]{1,4}",
    re.IGNORECASE,
)


def is_page_number(line: str) -> bool:
    """앞뒤 공백을 제거한 한 줄이 쪽 번호(``- 3 -``, ``3 / 20``, ``3쪽``)뿐인지."""
    return _PAGE_NUMBER.fullmatch(line) is not None


def _shorten(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"
