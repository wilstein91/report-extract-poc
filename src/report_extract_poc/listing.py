"""후보 ⓪ — 한경 컨센서스 목록 페이지에서 얻은 값.

PDF 를 열지 않는다. AI 도 쓰지 않는다. 목록 표에 이미 적혀 있는 값을 그대로 쓴다.
얻을 수 있는 항목은 목표주가와 투자의견 둘뿐이다. 나머지는 빈칸으로 둔다.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

from .schema import Cell, Extraction

ROOT = Path(__file__).resolve().parents[2]
LIST_CSV = ROOT / "data" / "baseline" / "hankyung_list.csv"


def extract(file_id: str, filename: str, _pages: list[str]) -> Extraction:
    t0 = time.perf_counter()
    row = None
    with LIST_CSV.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["file_id"] == file_id:
                row = r
                break

    ex = Extraction(file_id=file_id, filename=filename, note="목록 표. PDF 를 열지 않음")
    if row:
        # 목록의 0 은 '목표주가 없음'을 뜻하는 표기다. 값 0 이 아니다.
        tp = "" if row["적정가격"].strip() in {"0", "", "-"} else row["적정가격"]
        ex.cells["목표주가"] = Cell(value=tp, evidence=f"목록 표 report_idx={row['report_idx']}")
        ex.cells["투자의견"] = Cell(value=row["투자의견"], evidence=f"목록 표 report_idx={row['report_idx']}")
    ex.elapsed_sec = time.perf_counter() - t0
    return ex
