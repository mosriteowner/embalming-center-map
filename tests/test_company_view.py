"""社別の一覧（五十音順）のテスト。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))
import company_view as cv  # noqa: E402
import mapgen  # noqa: E402
from parse import Snapshot, parse  # noqa: E402
from test_parse import build_html  # noqa: E402
from test_trend import WAYBACK  # noqa: E402

GEO = HERE.parent / "data" / "japan_simplified.geojson"
READ = HERE.parent / "data" / "company_readings.json"


def snap_of(facs):
    return Snapshot(facilities=facs)


def test_kana_key_ignores_long_mark_and_small_kana():
    assert cv.kana_key("オームラ")[0] == cv.kana_key("オオムラ")[0]
    assert cv.kana_key("ジェイ")[0] == cv.kana_key("シエイ")[0]
    assert sorted(["ワイ", "アイ", "ケイ"], key=cv.kana_key) == ["アイ", "ケイ", "ワイ"]


def test_group_sorted_by_group_reading_and_members_inside():
    rd = {"companies": {cv.norm_name(n): {"name": n, "kana": k} for n, k in [
        ("アルファクラブ株式会社", "アルファクラブ"), ("アルファクラブ東北株式会社", "アルファクラブトウホク"),
        ("株式会社ブッシュ", "ブッシュ"), ("株式会社いとあ", "イトア")]},
        "groups": {cv.norm_name("アルファクラブグループ"): {"name": "アルファクラブグループ", "kana": "アルファクラブグループ"}}}
    s = snap_of({"栃木県": ["アルファクラブグループ アルファクラブ株式会社｜宇都宮"],
                 "福島県": ["アルファクラブグループ アルファクラブ東北株式会社｜福島"],
                 "東京都": ["株式会社ブッシュ｜練馬", "株式会社いとあ｜x"]})
    items, missing = cv.build(s, rd)
    assert missing == []
    assert [x["name"] for x in items] == ["アルファクラブグループ", "株式会社いとあ", "株式会社ブッシュ"]
    assert [m["name"] for m in items[0]["members"]] == ["アルファクラブ株式会社", "アルファクラブ東北株式会社"]


def test_missing_reading_goes_last_and_is_reported():
    s = snap_of({"東京都": ["株式会社新会社｜x", "株式会社ブッシュ｜y"]})
    rd = {"companies": {cv.norm_name("株式会社ブッシュ"): {"name": "株式会社ブッシュ", "kana": "ブッシュ"}}, "groups": {}}
    items, missing = cv.build(s, rd)
    assert missing == ["株式会社新会社"]
    assert items[-1]["name"] == "株式会社新会社"
    html, _ = cv.view_html(s, rd)
    assert "読み未登録" in html


def test_readings_file_covers_current_companies():
    s = parse(build_html())
    _, missing = cv.build(s, cv.load_readings(READ))
    assert missing == []
    d = json.loads(READ.read_text(encoding="utf-8"))
    assert all(r["kana"] and r["basis"] for r in d["companies"] + d["groups"])


def test_view_has_no_count_ranking():
    s = parse(build_html())
    html, _ = cv.view_html(s, cv.load_readings(READ))
    assert "順位" not in html and "五十音順" in html


def test_toggle_only_when_flag_on(tmp_path, monkeypatch):
    snap = parse(build_html())
    out = tmp_path / "i.html"
    kw = dict(wayback=WAYBACK[:5], readings=cv.load_readings(READ))
    monkeypatch.setattr(mapgen, "SHOW_COMPANY_LIST", False)
    mapgen.render(snap, [], "2026-10-15", GEO, out, "https://x/", {}, **kw)
    h = out.read_text(encoding="utf-8")
    assert 'id="v-co"' not in h and 'class="seg"' not in h and ">一覧<" in h
    monkeypatch.setattr(mapgen, "SHOW_COMPANY_LIST", True)
    mapgen.render(snap, [], "2026-10-15", GEO, out, "https://x/", {}, **kw)
    h = out.read_text(encoding="utf-8")
    assert 'id="v-co"' in h and 'id="v-pref"' in h and 'data-v="co"' in h
