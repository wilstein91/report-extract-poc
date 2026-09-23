"""후보 ② — 노트북에서 도는 언어 모델(Ollama). 자료를 외부로 보내지 않는다.

모델에게 항목을 채우게 하되, 두 가지를 반드시 함께 요구한다.
  - 리포트에 없으면 빈 문자열로 둘 것 (없다고 답할 수 있어야 한다)
  - 각 값의 근거가 된 원문 조각을 함께 낼 것 (눈으로 검산할 수 있어야 한다)
근거 조각이 실제 원문에 있는지는 코드가 따로 대조한다. 없으면 지어낸 값이다.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass

from .pdftext import flatten
from .schema import FIELDS, Cell, Extraction

OLLAMA_URL = "http://localhost:11434/api/generate"

PROMPT = """너는 증권사 리포트에서 정해진 항목만 뽑아내는 도구다.

아래는 리포트 첫 페이지 텍스트다.

<리포트>
{text}
</리포트>

다음 항목을 JSON 하나로만 답하라. 설명을 덧붙이지 마라.

{{
  "종목명": {{"값": "", "근거": ""}},
  "증권사": {{"값": "", "근거": ""}},
  "작성일": {{"값": "", "근거": ""}},
  "투자의견": {{"값": "", "근거": ""}},
  "목표주가": {{"값": "", "근거": ""}},
  "현재주가": {{"값": "", "근거": ""}},
  "영업이익추정치_당해": {{"값": "", "근거": ""}}
}}

규칙
- "값"은 리포트에 적힌 표기를 그대로 옮긴다. 단위를 바꾸거나 계산하지 않는다.
- 리포트에 없는 항목은 "값"을 빈 문자열로 둔다. 추측해서 채우지 마라.
  목표주가가 없는 리포트가 실제로 있다. 그 경우 반드시 빈 문자열이다.
- "근거"에는 그 값이 나온 원문을 20자 안팎으로 그대로 복사한다. 요약하지 마라.
- 투자의견은 Buy 를 매수로 바꾸지 말고 적힌 그대로 옮긴다.
- 영업이익추정치_당해는 실적 표에서 {year}년 추정치 열의 영업이익이다."""


@dataclass
class Config:
    """판정에 쓰는 값은 전부 인자로 받는다."""

    model: str = "qwen3.5:0.8b"
    pages: int = 1
    year: int = 2026
    temperature: float = 0.0
    num_ctx: int = 8192
    num_predict: int = 1200
    think: bool = False
    timeout_sec: int = 600


def _call(cfg: Config, prompt: str) -> tuple[str, dict]:
    payload = {
        "model": cfg.model,
        "prompt": prompt,
        "stream": False,
        "think": cfg.think,
        "format": "json",
        "options": {
            "temperature": cfg.temperature,
            "num_ctx": cfg.num_ctx,
            "num_predict": cfg.num_predict,
        },
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=cfg.timeout_sec) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("response", ""), d


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            return {}


def _norm_for_match(s: str) -> str:
    return re.sub(r"\s", "", s)


def extract(file_id: str, filename: str, pages: list[str], cfg: Config | None = None) -> Extraction:
    cfg = cfg or Config()
    t0 = time.perf_counter()
    text = flatten("\n".join(pages[: cfg.pages]))
    raw, meta = _call(cfg, PROMPT.format(text=text, year=cfg.year))
    data = _parse(raw)

    haystack = _norm_for_match(text)
    ex = Extraction(
        file_id=file_id, filename=filename,
        note=f"{cfg.model} · 로컬 · pages={cfg.pages} temp={cfg.temperature}",
    )

    for name in FIELDS:
        item = data.get(name) or {}
        if not isinstance(item, dict):
            item = {"값": item, "근거": ""}
        value = str(item.get("값") or "").strip()
        ev = str(item.get("근거") or "").strip()

        # 근거가 실제 원문에 있는지 대조한다. 없으면 모델이 지어낸 것이다.
        grounded = bool(ev) and _norm_for_match(ev) in haystack
        off = haystack.find(_norm_for_match(ev)) if grounded else -1

        ex.cells[name] = Cell(
            value=value,
            page=1 if grounded else None,
            char_offset=off if grounded else None,
            evidence=ev,
            # 반올림하지 않는다. 근거가 원문에서 확인되면 1.0, 아니면 0.0.
            confidence=1.0 if grounded else 0.0,
        )

    ex.elapsed_sec = time.perf_counter() - t0
    if not data:
        ex.note += " · JSON 파싱 실패"
    return ex
