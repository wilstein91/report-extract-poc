"""후보 ① — 기준선. PyMuPDF 텍스트 + 규칙. AI 를 쓰지 않는다.

판정에 쓰는 값은 코드에 박지 않고 Config 로 받는다.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .pdftext import excerpt, flatten
from .schema import Cell, Extraction

# 목표주가로 쓰이는 라벨. 증권사마다 다르다.
TARGET_LABELS = ["목표주가", "적정주가", "목표가", "적정가격", "Target Price", "TP"]
# 현재주가로 쓰이는 라벨.
PRICE_LABELS = ["현재주가", "현재 주가", "전일종가", "종가", "주가"]
# 값 탐색을 여기서 끊는다. 다른 항목의 숫자를 집어오지 않게 한다.
STOP_LABELS = ["현재주가", "현재 주가", "종가", "상승여력", "시가총액", "직전", "52주", "발행주식"]
# 라벨 앞에 이 말이 붙으면 그 자리는 건너뛴다.
SKIP_PREFIXES = ["직전", "전일", "기존", "종전"]
# 투자의견 표기. 원문 그대로 담고, 비교할 때만 대소문자를 무시한다.
OPINION_PATTERNS = [
    r"Not\s*Rated", r"N\.R\.?", r"투자의견\s*없음", r"\bNR\b",
    r"매수", r"중립", r"매도", r"비중확대", r"비중축소",
    r"BUY", r"HOLD", r"SELL", r"Buy", r"Hold", r"Sell", r"Neutral",
]
# 네 자리 이상이거나 천 단위 쉼표가 있는 수만 값으로 본다.
# (12개월) (9/21) 같은 괄호 안 숫자를 값으로 읽지 않기 위한 것이다.
NUMBER_RE = r"\d{1,3}(?:,\d{3})+|\d{4,}"
# 종가(2026.09.18) 의 2026 처럼 뒤에 .09 가 붙는 수는 날짜의 일부다.
DATE_TAIL_RE = r"\s*[.\-/]\s*\d{1,2}"

HOUSES = [
    "LS증권", "SK증권", "유안타증권", "한화투자증권", "메리츠증권", "iM증권",
    "상상인증권", "대신증권", "유진투자증권", "한국IR협의회", "한국투자증권",
    "삼성증권", "NH투자증권", "미래에셋증권", "키움증권", "신한투자증권", "하나증권",
]


@dataclass
class Config:
    """판정에 쓰는 값. 전부 인자로 받는다."""

    search_window: int = 60          # 라벨 뒤 몇 글자까지 값을 찾을지
    pages: int = 1                   # 항목을 찾을 때 앞에서 몇 페이지를 볼지
    target_labels: list[str] = field(default_factory=lambda: list(TARGET_LABELS))
    price_labels: list[str] = field(default_factory=lambda: list(PRICE_LABELS))
    stop_labels: list[str] = field(default_factory=lambda: list(STOP_LABELS))


def _find_labeled_number(text: str, labels: list[str], cfg: Config) -> tuple[str, int, str]:
    for label in labels:
        for m in re.finditer(re.escape(label), text):
            head = text[max(0, m.start() - 6):m.start()]
            if any(p in head for p in SKIP_PREFIXES):
                continue

            seg = text[m.end():m.end() + cfg.search_window]
            cut = len(seg)
            for stop in cfg.stop_labels:
                i = seg.find(stop)
                if 0 <= i < cut:
                    cut = i
            seg = seg[:cut]

            for n in re.finditer(NUMBER_RE, seg):
                if re.match(DATE_TAIL_RE, seg[n.end():n.end() + 4]):
                    continue
                return n.group(), m.end() + n.start(), excerpt(text, m.start())
    return "", -1, ""


def extract(file_id: str, filename: str, pages: list[str], cfg: Config | None = None) -> Extraction:
    cfg = cfg or Config()
    t0 = time.perf_counter()
    text = flatten("\n".join(pages[: cfg.pages]))
    whole = flatten("\n".join(pages))
    ex = Extraction(
        file_id=file_id, filename=filename,
        note=f"규칙 · window={cfg.search_window} pages={cfg.pages}",
    )

    def put(name: str, value: str, off: int, ev: str):
        ex.cells[name] = Cell(
            value=value,
            page=1 if off >= 0 else None,
            char_offset=off if off >= 0 else None,
            evidence=ev,
        )

    v, off, ev = _find_labeled_number(text, cfg.target_labels, cfg)
    put("목표주가", v, off, ev)

    v, off, ev = _find_labeled_number(text, cfg.price_labels, cfg)
    put("현재주가", v, off, ev)

    m = re.search("|".join(OPINION_PATTERNS), text)
    put("투자의견", m.group() if m else "", m.start() if m else -1,
        excerpt(text, m.start()) if m else "")

    # 종목명 — 종목코드가 있는 줄에서 코드 바로 앞 이름만 집는다.
    name, name_off, pos = "", -1, 0
    for line in text.split("\n"):
        lm = re.search(r"([가-힣A-Za-z][가-힣A-Za-z0-9&.]*(?:\s[가-힣A-Za-z0-9&.]+)?)\s*\(\s*\d{6}\s*\)", line)
        if lm:
            name, name_off = lm.group(1).strip(), pos + lm.start(1)
            break
        pos += len(line) + 1
    put("종목명", name, name_off, excerpt(text, name_off) if name_off >= 0 else "")

    m = re.search(r"(20\d{2}|\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", text)
    put("작성일", m.group() if m else "", m.start() if m else -1,
        excerpt(text, m.start()) if m else "")

    # 증권사는 첫 페이지에 없는 경우가 많다. 문서 전체에서 찾는다.
    hm = next((re.search(re.escape(h), whole) for h in HOUSES if re.search(re.escape(h), whole)), None)
    put("증권사", hm.group() if hm else "", -1, excerpt(whole, hm.start()) if hm else "")

    # 영업이익 추정치 — 실적 표의 당해연도 열. 규칙으로 열을 짚을 방법이 없어 비워 둔다.
    put("영업이익추정치_당해", "", -1, "")

    ex.elapsed_sec = time.perf_counter() - t0
    return ex
