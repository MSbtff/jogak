"""UML 컴포넌트 다이어그램과 배치(deployment) 다이어그램을 SVG 로 그립니다.

표준 라이브러리만 씁니다. 구조를 바꾸면 이 파일의 좌표와 이름을 고치고 다시 실행하세요.

    python docs/uml/draw.py   # → docs/uml/component.svg, docs/uml/deployment.svg
"""

from __future__ import annotations

from html import escape
from pathlib import Path

OUT = Path(__file__).parent

FONT = "'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR','Noto Sans CJK KR',sans-serif"
INK = "#1f2328"
INK_2 = "#57606a"
LINE = "#3d444d"
FILL = "#f6f8fa"
FILL_IN = "#ffffff"
FILL_EXT = "#fff8e6"
ACCENT = "#ddeeff"


class Svg:
    def __init__(self, width: int, height: int, title: str) -> None:
        self.w, self.h = width, height
        self.parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="{FONT}">',
            f"<title>{escape(title)}</title>",
            "<defs>"
            '<marker id="open" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="11" '
            'markerHeight="11" orient="auto-start-reverse">'
            f'<path d="M1,1 L11,6 L1,11" fill="none" stroke="{LINE}" stroke-width="1.4"/>'
            "</marker></defs>",
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        ]

    # --- 기본 도형 ---------------------------------------------------------------

    def text(self, x, y, s, size=13, weight="normal", anchor="start", color=INK, style=""):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" fill="{color}" {style}>{escape(s)}</text>'
        )

    def rect(self, x, y, w, h, fill=FILL, dash=False, rx=3, stroke=LINE, width=1.3):
        d = ' stroke-dasharray="6 4"' if dash else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}"{d}/>'
        )

    def path(self, points, dash=False, arrow=False, width=1.3):
        d = "M" + " L".join(f"{x},{y}" for x, y in points)
        extra = (' stroke-dasharray="6 4"' if dash else "") + (
            ' marker-end="url(#open)"' if arrow else ""
        )
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="{width}"{extra}/>'
        )

    def label(self, x, y, s, size=11.5, anchor="middle", color=INK_2):
        # 선 위의 글자가 잘 보이도록 흰 바탕을 깝니다
        w = text_width(s, size) + 8
        x0 = x - w / 2 if anchor == "middle" else (x if anchor == "start" else x - w)
        self.parts.append(
            f'<rect x="{x0}" y="{y - size}" width="{w}" height="{size + 5}" fill="#ffffff"/>'
        )
        self.text(
            x0 + 4 if anchor != "middle" else x,
            y,
            s,
            size,
            anchor=anchor if anchor == "middle" else "start",
            color=color,
        )

    # --- UML 요소 ----------------------------------------------------------------

    def component_icon(self, x, y):
        """오른쪽 위의 컴포넌트 아이콘 (탭 두 개가 달린 상자)."""
        self.rect(x, y, 16, 20, fill=FILL_IN, rx=1, width=1.1)
        self.rect(x - 5, y + 4, 10, 4, fill=FILL_IN, rx=0, width=1.1)
        self.rect(x - 5, y + 12, 10, 4, fill=FILL_IN, rx=0, width=1.1)

    def component(self, x, y, w, h, name, sub="", stereo="component", fill=FILL):
        self.rect(x, y, w, h, fill=fill)
        self.component_icon(x + w - 24, y + 8)
        cx = x + w / 2
        self.text(cx, y + 22, f"«{stereo}»", 11, anchor="middle", color=INK_2)
        self.text(cx, y + 41, name, 14.5, "bold", "middle")
        if sub:
            self.text(cx, y + 60, sub, 11.5, anchor="middle", color=INK_2)

    def lollipop(self, cx, cy, r=8):
        """제공 인터페이스(원)."""
        self.parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" '
            f'stroke="{LINE}" stroke-width="1.4"/>'
        )

    def socket(self, cx, cy, facing, r=13):
        """요구 인터페이스(반원). facing 은 반원이 열린 쪽: left/right/up/down."""
        start, end = {
            "left": ((cx, cy - r), (cx, cy + r)),
            "right": ((cx, cy + r), (cx, cy - r)),
            "up": ((cx + r, cy), (cx - r, cy)),
            "down": ((cx - r, cy), (cx + r, cy)),
        }[facing]
        self.parts.append(
            f'<path d="M{start[0]},{start[1]} A{r},{r} 0 0 1 {end[0]},{end[1]}" fill="none" '
            f'stroke="{LINE}" stroke-width="1.4"/>'
        )

    def node(self, x, y, w, h, name, stereo="node", fill=FILL, d=14):
        """3차원 상자 모양의 노드."""
        self.parts.append(
            f'<path d="M{x},{y} L{x + d},{y - d} L{x + w + d},{y - d} L{x + w},{y} Z" '
            f'fill="#e9edf1" stroke="{LINE}" stroke-width="1.3"/>'
            f'<path d="M{x + w},{y} L{x + w + d},{y - d} L{x + w + d},{y + h - d} L{x + w},{y + h} Z" '  # noqa: E501
            f'fill="#d8dee4" stroke="{LINE}" stroke-width="1.3"/>'
        )
        self.rect(x, y, w, h, fill=fill, rx=0)
        self.text(x + 12, y + 20, f"«{stereo}»", 11, color=INK_2)
        self.text(x + 12, y + 39, name, 14.5, "bold")

    def artifact(self, x, y, w, h, name, sub="", stereo="artifact", fill=FILL_IN):
        self.rect(x, y, w, h, fill=fill, rx=0)
        # 오른쪽 위 문서 아이콘 (접힌 모서리)
        ix, iy = x + w - 22, y + 7
        self.parts.append(
            f'<path d="M{ix},{iy} L{ix + 9},{iy} L{ix + 14},{iy + 5} L{ix + 14},{iy + 17} '
            f'L{ix},{iy + 17} Z M{ix + 9},{iy} L{ix + 9},{iy + 5} L{ix + 14},{iy + 5}" '
            f'fill="#ffffff" stroke="{LINE}" stroke-width="1.1"/>'
        )
        self.text(x + 10, y + 18, f"«{stereo}»", 10.5, color=INK_2)
        self.text(x + 10, y + 36, name, 13, "bold")
        if sub:
            self.text(x + 10, y + 52, sub, 11.5, color=INK_2)

    def note(self, x, y, w, lines, size=11.5):
        h = 14 + len(lines) * (size + 5)
        f = 10
        self.parts.append(
            f'<path d="M{x},{y} L{x + w - f},{y} L{x + w},{y + f} L{x + w},{y + h} L{x},{y + h} Z" '
            f'fill="#fffbdd" stroke="{LINE}" stroke-width="1.1"/>'
            f'<path d="M{x + w - f},{y} L{x + w - f},{y + f} L{x + w},{y + f}" fill="none" '
            f'stroke="{LINE}" stroke-width="1.1"/>'
        )
        for i, s in enumerate(lines):
            self.text(x + 10, y + 18 + i * (size + 5), s, size, color=INK)

    def save(self, name: str) -> Path:
        out = OUT / name
        out.write_text("\n".join([*self.parts, "</svg>"]) + "\n", encoding="utf-8")
        return out


def text_width(s: str, size: float) -> float:
    return sum(size * (1.0 if ord(ch) > 0x2E7F else 0.56) for ch in s)


# --- 컴포넌트 다이어그램 ---------------------------------------------------------------


def component_diagram() -> Path:
    g = Svg(1340, 900, "jogak UML 컴포넌트 다이어그램")
    W, H = 230, 76
    A, B, C = 90, 420, 750  # 열
    R1, R2, R3, R4 = 210, 370, 510, 650  # 행

    # 바깥 사용자
    g.component(B, 20, W, H, "사용자 코드", "RAG 파이프라인 · 터미널", fill=ACCENT)

    # jogak 서브시스템 경계
    g.rect(40, 170, 1000, 590, fill="#fbfcfd", rx=4, width=1.6)
    g.component_icon(1040 - 30, 180)
    g.text(56, 194, "«subsystem»", 11, color=INK_2)
    g.text(132, 195, "jogak", 15, "bold")

    comps = {
        "cli": (A, R1, "cli", "jogak 명령 (텍스트 → 청크)"),
        "api": (B, R1, "jogak", "공개 API (하위 모듈 재노출)"),
        "lc": (C, R1, "langchain", "JogakTextSplitter 어댑터"),
        "sent": (A, R2, "sentences", "regex · kiwi 문장 분리"),
        "chunker": (B, R2, "chunker", "Chunker · Chunk"),
        "length": (C, R2, "length", "tiktoken · HF 길이 함수"),
        "parser": (B, R3, "parser", "Node · parse()"),
        "markers": (B, R4, "markers", "Marker · 줄 머리 규칙"),
    }
    for x, y, name, sub in comps.values():
        g.component(x, y, W, H, name, sub)

    def cx(k):
        return comps[k][0] + W / 2

    # 바깥으로 제공하는 인터페이스 (경계 위쪽)
    lolly_y = 140
    provided = (("cli", "jogak CLI"), ("api", "chunk() · parse()"), ("lc", "TextSplitter"))
    for k, name in provided:
        x = cx(k)
        g.path([(x, comps[k][1]), (x, lolly_y + 8)])
        g.lollipop(x, lolly_y)
        g.label(x + 14, lolly_y + 4, name, anchor="start", color=INK)
    # 사용자 코드가 인터페이스를 씀
    g.path([(B + 40, 96), (cx("cli"), 112), (cx("cli"), lolly_y - 9)], dash=True, arrow=True)
    g.path([(cx("api"), 96), (cx("api"), lolly_y - 9)], dash=True, arrow=True)
    g.path([(B + W - 40, 96), (cx("lc"), 112), (cx("lc"), lolly_y - 9)], dash=True, arrow=True)
    g.label(cx("api") - 36, 122, "«use»")

    # 조립 연결: chunker 가 요구하는 전략 인터페이스
    my = R2 + H / 2
    # SentenceSplitter: sentences 가 제공, chunker 가 요구
    g.path([(A + W, my), (370 - 8, my)])
    g.lollipop(370, my)
    g.socket(370, my, "left")
    g.path([(370 + 13, my), (B, my)])
    g.label(370, R2 - 8, "SentenceSplitter", color=INK)
    # LengthFn: length 가 제공, chunker 가 요구
    g.path([(C, my), (700 + 8, my)])
    g.lollipop(700, my)
    g.socket(700, my, "right")
    g.path([(700 - 13, my), (B + W, my)])
    g.label(700, R2 - 8, "LengthFn", color=INK)

    # 내부 의존 (점선 화살표)
    g.path([(cx("cli") - 40, R1 + H), (cx("cli") - 40, 316), (B + 60, 316), (B + 60, R2)],
           dash=True, arrow=True)  # fmt: skip
    g.path([(A, R1 + H / 2), (62, R1 + H / 2), (62, R3 + H / 2), (B, R3 + H / 2)],
           dash=True, arrow=True)  # fmt: skip
    g.path([(cx("api"), R1 + H), (cx("api"), R2)], dash=True, arrow=True)
    g.path([(cx("lc") + 40, R1 + H), (cx("lc") + 40, 330), (B + W - 60, 330), (B + W - 60, R2)],
           dash=True, arrow=True)  # fmt: skip
    g.path([(cx("chunker"), R2 + H), (cx("chunker"), R3)], dash=True, arrow=True)
    g.path([(cx("parser"), R3 + H), (cx("parser"), R4)], dash=True, arrow=True)
    g.label(cx("chunker") + 26, R2 + H + 36, "«use»")
    g.label(cx("parser") + 26, R3 + H + 36, "«use»")
    g.label(98, R3 + H / 2 - 8, "«use» --tree", anchor="start")

    # 선택 의존성 (라이브러리)
    LY = 800
    libs = {
        "kiwi": (A, LY, W, "kiwipiepy"),
        "tiktoken": (C, LY, 150, "tiktoken"),
        "tokenizers": (C + 166, LY, 150, "tokenizers"),
    }
    for x, y, w, name in libs.values():
        g.component(x, y, w, 66, name, stereo="library", fill=FILL_EXT)
    g.component(1076, R1, 256, H, "langchain-text-splitters", "+ langchain-core",
                stereo="library", fill=FILL_EXT)  # fmt: skip

    g.path([(cx("sent"), R2 + H), (cx("sent"), LY)], dash=True, arrow=True)
    g.label(cx("sent"), 600, "«use» 함수 호출 시 import")
    g.path([(C + 75, R2 + H), (C + 75, LY)], dash=True, arrow=True)
    g.path([(C + 200, R2 + H), (C + 200, LY)], dash=True, arrow=True)
    g.label(C + 115, 600, "«use» 함수 호출 시 import")
    g.path([(C + W, R1 + H / 2), (1076, R1 + H / 2)], dash=True, arrow=True)
    g.label(1028, R1 + H / 2 - 10, "«use»")
    g.label(1028, R1 + H / 2 + 22, "import 시 필수")

    g.note(1080, 470, 240, [
        "핵심 계층(chunker · parser ·",
        "markers · sentences · length)은",
        "표준 라이브러리만 씁니다.",
        "«library» 는 pip extras 로",
        "선택 설치합니다.",
    ])  # fmt: skip
    g.path([(1080, 520), (C + W, R2 + H / 2 + 20)], dash=True)
    return g.save("component.svg")


# --- 배치 다이어그램 ---------------------------------------------------------------------


def deployment_diagram() -> Path:
    g = Svg(1360, 800, "jogak UML 배치 다이어그램")

    # 개발자 PC
    g.node(40, 60, 360, 270, "개발자 PC", stereo="device")
    g.node(
        60, 120, 310, 196, "Python 3.11+ (venv)", stereo="executionEnvironment", fill=FILL_IN, d=10
    )
    g.artifact(80, 176, 270, 60, "jogak 작업 트리", "src · tests · benchmark", stereo="source")
    g.artifact(80, 246, 270, 60, "benchmark/results/*.json", "벤치마크 결과", stereo="file")

    # GitHub
    g.node(500, 60, 360, 270, "GitHub", stereo="node")
    g.artifact(520, 116, 320, 60, "MSbtff/jogak", "main 브랜치 · v* 태그", stereo="repository")
    g.artifact(520, 186, 320, 60, "ci.yml", ".github/workflows", stereo="workflow")
    g.artifact(520, 256, 320, 60, "publish.yml", ".github/workflows", stereo="workflow")

    # GitHub Actions runner
    g.node(960, 60, 360, 270, "GitHub Actions 러너", stereo="node")
    g.text(972, 116, "ubuntu-latest", 11.5, color=INK_2)
    g.node(
        980, 140, 310, 170, "Python 3.11 ~ 3.14", stereo="executionEnvironment", fill=FILL_IN, d=10
    )
    g.text(992, 202, "기본 / 전체 extras 매트릭스", 11.5, color=INK_2)
    g.artifact(1000, 214, 270, 40, "jogak-0.1.0-py3-none-any.whl", stereo="wheel")
    g.artifact(1000, 262, 270, 40, "jogak-0.1.0.tar.gz", stereo="sdist")

    # PyPI
    g.node(960, 460, 360, 180, "PyPI (pypi.org)", stereo="node")
    g.artifact(980, 520, 320, 60, "jogak", "wheel · sdist", stereo="package")
    g.text(980, 606, "아직 배포 전 (Trusted Publisher 등록 필요)", 11.5, color="#9a6700")

    # 사용자 서버
    g.node(40, 460, 560, 290, "사용자 서버", stereo="device")
    g.node(60, 520, 510, 210, "Python 3.11+", stereo="executionEnvironment", fill=FILL_IN, d=10)
    g.artifact(80, 574, 220, 60, "jogak", "wheel", stereo="library")
    g.artifact(320, 574, 230, 60, "RAG 애플리케이션", "LangChain 등", stereo="application")
    g.artifact(80, 646, 470, 60, "kiwipiepy · tiktoken · tokenizers · langchain-text-splitters",
               "선택 설치 (pip extras)", stereo="library")  # fmt: skip

    # 벡터 DB
    g.node(680, 560, 200, 130, "벡터 DB", stereo="node")
    g.artifact(696, 614, 168, 60, "청크 임베딩", "path · start/end 메타", stereo="data")

    # 통신 경로
    g.path([(400, 195), (500, 195)], width=1.6)
    g.label(450, 186, "git push")
    g.label(450, 214, "«HTTPS»")
    g.path([(860, 195), (960, 195)], width=1.6)
    g.label(910, 186, "push · 태그")
    g.label(910, 214, "이벤트")
    g.path([(1140, 330), (1140, 460)], width=1.6)
    g.label(1132, 384, "«HTTPS» Trusted Publishing", anchor="end")
    g.label(1132, 404, "(OIDC, v* 태그일 때)", anchor="end")
    g.path([(600, 500), (960, 500)], width=1.6)
    g.label(780, 492, "pip install jogak[...]")
    g.label(780, 520, "«HTTPS»")
    g.path([(600, 625), (680, 625)], width=1.6)
    g.label(640, 616, "저장 · 검색")

    # 의존: 러너가 만든 wheel 이 PyPI 의 패키지로 올라감
    g.path([(1250, 302), (1250, 520)], dash=True, arrow=True)
    g.label(1252, 440, "«deploy»", anchor="start")
    return g.save("deployment.svg")


if __name__ == "__main__":
    for p in (component_diagram(), deployment_diagram()):
        print(p)
