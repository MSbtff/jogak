"""선택 의존성이 없으면 해당 모듈은 doctest 수집에서 뺍니다."""

import importlib.util

collect_ignore = []
if importlib.util.find_spec("langchain_text_splitters") is None:
    collect_ignore.append("src/jogak/langchain.py")
