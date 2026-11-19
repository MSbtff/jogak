"""벤치마크 결과(JSON)로 README 용 그래프를 그립니다.

사용법:
    pip install matplotlib
    python benchmark/plot.py [--size 800] [--out docs/benchmark.png]

benchmark/results/*.json 은 ``python benchmark/run.py ... --json`` 으로 만든 결과입니다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"

# (결과 파일, 패널 제목)
PANELS = (
    ("bge-m3.json", "임베딩 검색 · bge-m3"),
    ("multilingual-e5-small.json", "임베딩 검색 · e5-small"),
    ("bm25_kiwi.json", "키워드 검색 · BM25"),
)
# (run.py 의 방식 이름, 그래프에 쓸 이름)
SYSTEMS = (
    ("고정 길이 (10% 겹침)", "고정 길이"),
    ("LangChain Recursive (10% 겹침)", "LangChain Recursive"),
    ("jogak", "jogak"),
)

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
CONTEXT = "#b9b8b2"  # 비교 대상: 회색
ACCENT = "#2a78d6"  # jogak: 강조
KOREAN_FONTS = ["Apple SD Gothic Neo", "AppleGothic", "NanumGothic", "Noto Sans CJK KR",
                "Malgun Gothic", "DejaVu Sans"]  # fmt: skip


def load(size: int) -> list[tuple[str, list[tuple[str, float]]]]:
    panels = []
    for file, title in PANELS:
        path = RESULTS / file
        if not path.exists():
            continue
        rows = {
            r["system"]: r
            for r in json.loads(path.read_text(encoding="utf-8"))
            if r["size"] == size
        }
        panels.append((title, [(label, rows[key]["recall"]["1"]) for key, label in SYSTEMS]))
    return panels


def plot(size: int, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    fonts = [f for f in KOREAN_FONTS if f in installed] or ["DejaVu Sans"]
    plt.rcParams.update({"font.family": fonts, "font.size": 11, "text.color": TEXT})
    panels = load(size)
    fig, axes = plt.subplots(
        1, len(panels), figsize=(3.5 * len(panels), 2.5), sharey=True, facecolor=SURFACE
    )
    for ax, (title, bars) in zip(axes, panels, strict=True):
        labels = [b[0] for b in bars]
        values = [b[1] for b in bars]
        colors = [ACCENT if lbl == "jogak" else CONTEXT for lbl in labels]
        y = range(len(bars))
        ax.barh(y, values, height=0.55, color=colors, edgecolor=SURFACE, linewidth=2)
        for yi, v, lbl in zip(y, values, labels, strict=True):
            ax.text(
                v + 0.02, yi, f"{v:.2f}", va="center", fontsize=11,
                color=TEXT if lbl == "jogak" else TEXT_2,
                fontweight="bold" if lbl == "jogak" else "normal",
            )  # fmt: skip
        ax.set_title(title, fontsize=11, color=TEXT, loc="left", linespacing=1.25, pad=8)
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        ax.set_xticklabels(["0", "", "0.5", "", "1"], color=TEXT_2, fontsize=9)
        ax.set_yticks(list(y))
        ax.set_yticklabels(labels, color=TEXT)
        ax.invert_yaxis()
        ax.set_facecolor(SURFACE)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(length=0)
        for side in ("top", "right", "bottom"):
            ax.spines[side].set_visible(False)
        ax.spines["left"].set_color(TEXT_2)
    fig.suptitle(
        f"Recall@1 — 정답 조문이 검색 1위로 나온 비율  (청크 {size}자, 법률 3개, 질문 55개)",
        x=0.01, y=0.96, ha="left", fontsize=12.5, fontweight="bold", color=TEXT,
    )  # fmt: skip
    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.12, top=0.74, wspace=0.3)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    print(out)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--size", type=int, default=800)
    ap.add_argument("--out", type=Path, default=ROOT.parent / "docs" / "benchmark.png")
    args = ap.parse_args(argv)
    plot(args.size, args.out)


if __name__ == "__main__":
    main()
