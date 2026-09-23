"""results/runs 아래 실행 결과를 정답표와 대조해 채점한다.

    uv run python scripts/score.py

채점 규칙은 src/report_extract_poc/schema.py 에 있고, 모델을 돌리기 전에 정했다.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.report_extract_poc.schema import FIELDS, normalize  # noqa: E402

TRUTH = ROOT / "data" / "truth" / "ground_truth.csv"
RUNS = ROOT / "results" / "runs"
OUT = ROOT / "results" / "score.md"

# 성공 기준 ③ 을 채점할 자리. 리포트에 값이 없으므로 빈칸이어야 한다.
MUST_BE_BLANK = {("09", "목표주가"), ("09", "투자의견"),
                 ("10", "목표주가"), ("10", "투자의견")}


def read_csv(p: Path) -> dict[str, dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return {r["file_id"]: r for r in csv.DictReader(f)}


def score_run(rundir: Path, truth: dict[str, dict]) -> dict:
    meta = json.loads((rundir / "meta.json").read_text(encoding="utf-8"))
    got = read_csv(rundir / "output.csv")

    cells = wrong = attempted = grounded = 0
    errors, blank_ok = [], 0
    for fid, t in truth.items():
        g = got.get(fid, {})
        for f in FIELDS:
            exp, act = normalize(f, t.get(f)), normalize(f, g.get(f))
            cells += 1
            if act:
                attempted += 1
            if g.get(f + "__pos"):
                grounded += 1
            if exp != act:
                wrong += 1
                errors.append({
                    "file_id": fid, "항목": f,
                    "정답": t.get(f, "") or "(빈칸)",
                    "낸 값": g.get(f, "") or "(빈칸)",
                    "종류": "지어냄" if not exp and act else ("놓침" if exp and not act else "다름"),
                })
            if (fid, f) in MUST_BE_BLANK and not act:
                blank_ok += 1

    return {
        "label": meta["label"], "dir": rundir.name, "meta": meta,
        "cells": cells, "wrong": wrong, "right": cells - wrong,
        "attempted": attempted, "grounded": grounded,
        "blank_ok": blank_ok, "blank_total": len(MUST_BE_BLANK),
        "errors": errors,
    }


def main():
    truth = read_csv(TRUTH)
    runs = sorted(d for d in RUNS.iterdir() if d.is_dir() and (d / "meta.json").exists())
    if not runs:
        raise SystemExit("실행 결과가 없습니다. scripts/run.py 를 먼저 돌리세요.")

    # 같은 label 은 가장 최근 것만 쓴다.
    latest = {}
    for d in runs:
        latest[json.loads((d / "meta.json").read_text(encoding="utf-8"))["label"]] = d
    results = [score_run(d, truth) for d in latest.values()]
    results.sort(key=lambda r: r["wrong"])

    L = ["# 채점 결과", "",
         "성공 기준 (모델을 돌리기 전에 적음)", "",
         "```",
         "① 70개 중 오류 3개 이하",
         "② 모든 값에 원본 위치가 붙어 검산할 수 있다",
         "③ 없는 항목은 빈칸으로 두고 지어내지 않는다",
         "```", "",
         "| 후보 | 맞음 | 틀림 | ①통과 | ②위치있음 | ③빈칸 | 건당 초 |",
         "|---|---:|---:|:---:|---:|:---:|---:|"]
    for r in results:
        ok1 = "✅" if r["wrong"] <= 3 else "❌"
        ok3 = "✅" if r["blank_ok"] == r["blank_total"] else f"❌ {r['blank_ok']}/{r['blank_total']}"
        L.append(f"| {r['label']} | {r['right']}/{r['cells']} | {r['wrong']} | {ok1} "
                 f"| {r['grounded']}/{r['attempted']} | {ok3} | {r['meta']['mean_sec']:.2f} |")

    L += ["", "> ②의 분모는 값을 낸 칸 수다. 빈칸으로 둔 자리는 위치가 없는 것이 맞다.", ""]

    # 항목별로 어느 후보가 되는지
    L += ["## 항목별 정답 수", "", "| 항목 | " + " | ".join(r["label"] for r in results) + " |",
          "|---|" + "---:|" * len(results)]
    for f in FIELDS:
        cnt = []
        for r in results:
            miss = sum(1 for e in r["errors"] if e["항목"] == f)
            cnt.append(f"{len(truth) - miss}/{len(truth)}")
        L.append(f"| {f} | " + " | ".join(cnt) + " |")

    for r in results:
        L += ["", f"## 틀린 자리 — {r['label']} ({r['wrong']}개)", ""]
        if not r["errors"]:
            L.append("없음")
            continue
        L += ["| file_id | 항목 | 정답 | 낸 값 | 종류 |", "|---|---|---|---|---|"]
        for e in r["errors"]:
            L.append(f"| {e['file_id']} | {e['항목']} | {e['정답']} | {e['낸 값']} | {e['종류']} |")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"채점표: {OUT}")
    for r in results:
        print(f"  {r['label']:22} 틀림 {r['wrong']:2d}/{r['cells']}  "
              f"빈칸 {r['blank_ok']}/{r['blank_total']}  {r['meta']['mean_sec']:.2f}s")


if __name__ == "__main__":
    main()
