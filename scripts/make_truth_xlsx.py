"""정답표를 손으로 채우기 위한 엑셀 파일을 만든다.

정답은 사람이 PDF 원본을 보고 직접 적는다. 모델을 돌리기 전에 적어야 한다.
채우고 나면 scripts/xlsx_to_csv.py 로 data/truth/ground_truth.csv 에 옮긴다.

    uv run python scripts/make_truth_xlsx.py
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "data" / "reports"
OUT = ROOT / "data" / "truth" / "ground_truth_작성용.xlsx"

COLS = [
    ("file_id", 8),
    ("파일명", 38),
    ("종목명", 16),
    ("증권사", 14),
    ("작성일", 12),
    ("투자의견", 12),
    ("목표주가", 12),
    ("현재주가", 12),
    ("영업이익추정치_당해", 20),
    ("기입소요초", 11),
    ("비고", 30),
]

# 목표주가·투자의견이 없는 리포트. 해당 칸은 반드시 빈칸으로 남긴다.
NO_TARGET = {"09", "10"}


def main():
    pdfs = sorted(p.name for p in REPORTS.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"PDF가 없습니다: {REPORTS}")

    wb = Workbook()
    ws = wb.active
    ws.title = "정답표"

    header_fill = PatternFill("solid", fgColor="1F3864")
    warn_fill = PatternFill("solid", fgColor="FFF2CC")

    ws.append([c[0] for c in COLS])
    for i, (name, width) in enumerate(COLS, start=1):
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = width

    for name in pdfs:
        fid = name.split("_")[0]
        note = ""
        if fid in NO_TARGET:
            note = "목표주가·투자의견 없음 → 두 칸은 반드시 빈칸으로"
        ws.append([fid, name, "", "", "", "", "", "", "", "", note])
        if fid in NO_TARGET:
            for col in range(1, len(COLS) + 1):
                ws.cell(row=ws.max_row, column=col).fill = warn_fill

    ws.freeze_panes = "C2"

    # 숫자 칸은 문자열로 두어 엑셀이 앞자리 0을 지우거나 날짜로 바꾸지 않게 한다.
    for row in ws.iter_rows(min_row=2, min_col=1, max_col=1):
        for cell in row:
            cell.number_format = "@"

    guide = wb.create_sheet("작성 안내")
    for line in [
        ["정답표 작성 안내"],
        [],
        ["1. data/reports 폴더의 PDF를 하나씩 열고, 눈으로 보고 손으로 적습니다."],
        ["2. 한 건 시작할 때 시계를 보고, 끝나면 걸린 초를 기입소요초에 적습니다."],
        ["   → 이 값이 '지금 사람이 하는 수준'이고, 성공 기준 숫자의 근거가 됩니다."],
        [],
        ["어디서 찾나"],
        ["  종목명·증권사·작성일        리포트 첫 장 머리"],
        ["  투자의견·목표주가·현재주가  첫 장 오른쪽 박스에 대부분 모여 있음"],
        ["  영업이익추정치_당해         실적 표의 2026E 열, 영업이익 행"],
        [],
        ["주의"],
        ["  09번과 10번은 목표주가·투자의견이 없는 리포트입니다."],
        ["  그 칸은 반드시 빈칸으로 두세요. 0 이나 - 를 적으면 안 됩니다."],
        ["  이 두 건이 '없는 것을 없다고 답하는가'를 채점하는 자료입니다."],
        [],
        ["  투자의견은 원문 그대로 적습니다. Buy 를 매수로 바꾸지 않습니다."],
        ["  목표주가는 숫자만 적어도 되고 235,000 처럼 적어도 됩니다. 채점 때 쉼표를 뗍니다."],
    ]:
        guide.append(line)
    guide.column_dimensions["A"].width = 90
    guide["A1"].font = Font(bold=True, size=14)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"만들었습니다: {OUT}  ({len(pdfs)}건)")


if __name__ == "__main__":
    main()
