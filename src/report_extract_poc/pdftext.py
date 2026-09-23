"""PDF 에서 텍스트를 뽑는다. 리포트는 스캔본이 아니라 디지털 PDF 라 OCR 이 필요 없다."""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf


def page_texts(pdf_path: Path) -> list[str]:
    with pymupdf.open(pdf_path) as doc:
        return [p.get_text() for p in doc]


def flatten(text: str) -> str:
    """줄바꿈을 살린 채 연속 공백만 줄인다. 원본 위치를 크게 흔들지 않는다."""
    return re.sub(r"[ \t\u00a0]+", " ", text)


def excerpt(text: str, offset: int, width: int = 60) -> str:
    """추출한 값이 원본 어디에서 나왔는지 사람이 눈으로 볼 수 있게 주변을 잘라 준다."""
    a = max(0, offset - width // 3)
    b = min(len(text), offset + width)
    return text[a:b].replace("\n", "|").strip()
