"""Wayback Machine に保存された IFSA「組織案内」ページから、センター数の推移を取り出す。

使い方（GitHub Actions の wayback.yml が実行します。手元でも動きます）:
    python tools/wayback_history.py            # 取得して data/wayback_history.json を作る
    python tools/wayback_history.py --limit 5  # 試しに先頭5件だけ
    python tools/wayback_history.py --yearly   # 年に1件（その年の最後の保存）だけ

方針:
  * Internet Archive 公式の CDX API で、保存履歴を「内容が変わった回だけ」に絞って取得する。
  * 各保存の生HTML（…id_/ 形式。Wayback のツールバー等が混ざらない）を取得し、
    現在の src/parse.py で都道府県別の件数を読む。
  * 読み取りの結果は次の3区分で記録する。
      ok          : ページ自身が書く合計と集計が一致した（信頼できる）
      unverified  : 件数は読めたが、ページ記載の合計と一致しない／合計表記がない（参考値）
      unreadable  : 構造が違って読めない、または取得に失敗した
  * 既に取得済みの保存（ok / unverified）は再取得しない。何度実行しても安全。
  * Internet Archive に負荷をかけないよう、1件ごとに待機する。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import parse as parse_mod  # noqa: E402

TARGET = "www.embalming.jp/organization/"
CDX = "https://web.archive.org/cdx/search/cdx"
RAW = "https://web.archive.org/web/{ts}id_/{url}"
OUT = ROOT / "data" / "wayback_history.json"
UA = "embalming-center-map/1.0 (personal research; https://github.com/mosriteowner/embalming-center-map)"
SLEEP = 1.5


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def _get(session, url, params=None, tries=4, timeout=60):
    last = None
    for i in range(tries):
        try:
            r = session.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code}")
            if r.status_code in (403, 404):
                break
        except requests.RequestException as e:  # noqa: PERF203
            last = e
        time.sleep(3 * (i + 1))
    raise RuntimeError(str(last))


def list_snapshots(session) -> list[dict]:
    """内容(digest)が変わった保存だけを、古い順に返す。"""
    r = _get(session, CDX, params={
        "url": TARGET, "output": "json",
        "fl": "timestamp,digest,statuscode,original",
        "filter": "statuscode:200", "collapse": "digest",
    })
    rows = r.json()
    if not rows:
        return []
    head, body = rows[0], rows[1:]
    snaps = [dict(zip(head, row)) for row in body]
    return sorted(snaps, key=lambda x: x["timestamp"])


def decode(raw: bytes) -> str:
    for enc in ("utf-8", "cp932", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_html(html: str) -> dict:
    """1つの版のHTMLから、件数を読み取って記録用の辞書にする。"""
    # parse() は内部で validate するので、いったん検算を外して件数を読み、後で検算する。
    orig = parse_mod.validate
    parse_mod.validate = lambda snap: None
    try:
        snap = parse_mod.parse(html)
    finally:
        parse_mod.validate = orig
    if not snap.facilities:
        return {"status": "unreadable", "note": "都道府県別の表を読み取れませんでした（ページ構造が現在と異なる可能性）"}
    rec = {
        "counts": snap.counts,
        "total": snap.total,
        "prefectures": len(snap.facilities),
        "companies": len({c for p in snap.facilities for c in snap.companies(p)}),
        "declared": list(snap.declared) if snap.declared else None,
    }
    try:
        parse_mod.validate(snap)
        rec["status"] = "ok"
    except parse_mod.ParseError as e:
        rec["status"] = "unverified"
        rec["note"] = str(e)
    return rec


def fetch_one(session, snap: dict) -> dict:
    rec = {"timestamp": snap["timestamp"], "digest": snap["digest"]}
    url = RAW.format(ts=snap["timestamp"], url=snap.get("original") or "https://" + TARGET)
    try:
        r = _get(session, url)
    except RuntimeError as e:
        rec.update(status="unreadable", note=f"取得失敗: {e}")
        return rec
    try:
        rec.update(read_html(decode(r.content)))
    except Exception as e:  # noqa: BLE001
        rec.update(status="unreadable", note=f"解析失敗: {type(e).__name__}: {e}")
    return rec


def yearly_last(snaps: list[dict]) -> list[dict]:
    """各年の「最後の保存」だけを残す（＝その年末時点のページの状態）。"""
    last: dict[str, dict] = {}
    for s in sorted(snaps, key=lambda x: x["timestamp"]):
        last[s["timestamp"][:4]] = s
    return [last[y] for y in sorted(last)]


def run(session, out: Path = OUT, limit: int | None = None, sleep: float = SLEEP,
        yearly: bool = False) -> list[dict]:
    cache: dict[str, dict] = {}
    if out.exists():
        for r in json.loads(out.read_text(encoding="utf-8")).get("snapshots", []):
            if r.get("status") in ("ok", "unverified"):
                cache[r["timestamp"]] = r
    snaps = list_snapshots(session)
    if yearly:
        snaps = yearly_last(snaps)
    if limit:
        snaps = snaps[:limit]
    result = []
    for i, s in enumerate(snaps, 1):
        if s["timestamp"] in cache:
            result.append(cache[s["timestamp"]])
            continue
        print(f"[{i}/{len(snaps)}] {s['timestamp']}", flush=True)
        result.append(fetch_one(session, s))
        time.sleep(sleep)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "source": "Internet Archive Wayback Machine",
        "target": "https://" + TARGET,
        "snapshots": result,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def fmt_date(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"


def summary_markdown(result: list[dict]) -> str:
    mark = {"ok": "✅ 検算一致", "unverified": "△ 参考値", "unreadable": "✕ 読めず"}
    lines = ["## Wayback Machine から読み取ったセンター数の推移", "",
             f"保存（内容が変わった回）: {len(result)} 件", "",
             "| 保存日 | 区分 | 都道府県 | 会社 | センター(集計) | センター(ページ記載) | 備考 |",
             "|---|---|---|---|---|---|---|"]
    for r in result:
        d = r.get("declared")
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            fmt_date(r["timestamp"]), mark.get(r["status"], r["status"]),
            r.get("prefectures", ""), r.get("companies", ""), r.get("total", ""),
            d[2] if d else "", (r.get("note") or "").replace("|", "/")))
    n = {k: sum(1 for r in result if r["status"] == k) for k in mark}
    lines += ["", f"検算一致 {n['ok']} 件 / 参考値 {n['unverified']} 件 / 読めず {n['unreadable']} 件"]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yearly", action="store_true",
                    help="年に1件（その年の最後の保存＝年末時点）だけを取得する")
    ap.add_argument("--limit", type=int, default=None, help="先頭から何件だけ処理するか（試験用）")
    args = ap.parse_args()
    result = run(make_session(), limit=args.limit, yearly=args.yearly)
    md = summary_markdown(result)
    print(md)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
