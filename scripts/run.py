"""후보 하나를 10건에 돌리고 결과를 results/runs 아래 새 폴더에 남긴다.

    uv run python scripts/run.py --candidate rules
    uv run python scripts/run.py --candidate llm --model gemma4:e4b

실행할 때마다 새 폴더를 만든다. 이전 결과를 덮어쓰지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.report_extract_poc import listing, llm, pdftext, rules  # noqa: E402
from src.report_extract_poc.schema import FIELDS  # noqa: E402

REPORTS = ROOT / "data" / "reports"
RUNS = ROOT / "results" / "runs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", choices=["list", "rules", "llm"], required=True)
    ap.add_argument("--model", default="qwen3.5:0.8b", help="llm 후보가 쓸 모델")
    ap.add_argument("--pages", type=int, default=1, help="앞에서 몇 페이지를 볼지")
    ap.add_argument("--window", type=int, default=60, help="규칙 후보의 라벨 뒤 탐색 폭")
    ap.add_argument("--year", type=int, default=2026, help="당해연도 추정치의 연도")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--tag", default="", help="폴더 이름에 붙일 꼬리표")
    args = ap.parse_args()

    if args.candidate == "list":
        run = lambda fid, name, pages: listing.extract(fid, name, pages)
        label = "list"
    elif args.candidate == "rules":
        cfg = rules.Config(search_window=args.window, pages=args.pages)
        run = lambda fid, name, pages: rules.extract(fid, name, pages, cfg)
        label = "rules"
    else:
        cfg = llm.Config(model=args.model, pages=args.pages, year=args.year,
                         temperature=args.temperature)
        run = lambda fid, name, pages: llm.extract(fid, name, pages, cfg)
        label = "llm_" + args.model.replace(":", "-").replace("/", "-")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = RUNS / f"{stamp}_{label}{('_' + args.tag) if args.tag else ''}"
    outdir.mkdir(parents=True, exist_ok=False)

    rows, ev_lines, total = [], [], 0.0
    for pdf in sorted(REPORTS.glob("*.pdf")):
        fid = pdf.name.split("_")[0]
        ex = run(fid, pdf.name, pdftext.page_texts(pdf))
        total += ex.elapsed_sec

        row = {"file_id": fid, "파일명": pdf.name, "소요초": f"{ex.elapsed_sec:.3f}"}
        for f in FIELDS:
            c = ex.get(f)
            row[f] = c.value
            # 점수는 반올림하지 않고 그대로 남긴다.
            row[f + "__conf"] = "" if c.confidence is None else repr(c.confidence)
            row[f + "__pos"] = "" if c.char_offset is None else str(c.char_offset)
        rows.append(row)

        ev_lines.append(f"## {fid} · {pdf.name}\n\n`{ex.note}` · {ex.elapsed_sec:.2f}s\n")
        ev_lines.append("| 항목 | 값 | 원문 근거 | 위치 | conf |")
        ev_lines.append("|---|---|---|---|---|")
        for f in FIELDS:
            c = ex.get(f)
            v = c.value or "*(빈칸)*"
            e = (c.evidence or "").replace("|", "\|") or "—"
            ev_lines.append(f"| {f} | {v} | {e} | {c.char_offset if c.char_offset is not None else '—'} | {'' if c.confidence is None else c.confidence} |")
        ev_lines.append("")
        print(f"  {fid} {ex.elapsed_sec:6.2f}s", flush=True)

    with (outdir / "output.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 눈으로 확인할 수 있는 형태. 숫자만 보면 값이 엉뚱한 자리에서 온 것을 놓친다.
    (outdir / "evidence.md").write_text(
        f"# {label} 근거 대조표\n\n생성 {stamp}\n\n" + "\n".join(ev_lines),
        encoding="utf-8",
    )
    (outdir / "meta.json").write_text(
        json.dumps({
            "candidate": args.candidate, "label": label, "model": args.model,
            "pages": args.pages, "window": args.window, "year": args.year,
            "temperature": args.temperature, "n": len(rows),
            "total_sec": total, "mean_sec": total / len(rows), "stamp": stamp,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n{outdir.name}  ({len(rows)}건, 평균 {total / len(rows):.2f}s)")


if __name__ == "__main__":
    main()
