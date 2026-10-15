"""推移グラフ・変化点表のテスト。"""
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))
import trend  # noqa: E402
from mapgen import render  # noqa: E402
from parse import parse  # noqa: E402
from test_parse import build_html  # noqa: E402

GEO = HERE.parent / "data" / "japan_simplified.geojson"


def wb(ts, total, prefs, status="unverified"):
    return {"timestamp": ts, "total": total, "prefectures": prefs, "status": status}


WAYBACK = [wb("20150330000000", 49, 19), wb("20150812000000", 49, 19),
           wb("20160203000000", 51, 20), wb("20231128000000", 85, 31),
           wb("20260612000000", 94, 33, "ok"),
           {"timestamp": "20200101000000", "status": "unreadable"}]


def test_load_skips_unreadable(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(json.dumps({"snapshots": WAYBACK}), encoding="utf-8")
    assert len(trend.load_wayback(p)) == 5
    assert trend.load_wayback(tmp_path / "none.json") == []


def test_series_and_change_points():
    s = trend.build_series(WAYBACK[:5], [])
    assert [p["total"] for p in s] == [49, 49, 51, 85, 94]
    cps = trend.change_points(s)
    assert [c["total"] for c in cps] == [49, 51, 85, 94]
    assert cps[0]["prev"] is None
    # 変更時期は「直前の保存日〜確認日」
    assert cps[2]["prev"]["d"] == date(2016, 2, 3) and cps[2]["d"] == date(2023, 11, 28)


def test_live_points_only_after_last_wayback():
    hist = [{"date": "2026-01-01", "total": 90, "counts": {"東京都": 90}},
            {"date": "2026-10-04", "total": 94, "counts": {"東京都": 50, "大阪府": 44}}]
    s = trend.build_series(WAYBACK[:5], hist)
    assert [p["kind"] for p in s].count("live") == 1 and s[-1]["d"] == date(2026, 10, 4)


def test_section_has_chart_table_and_caveats():
    h = trend.section_html(trend.build_series(WAYBACK[:5], []))
    assert h.count("<circle") == 5 and "<svg" in h
    assert "最古の保存" in h and "2016-02-03 〜 2023-11-28" in h and "+34" in h
    assert "照合できたのは、Wayback由来の5件のうち1件" in h
    assert "分かりません" in h and "Wayback Machineの保存5件" in h


def test_render_includes_or_omits_section(tmp_path):
    snap = parse(build_html())
    hist = [{"date": "2026-10-04", "total": 94, "counts": snap.counts, "facilities": snap.facilities}]
    out = tmp_path / "i.html"
    render(snap, hist, "2026-10-14", GEO, out, "https://x/", {}, wayback=WAYBACK[:5])
    assert 'id="trend"' in out.read_text(encoding="utf-8")
    render(snap, hist, "2026-10-14", GEO, out, "https://x/", {})
    assert 'id="trend"' not in out.read_text(encoding="utf-8")


CASES = {
    "source_url": "https://www.embalming.jp/embalming/medic/", "retrieved": "2026-10-14",
    "annual": [{"year": 1988, "cases": 191, "from": "graph"}, {"year": 2017, "cases": 42760, "from": "text"},
               {"year": 2025, "cases": 88531, "from": "graph"}],
    "text_table": [{"year": 1988, "prefectures": None, "centers": None, "cases": 191, "cumulative": None},
                   {"year": 2017, "prefectures": 24, "centers": 61, "cases": 42760, "cumulative": 446034},
                   {"year": 2026, "prefectures": 33, "centers": 94, "cases": 1, "cumulative": 2}],
}


def test_cases_section_chart_and_table():
    series = trend.build_series(WAYBACK[:5], [])
    h = trend.cases_section_html(series, CASES)
    assert 'id="cases"' in h and h.count('class="bar') == 3 and "88,531" in h
    assert "24都道府県61センター" in h and "446,034" in h
    assert trend.cases_section_html(series, None) == "" and trend.cases_section_html(series, {}) == ""


def test_cases_table_range_from_same_year_snapshots():
    s = trend.build_series([wb("20240301000000", 85, 31), wb("20240620000000", 90, 32),
                            wb("20240713000000", 91, 32)], [])
    cases = {**CASES, "text_table": [{"year": 2024, "prefectures": 32, "centers": 90, "cases": 82068,
                                      "cumulative": 886542}]}
    h = trend.cases_section_html(s, cases)
    assert "31〜32都道府県85〜91センター" in h
    cases["text_table"][0]["year"] = 2030
    assert "保存なし" in trend.cases_section_html(s, cases)


def test_render_includes_cases(tmp_path):
    snap = parse(build_html())
    hist = [{"date": "2026-10-04", "total": 94, "counts": snap.counts, "facilities": snap.facilities}]
    out = tmp_path / "i.html"
    render(snap, hist, "2026-10-14", GEO, out, "https://x/", {}, wayback=WAYBACK[:5], cases=CASES)
    t = out.read_text(encoding="utf-8")
    assert 'id="trend"' in t and 'id="cases"' in t
    render(snap, hist, "2026-10-14", GEO, out, "https://x/", {}, wayback=WAYBACK[:5])
    assert 'id="cases"' not in out.read_text(encoding="utf-8")
