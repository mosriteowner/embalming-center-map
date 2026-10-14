"""Wayback取得スクリプトのテスト（ネットワークは使わず、偽のセッションで検証）。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE))
import wayback_history as wb  # noqa: E402
from test_parse import build_html  # noqa: E402


class FakeResp:
    def __init__(self, status=200, content=b"", payload=None):
        self.status_code, self.content, self._p = status, content, payload

    def json(self):
        return self._p


class FakeSession:
    """CDX一覧と各版のHTMLを返す。old は旧構造（読めない版）。"""
    def __init__(self, pages):
        self.pages, self.calls = pages, []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        if url == wb.CDX:
            rows = [["timestamp", "digest", "statuscode", "original"]]
            rows += [[ts, f"d{ts}", "200", "https://www.embalming.jp/organization/"] for ts in self.pages]
            return FakeResp(payload=rows)
        ts = url.split("/web/")[1].split("id_")[0]
        return FakeResp(content=self.pages[ts])


def test_ok_unverified_unreadable_and_cache(tmp_path):
    good = build_html().encode("utf-8")
    wrong_total = build_html(declared="（33都道府県・事業会社36社・90センター）").encode("cp932", errors="replace")
    old = "<html><body><p>旧レイアウト</p></body></html>".encode("utf-8")
    pages = {"20200101000000": old, "20230101000000": wrong_total, "20261003000000": good}
    out = tmp_path / "h.json"
    res = wb.run(FakeSession(pages), out=out, sleep=0)
    st = {r["timestamp"]: r["status"] for r in res}
    assert st == {"20200101000000": "unreadable", "20230101000000": "unverified", "20261003000000": "ok"}
    ok = next(r for r in res if r["status"] == "ok")
    assert ok["total"] == 94 and ok["prefectures"] == 33 and ok["declared"] == [33, 36, 94]
    assert json.loads(out.read_text(encoding="utf-8"))["snapshots"]

    # 2回目: ok/unverified は再取得しない（unreadable だけ再試行）
    s2 = FakeSession(pages)
    wb.run(s2, out=out, sleep=0)
    fetched = [u for u in s2.calls if "id_" in u]
    assert len(fetched) == 1 and "20200101000000" in fetched[0]


def test_summary_markdown():
    md = wb.summary_markdown([
        {"timestamp": "20261003000000", "status": "ok", "prefectures": 33, "companies": 36,
         "total": 94, "declared": [33, 36, 94]},
        {"timestamp": "20200101000000", "status": "unreadable", "note": "x|y"},
    ])
    assert "2026-10-03" in md and "検算一致 1 件" in md and "読めず 1 件" in md and "x/y" in md


def test_yearly_keeps_last_snapshot_of_each_year():
    snaps = [{"timestamp": t} for t in ("20200105000000", "20200901000000", "20210301000000",
                                        "20211201000000", "20211231000000", "20260101000000")]
    got = [s["timestamp"] for s in wb.yearly_last(snaps)]
    assert got == ["20200901000000", "20211231000000", "20260101000000"]
