"""청크 크기를 토큰 수로 재는 길이 함수들. 각각 선택 의존성이 필요합니다."""

from __future__ import annotations

from collections.abc import Callable


def tiktoken_length(encoding: str = "cl100k_base") -> Callable[[str], int]:
    """OpenAI tiktoken 인코딩 기준 토큰 수. ``pip install 'jogak[tiktoken]'``"""
    try:
        import tiktoken
    except ImportError as e:  # pragma: no cover
        raise ImportError("tiktoken_length needs tiktoken: pip install 'jogak[tiktoken]'") from e
    enc = tiktoken.get_encoding(encoding)
    return lambda text: len(enc.encode(text, disallowed_special=()))


def hf_length(model: str) -> Callable[[str], int]:
    """Hugging Face 토크나이저 기준 토큰 수 (임베딩 모델과 맞출 때).

    ``pip install 'jogak[hf]'`` 가 필요하며, 처음 호출 시 토크나이저를 내려받습니다.
    """
    try:
        from tokenizers import Tokenizer
    except ImportError as e:  # pragma: no cover
        raise ImportError("hf_length needs tokenizers: pip install 'jogak[hf]'") from e
    tok = Tokenizer.from_pretrained(model)
    return lambda text: len(tok.encode(text, add_special_tokens=False).ids)
