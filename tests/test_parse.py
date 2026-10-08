"""パーサーと検算のテスト。

注意: fixture は、2026-10-03 に取得したIFSAページの「構造」（見出し＋2列の表、
会社名セルが省略される行、会社名だけの行など）を再現した合成HTMLです。
実サイトの生HTMLそのものではありません。実サイトでの動作は、初回の
GitHub Actions 実行（手動実行）で確認してください。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from parse import PREFECTURES, ParseError, parse  # noqa: E402

# 県 -> [(会社名, 本社, [施設...])]
DATA = {
    "北海道": [("NK北海道株式会社", "北海道札幌市", ["北海道エンバーミングセンター 北海道札幌市"]),
               ("株式会社ネオ", "北海道札幌市", ["北海道エンバーミングセンター 北海道札幌市"]),   # 同名施設
               ("株式会社ブッシュ", "京都府京都市", ["札幌センター 北海道札幌市"]),
               ("株式会社いとあ", "北海道札幌市", ["いとあ北海道エンバーミングセンター 北海道札幌市"])],
    "青森県": [("株式会社リンクモア", "青森県青森市", ["青森エンバーミングセンター"])],
    "岩手県": [("アルファクラブ東北株式会社", "福島県郡山市", ["盛岡センター", "おうしゅうセンター"])],
    "宮城県": [("株式会社センティスト", "宮城県仙台市", ["東北センター"]), ("株式会社清月記", "宮城県仙台市", ["仙台センター"])],
    "山形県": [("アルファクラブ東北株式会社", "福島県郡山市", ["山形センター"])],
    "福島県": [("アルファクラブ株式会社", "福島県郡山市", ["郡山", "福島", "いわき"])],
    "茨城県": [("アルファクラブ株式会社", "福島県郡山市", ["土浦", "水海道"])],
    "栃木県": [("アルファクラブ株式会社", "栃木県宇都宮市", ["宇都宮", "小山", "那須"])],
    "埼玉県": [("SOUセレモニー株式会社", "千葉県千葉市", ["花友"]),
               ("アイエムエスジャパン株式会社", "埼玉県川口市", [f"IMS{i}" for i in range(8)])],
    "千葉県": [("株式会社ジェイイーシー", "東京都大田区", ["市原"]),
               ("SOUセレモニー株式会社", "千葉県千葉市", ["千葉", "茂原"]),
               ("株式会社金宝堂", "千葉県野田市", ["我孫子", "野田"])],
    "東京都": [("株式会社ジェイイーシー", "東京都大田区", ["東京", "城東"]),
               ("株式会社公益社", "東京都港区", ["世田谷"]), ("株式会社SEC", "神奈川県平塚市", ["八王子"]),
               ("NK東日本株式会社", "東京都板橋区", ["板橋"]), ("株式会社ディーサポート", "東京都大田区", ["大田"]),
               ("株式会社ブッシュ", "京都府京都市", ["豊玉", "葛飾", "清瀬"]),
               ("フューネラルサポートサービス合同会社", "神奈川県相模原市", ["昭島"]),
               ("株式会社ジーエスアイ", "東京都中央区", ["立石"]), ("東京博善株式会社", "東京都港区", ["お花茶屋"]),
               ("株式会社メモリードグループ", "群馬県前橋市", ["東京世田谷"])],
    "神奈川県": [("株式会社SEC", "神奈川県平塚市", ["平塚", "相模原", "海老名"]),
                 ("YMSコーポレーション株式会社", "神奈川県横浜市", ["港北"]),
                 ("ライフアンドデザイン・グループ株式会社", "東京都中央区", ["こすもす"]),
                 ("フューネラルサポートサービス合同会社", "神奈川県相模原市", ["FSS相模原"])],
    "新潟県": [("株式会社山内葬祭", "新潟県新潟市", ["燕"]), ("株式会社VIP", "新潟県三条市", ["新潟", "県央", "長岡"])],
    "富山県": [("株式会社ブッシュ", "京都府京都市", ["富山"])],
    "石川県": [("株式会社オームラ", "福井県福井市", ["金沢"])],
    "福井県": [("株式会社オームラ", "福井県福井市", ["福井"])],
    "山梨県": [("YMSコーポレーション株式会社", "神奈川県横浜市", ["山梨"]), ("株式会社ブッシュ", "京都府京都市", ["甲府"])],
    "岐阜県": [("アルファクラブ株式会社", "岐阜県岐阜市", ["岐阜"])],
    "静岡県": [("株式会社あいネットサービス", "静岡県静岡市", ["藤枝"]),
               ("アルファクラブ静岡株式会社", "静岡県静岡市", ["静岡", "青島", "浜松"])],
    "愛知県": [("株式会社のいり", "愛知県一宮市", ["のいり"]), ("株式会社シンセリー", "愛知県名古屋市", ["GC東海"])],
    "三重県": [("ライフプラン株式会社", "三重県桑名市", ["桑名"])],
    "滋賀県": [("株式会社ブッシュ", "京都府京都市", ["滋賀"])],
    "京都府": [("株式会社公益社", "京都市中京区", ["公益社"]),
               ("株式会社ブッシュ", "京都府京都市", ["京都", "洛南", "綾部"]),
               ("ライフアンドデザイン・グループ株式会社", "東京都中央区", ["L&D京都"])],
    "大阪府": [("株式会社CSCサービス", "大阪府大阪市", ["APセンター"]),
               ("株式会社公益社", "大阪府大阪市", ["大阪EC"]),
               ("株式会社ブッシュ", "京都府京都市", ["大阪"]),
               ("ライフアンドデザイン・グループ株式会社", "東京都中央区", ["L&D大阪"]),
               ("株式会社京阪互助センター", "大阪府大阪市", ["葉ざくら"])],
    "兵庫県": [("株式会社タルイ", "兵庫県明石市", ["タルイ"]), ("株式会社ブッシュ", "京都府京都市", ["西宮", "神戸"])],
    "岡山県": [("株式会社ブッシュ", "京都府京都市", ["岡山"])],
    "広島県": [("株式会社ジェイイーシー", "東京都大田区", ["広島"])],
    "愛媛県": [("株式会社ジェイイーシー", "東京都大田区", ["松山"])],
    "福岡県": [("有限会社セレモ九州要", "福岡県飯塚市", ["福岡EC"]), ("株式会社ブッシュ", "京都府京都市", ["福岡"])],
    "熊本県": [("株式会社ジェイイーシー", "東京都大田区", ["熊本", "人吉", "八代", "玉名"])],
    "大分県": [("株式会社ジェイイーシー", "東京都大田区", ["大分"])],
    "鹿児島県": [("株式会社ジェイイーシー", "東京都大田区", ["鹿児島"])],
    "沖縄県": [("株式会社敬天", "沖縄県島尻郡南風原町", ["敬天EC"])],
}
EXPECTED_COUNTS = {
    "北海道": 4, "青森県": 1, "岩手県": 2, "宮城県": 2, "山形県": 1, "福島県": 3, "茨城県": 2, "栃木県": 3,
    "埼玉県": 9, "千葉県": 5, "東京都": 13, "神奈川県": 6, "新潟県": 4, "富山県": 1, "石川県": 1, "福井県": 1,
    "山梨県": 2, "岐阜県": 1, "静岡県": 4, "愛知県": 2, "三重県": 1, "滋賀県": 1, "京都府": 5, "大阪府": 5,
    "兵庫県": 3, "岡山県": 1, "広島県": 1, "愛媛県": 1, "福岡県": 2, "熊本県": 4, "大分県": 1, "鹿児島県": 1, "沖縄県": 1,
}


def build_html(data=DATA, declared="（33都道府県・事業会社36社・94センター）", drop=None):
    out = ["<html><body><h3>組織案内</h3><table><tr><td>センター</td><td>"
           f"北海道・青森県 {declared}</td></tr></table>",
           "<h3>エンバーミングセンター案内</h3><ul>"
           + "".join(f"<li><a href='#unit-{600+i}'>{p}</a></li>" for i, p in enumerate(PREFECTURES) if p in data)
           + "</ul>"]
    for pref in PREFECTURES:
        if pref not in data:
            continue
        out.append(f"<h4 id='unit-{600+PREFECTURES.index(pref)}'>{pref}</h4><table><thead><tr><th>会社名</th><th>施設名</th></tr></thead><tbody>")
        for co, hq, facs in data[pref]:
            if drop and (pref, co) == drop:
                continue
            if pref == "大阪府":     # 会社名だけの行 → 施設だけの行（実ページの崩れ方を模擬）
                out.append(f"<tr><td>{co}<br>本社 {hq}</td></tr>")
                out += [f"<tr><td></td><td>{f}<br>{pref}</td></tr>" for f in facs]
            else:
                for i, f in enumerate(facs):
                    if i == 0:
                        out.append(f"<tr><td rowspan='{len(facs)}'>{co}<br>本社 {hq}</td><td>{f}<br>{pref}</td></tr>")
                    else:                   # rowspan で会社名セル省略
                        out.append(f"<tr><td>{f}<br>{pref}</td></tr>")
        out.append("</tbody></table>")
    out.append("</body></html>")
    return "\n".join(out)


def test_counts_match_declared():
    snap = parse(build_html())
    assert snap.total == 94
    assert len(snap.facilities) == 33
    assert snap.counts == EXPECTED_COUNTS


def test_duplicate_facility_names_kept():
    snap = parse(build_html())
    hokkaido = snap.facilities["北海道"]
    assert len(hokkaido) == 4 and len(set(hokkaido)) == 4   # 会社名付きなので区別される


def test_companies_listed():
    snap = parse(build_html())
    assert "株式会社ブッシュ" in snap.companies("東京都")


def test_fails_when_row_missing():
    with pytest.raises(ParseError):
        parse(build_html(drop=("東京都", "株式会社ディーサポート")))


def test_fails_when_declared_total_missing():
    with pytest.raises(ParseError):
        parse(build_html(declared=""))


def test_fails_when_declared_total_differs():
    with pytest.raises(ParseError):
        parse(build_html(declared="（33都道府県・事業会社36社・95センター）"))


# ---- リンク・拡大図・PNG ----------------------------------------------------
GEO = Path(__file__).resolve().parent.parent / "data" / "japan_simplified.geojson"
SRC = "https://www.embalming.jp/organization/"


def test_anchors_extracted():
    snap = parse(build_html())
    assert snap.anchors["東京都"] == "#unit-" + str(600 + PREFECTURES.index("東京都"))
    assert set(snap.anchors) == set(EXPECTED_COUNTS)      # 掲載のない県は目次にない


def test_render_has_links_and_regions(tmp_path):
    from mapgen import render
    snap = parse(build_html())
    out = tmp_path / "index.html"
    render(snap, [{"date": "2026-10-04", "total": 94, "counts": snap.counts,
                   "facilities": snap.facilities}], "2026-10-04", GEO, out, SRC)
    h = out.read_text(encoding="utf-8")
    assert f'href="{SRC}#unit-{600 + PREFECTURES.index("東京都")}"' in h   # 東京都のリンク
    for name in ("首都圏", "近畿", "九州"):
        assert name in h
    # 0件の県(群馬)はリンクにならない
    assert f'#unit-{600 + PREFECTURES.index("群馬県")}' not in h
    # <svg> が全国+3地域=4つ
    assert h.count("<svg ") == 4


def test_render_without_anchor_falls_back_to_page_url(tmp_path):
    from mapgen import render
    snap = parse(build_html())
    snap.anchors.clear()
    out = tmp_path / "index.html"
    render(snap, [], "2026-10-04", GEO, out, SRC)
    assert f'href="{SRC}"' in out.read_text(encoding="utf-8")


def test_png_svg_has_credits():
    from mapgen import REGIONS, _load_geo, _png_svg
    snap = parse(build_html())
    svg, w = _png_svg(snap, _load_geo(GEO), REGIONS[0], "2026-10-04", SRC, "https://example.org/")
    assert "地球地図日本" in svg and "国土地理院" in svg and SRC in svg
    assert "計33センター" in svg      # 首都圏 13+9+6+5


def test_png_rasterizes(tmp_path):
    pytest.importorskip("cairosvg")
    from mapgen import render_pngs
    snap = parse(build_html())
    made = render_pngs(snap, "2026-10-04", GEO, tmp_path / "img", SRC, "https://example.org/")
    assert set(made) == {"japan", "shutoken", "kinki", "kyushu"}
    for rel in made.values():
        assert (tmp_path / rel).stat().st_size > 5000


def test_company_section_can_be_switched_off_and_on(tmp_path, monkeypatch):
    import mapgen
    snap = parse(build_html())
    hist = [{"date": "2026-10-04", "total": 94, "counts": snap.counts, "facilities": snap.facilities}]
    off = tmp_path / "off.html"
    monkeypatch.setattr(mapgen, "SHOW_COMPANIES", False)     # 設定値に左右されないよう明示する
    mapgen.render(snap, hist, "2026-10-04", GEO, off, SRC)
    h = off.read_text(encoding="utf-8")
    assert "運営事業者別" not in h and "<script>" not in h and 'id="sel"' not in h
    assert '<table class="pt">' in h and "white-space:nowrap" in h        # 表の折り返し対策

    monkeypatch.setattr(mapgen, "SHOW_COMPANIES", True)
    on = tmp_path / "on.html"
    mapgen.render(snap, hist, "2026-10-04", GEO, on, SRC)
    h2 = on.read_text(encoding="utf-8")
    assert "運営事業者別" in h2 and "<script>" in h2 and 'id="sel"' in h2


def test_company_table_has_sort_toggle(tmp_path, monkeypatch):
    import mapgen
    snap = parse(build_html())
    out = tmp_path / "x.html"
    monkeypatch.setattr(mapgen, "SHOW_COMPANIES", True)
    mapgen.render(snap, [], "2026-10-08", GEO, out, SRC)
    h = out.read_text(encoding="utf-8")
    assert 'data-mode="name"' in h and 'data-mode="count"' in h and 'id="ctab"' in h
    assert 'data-t="0"' in h and 'data-n="0"' in h
