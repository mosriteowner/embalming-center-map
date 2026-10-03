"""IFSAページを取得 → 検算 → 履歴更新 → docs/index.html を再生成。

    python src/update.py                  # 本番（ネット接続）
    python src/update.py --html-file x.html --date 2026-10-04   # ローカルHTMLで試す

検算に失敗した場合は何も書き換えず、終了コード1で終了します（Actionsが失敗として通知）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mapgen import render          # noqa: E402
from parse import ParseError, parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = "https://www.embalming.jp/organization/"
HISTORY = ROOT / "data" / "history.json"
GEO = ROOT / "data" / "japan_simplified.geojson"
OUT = ROOT / "docs" / "index.html"
UA = "embalming-center-map/1.0 (+https://github.com/mosriteowner/embalming-center-map; weekly fetch)"


def fetch(url: str) -> str:
    import requests
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
    return r.text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html-file")
    ap.add_argument("--date")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--history", default=str(HISTORY))
    a = ap.parse_args()

    today = a.date or datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    html = Path(a.html_file).read_text(encoding="utf-8") if a.html_file else fetch(SOURCE_URL)

    try:
        snap = parse(html)
    except ParseError as e:
        print(f"[ERROR] 検算に失敗したため更新を中止します: {e}", file=sys.stderr)
        return 1

    hp = Path(a.history)
    history = json.loads(hp.read_text(encoding="utf-8")) if hp.exists() else []
    new_rec = {"date": today, "total": snap.total, "counts": snap.counts,
               "facilities": snap.facilities}
    if not history or history[-1]["facilities"] != snap.facilities:
        history.append(new_rec)
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[INFO] 変更を記録: {snap.total}センター / {len(snap.facilities)}都道府県")
    else:
        print("[INFO] 前回から変更なし")

    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    render(snap, history, today, GEO, outp, SOURCE_URL)
    (outp.parent / ".nojekyll").write_text("", encoding="utf-8")
    print(f"[INFO] 生成: {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
