"""実施件数÷全国の死亡数 のテスト。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))
import trend  # noqa: E402
from mapgen import render  # noqa: E402
from parse import parse  # noqa: E402
from test_parse import build_html  # noqa: E402
from test_trend import WAYBACK  # noqa: E402

GEO = HERE.parent / "data" / "japan_simplified.geojson"
DEATHS = HERE.parent / "data" / "deaths.json"
REAL_CASES = HERE.parent / "data" / "ifsa_cases.json"


def test_deaths_file_is_consistent():
    d = trend.load_deaths(DEATHS)
    ys = sorted(d["by_year"])
    assert ys == list(range(1988, 2026))                       # 欠けた年がない
    # 資料の記載「死亡数は1,589,533人で（前年より）15,845人減少」と合う
    assert d["by_year"][2024]["deaths"] - d["by_year"][2025]["deaths"] == 15845
    assert all(r["deaths"] > 700000 for r in d["deaths"])


def test_ratio_values_match_hand_calculation():
    rows = {r["year"]: r for r in trend.ratio_rows(trend.load_cases(REAL_CASES), trend.load_deaths(DEATHS))}
    assert round(rows[2024]["pct"], 2) == 5.11     # 日経の「全死亡数の5%」と整合
    assert round(rows[2025]["pct"], 2) == 5.57
    assert round(rows[1988]["pct"], 3) == 0.024
    assert len(rows) == 21                          # 実施件数のある年すべて


def test_missing_deaths_year_is_skipped():
    d = {"by_year": {2024: {"deaths": 1000000}}}
    cases = {"annual": [{"year": 2023, "cases": 5}, {"year": 2024, "cases": 50}]}
    assert [r["year"] for r in trend.ratio_rows(cases, d)] == [2024]
    assert trend.ratio_section_html(cases, d) == ""             # 2点未満なら出さない
    assert trend.ratio_rows(cases, None) == []


def test_section_cautions_and_chart():
    c, d = trend.load_cases(REAL_CASES), trend.load_deaths(DEATHS)
    h = trend.ratio_section_html(c, d)
    assert "日本における日本人" in h and "外国人" in h and "年ごとの数値" in h
    assert "5.11%" in h and "5.57%" in h and "mhlw.go.jp" in h
    assert 'class="mk open"' in h                                # 2017年（本文の表の値）は白抜き


def test_render_includes_ratio_only_with_deaths(tmp_path):
    snap = parse(build_html())
    out = tmp_path / "i.html"
    cases = trend.load_cases(REAL_CASES)
    render(snap, [], "2026-10-21", GEO, out, "https://x/", {}, wayback=WAYBACK[:5], cases=cases,
           deaths=trend.load_deaths(DEATHS))
    assert 'id="ratio"' in out.read_text(encoding="utf-8")
    render(snap, [], "2026-10-21", GEO, out, "https://x/", {}, wayback=WAYBACK[:5], cases=cases)
    assert 'id="ratio"' not in out.read_text(encoding="utf-8")
