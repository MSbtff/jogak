"""명령줄 도구: ``jogak 규정.txt --max-size 500``"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .chunker import Chunker
from .parser import parse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jogak", description="한국어 규정·법령·공문서를 구조에 맞춰 청크로 나눕니다."
    )
    parser.add_argument("file", nargs="?", default="-", help="입력 파일 (생략하거나 -면 표준 입력)")
    parser.add_argument("--max-size", type=int, default=800, help="청크 최대 글자 수 (기본 800)")
    parser.add_argument("--no-merge", action="store_true", help="장·조 단위를 서로 묶지 않음")
    parser.add_argument("--title", help="모든 청크 경로 앞에 붙일 문서 제목")
    parser.add_argument("--splitter", default="regex", help="문장 분리기: regex 또는 kiwi")
    parser.add_argument("--json", action="store_true", help="JSON Lines 로 출력")
    parser.add_argument("--tree", action="store_true", help="청크 대신 파싱한 구조 트리를 출력")
    parser.add_argument("--version", action="version", version=f"jogak {__version__}")
    args = parser.parse_args(argv)

    if args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()

    if args.tree:
        _print_tree(parse(text), text)
        return 0

    chunker = Chunker(args.max_size, merge=not args.no_merge, sentence_splitter=args.splitter)
    for c in chunker.chunk(text, title=args.title):
        if args.json:
            print(json.dumps(c.to_dict(), ensure_ascii=False))
        else:
            print(f"── #{c.index} [{c.context or '-'}] ({len(c.text)}자, {c.start}-{c.end})")
            print(c.text)
            print()
    return 0


def _print_tree(node, text: str, depth: int = 0) -> None:
    if node.kind != "document":
        body = " ".join(text[node.body_start : node.own_end].split())
        body = body if len(body) <= 50 else body[:49] + "…"
        print(f"{'  ' * depth}{node.label}  {body}".rstrip())
        depth += 1
    for child in node.children:
        _print_tree(child, text, depth)


if __name__ == "__main__":
    raise SystemExit(main())
