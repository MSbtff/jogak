"""legalize-kr 의 법령 Markdown 을 법제처 웹사이트에서 복사한 것과 비슷한 일반 텍스트로 바꿉니다.

사용법:
    python benchmark/prepare_data.py <legalize-kr 법률.md 파일들...>

출처: https://github.com/legalize-kr/legalize-kr
(법령 원문은 공공저작물, 저장소 구조와 메타데이터는 MIT)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_ARTICLE_TITLE = re.compile(r"^(제[0-9]+조(?:의[0-9]+)?)\s+\(")


def convert(md: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    m = _FRONT_MATTER.match(md)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip("'")
        md = md[m.end() :]

    out: list[str] = []
    pending_article: str | None = None
    for line in md.splitlines():
        line = line.replace("**", "").replace("\\", "")
        h = _HEADING.match(line)
        if h:
            if pending_article:
                out.append(pending_article)
            text = _ARTICLE_TITLE.sub(r"\1(", h.group(1).strip())
            if text.startswith("제") and "조" in text.split()[0]:
                pending_article = text  # 다음 본문 줄과 합쳐 "제1조(목적) 이 법은 ..." 형태로
            else:
                pending_article = None
                out.extend(["", text, ""])
            continue
        if pending_article is not None:
            if not line.strip():
                continue
            out.append(f"{pending_article} {line.strip()}")
            pending_article = None
            continue
        if line.strip():
            out.append(line.rstrip())
        elif out and out[-1] != "":
            out.append("")
    if pending_article:
        out.append(pending_article)
    text = "\n".join(out).strip() + "\n"
    return meta, re.sub(r"\n{3,}", "\n\n", text)


def main(paths: list[str]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for p in paths:
        meta, text = convert(Path(p).read_text(encoding="utf-8"))
        name = meta.get("제목", Path(p).stem).replace(" ", "")
        header = (
            f"<!-- 출처: legalize-kr ({meta.get('출처', '')}), "
            f"공포 {meta.get('공포일자', '?')}, 시행 {meta.get('시행일자', '?')} -->\n"
        )
        out = DATA_DIR / f"{name}.txt"
        out.write_text(header + text, encoding="utf-8")
        print(f"{out}  {len(text):,}자")


if __name__ == "__main__":
    main(sys.argv[1:])
