"""エンバーマー人数（報道・公表資料の記載）のテスト。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))
import embalmers  # noqa: E402
from mapgen import render  # noqa: E402
from parse import parse  # noqa: E402
from test_parse import build_html  # noqa: E402
from test_trend import WAYBACK  # noqa: E402

GEO = HERE.parent / "data" / "japan_simplified.geojson"
DATA = HERE.parent / "data" / "ifsa_embalmers.json"


def test_data_file_is_consistent():
    d = embalmers.load_embalmers(DATA)
    assert len(d["entries"]) >= 7
    for r in d["entries"]:
        assert r["kind"] in d["kinds"] and r["origin"] in d["origins"]
        assert r["count"] > 0 and r["medium"] and r["published"] and r["headline"]
    assert [r["_d"] for r in d["entries"]] == sorted(r["_d"] for r in d["entries"])
    # 日経の237人（2025年7月末）
    assert any(r["count"] == 237 and r["asof"] == "2025-07-31" and r["kind"] == "active" for r in d["entries"])


def test_missing_file_gives_none(tmp_path):
    assert embalmers.load_embalmers(tmp_path / "none.json") is None
    assert embalmers.section_html(None) == ""


def test_chart_has_no_connecting_line_and_labels_once():
    d = embalmers.load_embalmers(DATA)
    svg = embalmers.chart_svg(d["entries"])
    assert "<line" in svg and 'class="ln"' not in svg      # 点を結ぶ線はない
    assert svg.count(">237<") == 1                         # 同じ値で近い点のラベルは重ねない
    assert ">350<" in svg and ">約180<" in svg


def test_section_has_table_and_cautions():
    h = embalmers.section_html(embalmers.load_embalmers(DATA))
    assert "読売新聞" in h and "日本経済新聞" in h and "IFSAプレスリリース" in h
    assert "nikkei.com" in h and "線で結ばず" in h
    assert "区分不明" in h and "転載していません" in h


def test_render_adds_embalmer_tab(tmp_path):
    snap = parse(build_html())
    out = tmp_path / "i.html"
    render(snap, [], "2026-10-14", GEO, out, "https://x/", {}, wayback=WAYBACK[:5],
           embalmers=embalmers.load_embalmers(DATA))
    h = out.read_text(encoding="utf-8")
    assert 'id="p-emb"' in h and 'id="t-emb"' in h and "エンバーマー" in h
    render(snap, [], "2026-10-14", GEO, out, "https://x/", {}, wayback=WAYBACK[:5])
    assert 'id="p-emb"' not in out.read_text(encoding="utf-8")
