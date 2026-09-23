"""추출 항목의 정의와 채점 규칙.

채점 규칙은 모델을 돌리기 전에 정한다. 결과를 보고 규칙을 바꾸면 채점이 성립하지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 추출할 일곱 항목. 정답표(data/truth/ground_truth.csv)의 열 이름과 같다.
FIELDS = [
    "종목명",
    "증권사",
    "작성일",
    "투자의견",
    "목표주가",
    "현재주가",
    "영업이익추정치_당해",
]

# 숫자로 비교하는 항목. 나머지는 글자로 비교한다.
NUMERIC_FIELDS = {"목표주가", "현재주가", "영업이익추정치_당해"}

# 값이 없음을 뜻하는 표기. 빈 문자열로 정규화한다.
# "없다"와 "0"은 다른 답이므로 0 을 여기에 넣지 않는다.
NULL_TOKENS = {"", "-", "–", "—", "n/a", "na", "none", "null", "없음", "해당없음"}


def normalize(field: str, value) -> str:
    """비교 직전에만 쓰는 정규화. 원본 값은 그대로 저장해 둔다."""
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in NULL_TOKENS:
        return ""

    if field in NUMERIC_FIELDS:
        # 쉼표·공백·단위를 떼고 숫자만 남긴다. 235,000원 == 235000
        s = re.sub(r"[,\s]", "", s)
        s = re.sub(r"(원|won|KRW)$", "", s, flags=re.I)
        m = re.fullmatch(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return s  # 숫자로 읽히지 않으면 원문 그대로 두고 불일치 처리
        f = float(s)
        return str(int(f)) if f == int(f) else str(f)

    if field == "작성일":
        # 2026. 9. 22 / 2026-09-22 / 26.09.22 / 20260922 를 모두 YYYYMMDD 로 맞춘다.
        m = re.search(r"(\d{2,4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", s)
        if m:
            y, mo, d = m.groups()
            y = y if len(y) == 4 else f"20{y}"
            return f"{y}{int(mo):02d}{int(d):02d}"
        digits = re.sub(r"\D", "", s)
        return digits if len(digits) == 8 else s

    if field == "투자의견":
        # 대소문자와 공백만 무시한다. Buy 와 매수는 서로 다른 답으로 둔다.
        # 표기를 통일하려면 매핑 규칙을 따로 만들고 그 규칙을 따로 검증해야 한다.
        return re.sub(r"\s", "", s).lower()

    return re.sub(r"\s+", " ", s)


@dataclass
class Cell:
    """항목 하나의 추출 결과.

    evidence 는 이 값이 원본 텍스트 어디에서 나왔는지를 사람이 눈으로 확인하기 위한 것이다.
    숫자만 보고 판단하면 값이 의도한 것을 재고 있지 않은 경우를 놓친다.
    """

    value: str = ""
    page: int | None = None
    char_offset: int | None = None
    evidence: str = ""
    confidence: float | None = None  # 반올림하지 않고 그대로 저장한다


@dataclass
class Extraction:
    file_id: str
    filename: str
    cells: dict[str, Cell] = field(default_factory=dict)
    elapsed_sec: float = 0.0
    note: str = ""

    def get(self, name: str) -> Cell:
        return self.cells.get(name, Cell())
