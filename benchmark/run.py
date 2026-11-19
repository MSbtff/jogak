"""청킹 방식별 검색 성능(Recall@k, MRR)을 비교합니다.

사용법:
    pip install -e ".[kiwi,langchain]"
    python benchmark/run.py [--sizes 200 400 800] [--tokenizer kiwi|bigram] [--json out.json]

    # 임베딩 검색 (pip install sentence-transformers)
    python benchmark/run.py --dense intfloat/multilingual-e5-small

방법:
    1. benchmark/data/*.txt (법률 3개)를 청킹 방식마다 잘라 하나의 색인으로 합칩니다.
    2. benchmark/questions.jsonl 의 질문마다 BM25 (또는 --dense 임베딩 모델)로 상위 청크를
       찾습니다.
    3. 정답 근거 문장(evidence)이 원문에 딱 한 번 나오는지 먼저 확인하고,
       그 구간을 통째로 담은 청크가 상위 k 개 안에 있으면 맞힌 것으로 칩니다.
    4. 같은 글자 예산(--budget, 기본 2,000자) 안에 들어가는 상위 청크만 LLM 에 넣는다고 보고
       그 안에서 맞힌 비율도 셉니다. 청크 길이가 서로 달라도 공정하게 비교하기 위해서입니다.
    5. 청크가 조·항·호 같은 구조 경계에서 시작하는 비율도 셉니다 (경계는 jogak.parse 기준).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
QUESTIONS = ROOT / "questions.jsonl"
KS = (1, 3, 5, 10)
sys.path.insert(0, str(ROOT.parent / "src"))  # 설치하지 않고 저장소에서 바로 실행할 때


# --- 데이터 --------------------------------------------------------------------


@dataclass(frozen=True)
class Doc:
    name: str
    text: str


@dataclass(frozen=True)
class Question:
    id: str
    law: str
    ref: str
    question: str
    evidence: str
    start: int = -1
    end: int = -1


def load_docs() -> dict[str, Doc]:
    docs = {}
    for path in sorted(DATA_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        if text.startswith("<!--"):  # 출처 주석 줄은 색인하지 않습니다
            text = text.split("\n", 1)[1]
        docs[path.stem] = Doc(path.stem, text)
    return docs


def load_questions(docs: dict[str, Doc]) -> list[Question]:
    out = []
    for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        text = docs[q["law"]].text
        n = text.count(q["evidence"])
        if n != 1:
            raise SystemExit(
                f"{q['id']}: 근거 문장이 {n}번 나옵니다 (1번이어야 함): {q['evidence']}"
            )
        start = text.index(q["evidence"])
        out.append(Question(**q, start=start, end=start + len(q["evidence"])))
    return out


# --- 청킹 방식 -------------------------------------------------------------------


@dataclass(frozen=True)
class Piece:
    doc: str
    start: int
    end: int
    index_text: str  # 실제로 색인되는 텍스트 (경로 문맥 포함 여부에 따라 다름)


Splitter = Callable[[Doc, int], list[Piece]]


def fixed_window(doc: Doc, size: int) -> list[Piece]:
    """글자 수로 자르고 10% 겹침."""
    step = size - size // 10
    out = []
    for s in range(0, len(doc.text), step):
        e = min(s + size, len(doc.text))
        out.append(Piece(doc.name, s, e, doc.text[s:e]))
        if e == len(doc.text):
            break
    return out


def langchain_recursive(doc: Doc, size: int) -> list[Piece]:
    """LangChain RecursiveCharacterTextSplitter (기본 구분자, 10% 겹침)."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=size // 10, add_start_index=True
    )
    out = []
    for d in splitter.create_documents([doc.text]):
        s = d.metadata["start_index"]
        if s < 0 or doc.text[s : s + len(d.page_content)] != d.page_content:
            raise AssertionError("start_index 가 원문과 맞지 않습니다")
        out.append(Piece(doc.name, s, s + len(d.page_content), d.page_content))
    return out


def jogak_splitter(*, merge: bool, context: bool) -> Splitter:
    def split(doc: Doc, size: int) -> list[Piece]:
        from jogak import Chunker

        chunks = Chunker(max_size=size, merge=merge).chunk(doc.text)
        return [
            Piece(doc.name, c.start, c.end, c.embed_text if context else c.text) for c in chunks
        ]

    return split


SYSTEMS: dict[str, Splitter] = {
    "고정 길이 (10% 겹침)": fixed_window,
    "LangChain Recursive (10% 겹침)": langchain_recursive,
    "jogak": jogak_splitter(merge=True, context=True),
    "jogak (경로 문맥 없이)": jogak_splitter(merge=True, context=False),
    "jogak merge=False": jogak_splitter(merge=False, context=True),
}


# --- 검색 (BM25) ------------------------------------------------------------------

_KIWI_TAGS = ("NNG", "NNP", "NR", "SL", "SN", "SH", "XR", "VV", "VA")


def kiwi_tokenizer() -> Callable[[Sequence[str]], list[list[str]]]:
    from kiwipiepy import Kiwi

    kiwi = Kiwi()

    def tokenize(texts: Sequence[str]) -> list[list[str]]:
        return [
            [t.form for t in toks if t.tag.startswith(_KIWI_TAGS)] for toks in kiwi.tokenize(texts)
        ]

    return tokenize


def bigram_tokenizer() -> Callable[[Sequence[str]], list[list[str]]]:
    def tokenize(texts: Sequence[str]) -> list[list[str]]:
        out = []
        for text in texts:
            grams = []
            for word in text.split():
                grams += [word[i : i + 2] for i in range(max(1, len(word) - 1))]
            out.append(grams)
        return out

    return tokenize


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = sum(self.len) / len(docs)
        df = Counter(t for d in self.tf for t in d)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: list[str], k: int) -> list[int]:
        scores = []
        for i, tf in enumerate(self.tf):
            norm = self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)
            s = 0.0
            for t in query:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            scores.append(s)
        return sorted(range(len(scores)), key=lambda i: -scores[i])[:k]


# --- 검색 (임베딩) -----------------------------------------------------------------

Search = Callable[[int], list[int]]  # 질문 번호 → 관련도 순 청크 번호
Retriever = Callable[[list[str]], Search]  # 색인할 텍스트들 → Search


def bm25_retriever(
    questions: list[Question], tokenize: Callable[[Sequence[str]], list[list[str]]]
) -> Retriever:
    q_tokens = tokenize([q.question for q in questions])

    def build(texts: list[str]) -> Search:
        index = BM25(tokenize(texts))
        return lambda qi: index.search(q_tokens[qi], len(texts))

    return build


def dense_retriever(questions: list[Question], model_name: str) -> Retriever:
    """sentence-transformers 모델로 코사인 유사도 검색. 같은 텍스트의 임베딩은 재사용합니다."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    e5 = "e5" in model_name.lower()  # E5 계열은 "query: " / "passage: " 접두어가 필요
    q_vecs = model.encode(
        [("query: " if e5 else "") + q.question for q in questions], normalize_embeddings=True
    )
    cache: dict[str, np.ndarray] = {}

    def build(texts: list[str]) -> Search:
        new = list(dict.fromkeys(t for t in texts if t not in cache))
        if new:
            vecs = model.encode(
                [("passage: " if e5 else "") + t for t in new],
                normalize_embeddings=True,
                batch_size=32,
            )
            cache.update(zip(new, vecs, strict=True))
        matrix = np.stack([cache[t] for t in texts])
        return lambda qi: list(np.argsort(-(matrix @ q_vecs[qi])))

    return build


# --- 평가 --------------------------------------------------------------------------


@dataclass
class Result:
    system: str
    size: int
    n_chunks: int
    avg_len: float
    recall: dict[int, float]
    mrr: float
    budget_recall: float
    boundary_start: float
    first_hit: dict[str, int | None]  # 질문 id → 처음 맞힌 순위 (없으면 None)


def evaluate(
    name: str,
    split: Splitter,
    size: int,
    docs: dict[str, Doc],
    questions: list[Question],
    retriever: Retriever,
    budget: int,
    boundaries: dict[str, set[int]],
) -> Result:
    pieces = [p for d in docs.values() for p in split(d, size)]
    search = retriever([p.index_text for p in pieces])
    depth = max(KS)
    hits: dict[int, int] = Counter()
    rr = 0.0
    budget_hits = 0
    first_hit = {}
    for qi, q in enumerate(questions):
        ranked = search(qi)

        def contains(i: int, q: Question = q) -> bool:
            p = pieces[i]
            return p.doc == q.law and p.start <= q.start and q.end <= p.end

        rank = next((r for r, i in enumerate(ranked[:depth], 1) if contains(i)), None)
        first_hit[q.id] = rank
        used = 0
        for i in ranked:
            used += len(pieces[i].index_text)
            if used > budget:
                break
            if contains(i):
                budget_hits += 1
                break
        if rank:
            rr += 1 / rank
            for k in KS:
                if rank <= k:
                    hits[k] += 1
    n = len(questions)
    return Result(
        system=name,
        size=size,
        n_chunks=len(pieces),
        avg_len=sum(len(p.index_text) for p in pieces) / len(pieces),
        recall={k: hits[k] / n for k in KS},
        mrr=rr / n,
        budget_recall=budget_hits / n,
        boundary_start=sum(
            _skip_space(docs[p.doc].text, p.start) in boundaries[p.doc] for p in pieces
        )
        / len(pieces),
        first_hit=first_hit,
    )


def _skip_space(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def structure_boundaries(doc: Doc) -> set[int]:
    from jogak import parse

    return {n.start for n in parse(doc.text).walk() if n.kind != "document"}


def to_markdown(results: list[Result], budget: int) -> str:
    lines = []
    for size in sorted({r.size for r in results}):
        lines += [
            f"\n**max_size = {size}자**\n",
            "| 방식 | 청크 수 | 평균 길이 | 경계 시작 | "
            + " | ".join(f"R@{k}" for k in KS)
            + f" | MRR@10 | R@{budget:,}자 |",
            "|---|---:|---:|---:|" + "---:|" * len(KS) + "---:|---:|",
        ]
        for r in (r for r in results if r.size == size):
            lines.append(
                f"| {r.system} | {r.n_chunks} | {r.avg_len:.0f} | {r.boundary_start:.0%} | "
                + " | ".join(f"{r.recall[k]:.2f}" for k in KS)
                + f" | {r.mrr:.3f} | {r.budget_recall:.2f} |"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sizes", type=int, nargs="+", default=[200, 400, 800])
    ap.add_argument("--tokenizer", choices=["kiwi", "bigram"], default="kiwi", help="BM25 토큰화")
    ap.add_argument("--dense", metavar="MODEL", help="BM25 대신 이 임베딩 모델로 검색")
    ap.add_argument("--budget", type=int, default=2000, help="LLM 에 넣을 글자 예산")
    ap.add_argument("--json", type=Path, help="질문별 결과까지 JSON 으로 저장")
    args = ap.parse_args(argv)

    docs = load_docs()
    questions = load_questions(docs)
    if args.dense:
        retriever = dense_retriever(questions, args.dense)
        how = f"임베딩 {args.dense}"
    else:
        tokenize = kiwi_tokenizer() if args.tokenizer == "kiwi" else bigram_tokenizer()
        retriever = bm25_retriever(questions, tokenize)
        how = f"BM25 + {args.tokenizer}"

    print(
        f"법령 {len(docs)}개 ({sum(len(d.text) for d in docs.values()):,}자), "
        f"질문 {len(questions)}개, 검색: {how}",
        file=sys.stderr,
    )
    boundaries = {name: structure_boundaries(d) for name, d in docs.items()}
    results = [
        evaluate(name, split, size, docs, questions, retriever, args.budget, boundaries)
        for size in args.sizes
        for name, split in SYSTEMS.items()
    ]
    print(to_markdown(results, args.budget))
    if args.json:
        args.json.write_text(
            json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
