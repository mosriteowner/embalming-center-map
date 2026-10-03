"""集計結果から、色分け地図つきの静的HTMLと、PNG画像を生成する。

* 全国図 + 地域拡大図（首都圏・近畿・九州）
* 県の図形・数字をクリック/タップ → IFSA公式ページの該当県の一覧へ
* PNG は出典・日付入りの単体画像（Xなどに貼れる）
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

from parse import PREFECTURES, Snapshot

# 色の区分は経年比較のため固定。(下限, 上限, ラベル, 塗り色, 文字色)
BINS = [
    (0, 0, "0", "#e6e6e6", "#222"),
    (1, 1, "1", "#fff3b0", "#222"),
    (2, 2, "2", "#ffd166", "#222"),
    (3, 3, "3", "#f9a03f", "#222"),
    (4, 5, "4〜5", "#ee6c4d", "#fff"),
    (6, 9, "6〜9", "#c1121f", "#fff"),
    (10, 19, "10〜19", "#6a040f", "#fff"),
    (20, 10**6, "20以上", "#25020a", "#fff"),
]

# 数字ラベルの位置（経度, 緯度）。
LABEL_POS = {
    "北海道": (142.9, 43.4), "青森県": (140.9, 40.7), "岩手県": (141.4, 39.6),
    "宮城県": (140.9, 38.4), "山形県": (140.1, 38.5), "福島県": (140.2, 37.4),
    "茨城県": (140.3, 36.3), "栃木県": (139.8, 36.7), "埼玉県": (139.4, 36.0),
    "千葉県": (140.2, 35.5), "東京都": (139.35, 35.7), "神奈川県": (139.4, 35.4),
    "新潟県": (138.9, 37.5), "富山県": (137.2, 36.65), "石川県": (136.8, 36.8),
    "福井県": (136.2, 35.9), "山梨県": (138.6, 35.6), "岐阜県": (137.2, 35.9),
    "静岡県": (138.2, 35.0), "愛知県": (137.2, 35.0), "三重県": (136.4, 34.5),
    "滋賀県": (136.1, 35.3), "京都府": (135.5, 35.25), "大阪府": (135.5, 34.6),
    "兵庫県": (134.8, 35.0), "岡山県": (133.9, 35.0), "広島県": (132.8, 34.6),
    "愛媛県": (132.9, 33.6), "福岡県": (130.6, 33.5), "熊本県": (130.8, 32.6),
    "大分県": (131.5, 33.2), "鹿児島県": (130.6, 31.5), "沖縄県": (127.75, 26.45),
}
# 拡大図では位置を微調整（全国図の位置から差し替える県のみ）
LABEL_POS_ZOOM = {
    "東京都": (139.3, 35.72), "神奈川県": (139.4, 35.42), "埼玉県": (139.4, 36.0),
    "千葉県": (140.25, 35.55), "大阪府": (135.5, 34.62), "京都府": (135.4, 35.3),
    "兵庫県": (134.85, 35.1), "滋賀県": (136.05, 35.3), "三重県": (136.4, 34.6),
    "鹿児島県": (130.35, 31.85),
}

# 拡大図の定義。core=その地域に数える県（小計用）、bbox=(経度min, 経度max, 緯度min, 緯度max)
REGIONS = [
    {"key": "shutoken", "name": "首都圏", "desc": "1都3県",
     "core": ["東京都", "神奈川県", "埼玉県", "千葉県"],
     "bbox": (138.45, 140.95, 34.85, 37.0), "width": 760},
    {"key": "kinki", "name": "近畿", "desc": "2府5県・三重県を含む",
     "core": ["滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "三重県"],
     "bbox": (134.1, 137.0, 33.35, 35.95), "width": 760},
    {"key": "kyushu", "name": "九州", "desc": "7県・沖縄県を除く",
     "core": ["福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県"],
     "bbox": (129.3, 132.1, 30.1, 33.95), "width": 760},
]

OKINAWA_SHIFT = (-3.0, 5.8)   # 全国図で沖縄を九州の西の海上に移す(経度, 緯度)
SCALE = 55.0                  # 全国図: px / 緯度1度
LON_FACTOR = math.cos(math.radians(37.0))
FONT = "'Noto Sans CJK JP','Noto Sans JP','Hiragino Sans',Meiryo,sans-serif"


def bin_of(n: int):
    for b in BINS:
        if b[0] <= n <= b[1]:
            return b
    return BINS[-1]


# ----------------------------------------------------------------- 地図データ
def _load_geo(path: Path):
    gj = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for ft in gj["features"]:
        name = ft["properties"]["name"]
        g = ft["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        keep = []
        for poly in polys:
            ring = poly[0]
            mean_lat = sum(p[1] for p in ring) / len(ring)
            if name != "沖縄県" and mean_lat < 29.5:   # 小笠原・奄美などは省略
                continue
            keep.append(ring)
        out[name] = keep
    return out


class Proj:
    """経緯度 → 画面座標。"""

    def __init__(self, lon0, lon1, lat0, lat1, scale, okinawa_shift=False, pad=0):
        self.lon0, self.lat1, self.scale, self.pad = lon0, lat1, scale, pad
        self.okinawa_shift = okinawa_shift
        self.width = (lon1 - lon0) * scale * LON_FACTOR + 2 * pad
        self.height = (lat1 - lat0) * scale + 2 * pad

    def xy(self, pref, lon, lat):
        if self.okinawa_shift and pref == "沖縄県":
            lon += OKINAWA_SHIFT[0]
            lat += OKINAWA_SHIFT[1]
        return ((lon - self.lon0) * self.scale * LON_FACTOR + self.pad,
                (self.lat1 - lat) * self.scale + self.pad)


def _national_proj(geo) -> Proj:
    xs, ys = [], []
    for pref, rings in geo.items():
        for ring in rings:
            for lon, lat in ring:
                if pref == "沖縄県":
                    lon += OKINAWA_SHIFT[0]; lat += OKINAWA_SHIFT[1]
                xs.append(lon); ys.append(lat)
    return Proj(min(xs), max(xs), min(ys), max(ys), SCALE, okinawa_shift=True, pad=10)


def _region_proj(region) -> Proj:
    lon0, lon1, lat0, lat1 = region["bbox"]
    scale = region["width"] / ((lon1 - lon0) * LON_FACTOR)
    return Proj(lon0, lon1, lat0, lat1, scale)


def _intersects(ring, bbox) -> bool:
    lon0, lon1, lat0, lat1 = bbox
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return not (max(xs) < lon0 or min(xs) > lon1 or max(ys) < lat0 or min(ys) > lat1)


# ----------------------------------------------------------------- SVG 部品
def _map_inner(snap: Snapshot, geo, proj: Proj, bbox=None, links=None,
               label_size=13, stroke=0.5) -> str:
    """地図本体(県の図形+数字)。links: {県名: URL} を渡すとクリック可能にする。"""
    counts = snap.counts
    pos_table = {**LABEL_POS, **LABEL_POS_ZOOM} if bbox else LABEL_POS
    e = html.escape

    def wrap(pref, inner):
        if links is None or counts.get(pref, 0) == 0:
            return inner
        return (f'<a href="{e(links[pref])}" target="_blank" rel="noopener noreferrer">'
                f'{inner}</a>')

    paths, labels = [], []
    for pref in PREFECTURES:
        rings = geo.get(pref, [])
        if bbox:
            rings = [r for r in rings if _intersects(r, bbox)]
        if not rings:
            continue
        n = counts.get(pref, 0)
        d = "".join("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in
                                   (proj.xy(pref, lon, lat) for lon, lat in ring)) + "Z"
                    for ring in rings)
        tip = f"{pref}：{n}センター" + ("（クリックでIFSAの一覧へ）" if links is not None and n else "")
        paths.append(wrap(pref, f'<path d="{d}" fill="{bin_of(n)[3]}" stroke="#666" '
                                f'stroke-width="{stroke}" stroke-linejoin="round">'
                                f'<title>{e(tip)}</title></path>'))
        if n == 0 or pref not in pos_table:
            continue
        lon, lat = pos_table[pref]
        if bbox and not (bbox[0] <= lon <= bbox[1] and bbox[2] <= lat <= bbox[3]):
            continue
        x, y = proj.xy(pref, lon, lat)
        size = label_size if n < 10 else label_size - 2
        labels.append(wrap(pref, f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" '
                                 f'dominant-baseline="central" font-size="{size}" font-weight="700" '
                                 f'fill="{bin_of(n)[4]}" style="cursor:pointer">{n}</text>'))
    extra = ""
    if proj.okinawa_shift:    # 沖縄の枠
        pts = [proj.xy("沖縄県", lon, lat) for ring in geo.get("沖縄県", []) for lon, lat in ring]
        if pts:
            pad = 8
            fx0, fx1 = min(x for x, _ in pts) - pad, max(x for x, _ in pts) + pad
            fy0, fy1 = min(y for _, y in pts) - pad, max(y for _, y in pts) + pad
            extra = (f'<rect x="{fx0:.0f}" y="{fy0:.0f}" width="{fx1-fx0:.0f}" height="{fy1-fy0:.0f}" '
                     f'fill="none" stroke="#888" stroke-width="0.8" stroke-dasharray="4 3"/>')
    return "".join(paths) + extra + "".join(labels)


def _svg_doc(inner: str, proj: Proj, label: str) -> str:
    return (f'<svg viewBox="0 0 {proj.width:.0f} {proj.height:.0f}" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{html.escape(label)}">'
            f'{inner}</svg>')


def _links(snap: Snapshot, source_url: str) -> dict[str, str]:
    return {p: source_url + snap.anchors.get(p, "") for p in PREFECTURES}


# ----------------------------------------------------------------- PNG
def _png_svg(snap: Snapshot, geo, region: dict | None, label_date: str,
             source_url: str, page_url: str) -> tuple[str, int]:
    proj = _region_proj(region) if region else _national_proj(geo)
    bbox = region["bbox"] if region else None
    inner = _map_inner(snap, geo, proj, bbox=bbox, links=None,
                       label_size=20 if region else 13, stroke=1.0 if region else 0.5)
    W = int(max(proj.width, 760))
    top, mapH = 96, int(proj.height)
    legend_y = top + mapH + 14
    foot_y = legend_y + 52
    H = foot_y + 5 * 18 + 10
    name = region["name"] if region else "全国"
    sub2 = f"全国 {len(snap.facilities)}都道府県・{snap.total}センター"
    if region:
        sub = sum(snap.counts.get(p, 0) for p in region["core"])
        sub2 = f"{region['name']}（{region['desc']}）計{sub}センター／" + sub2
    mx = (W - proj.width) / 2
    t = html.escape
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
             f'font-family="{FONT}">',
             f'<rect width="{W}" height="{H}" fill="#fff"/>',
             f'<text x="20" y="34" font-size="22" font-weight="700" fill="#111">'
             f'エンバーミングセンター分布マップ（{t(name)}）</text>',
             f'<text x="20" y="58" font-size="13" fill="#333">{t(sub2)}</text>',
             f'<text x="20" y="78" font-size="12" fill="#555">IFSA公表情報を都道府県別に集計した非公式の図'
             f'／IFSA掲載内容（{t(label_date)} 確認）</text>',
             f'<clipPath id="mapclip"><rect width="{proj.width:.0f}" height="{proj.height:.0f}"/></clipPath>',
             f'<g transform="translate({mx:.1f},{top})" clip-path="url(#mapclip)">{inner}</g>']
    # 凡例
    iw = min(110, (W - 40) / len(BINS))
    for i, b in enumerate(BINS):
        x = 20 + i * iw
        parts.append(f'<rect x="{x:.0f}" y="{legend_y}" width="16" height="16" fill="{b[3]}" '
                     f'stroke="#666" stroke-width="0.6"/>'
                     f'<text x="{x+22:.0f}" y="{legend_y+13}" font-size="13" fill="#222">{t(b[2])}</text>')
    parts.append(f'<text x="20" y="{legend_y+36}" font-size="11" fill="#666">'
                 f'数字＝センター数。灰色は「IFSAの公表ページに掲載なし」であり、実施できないという意味ではありません。</text>')
    lines = ["出典：一般社団法人 日本遺体衛生保全協会（IFSA）公式サイト「IFSA組織案内」",
             source_url,
             "地図：「地球地図日本」（国土地理院）をもとに、dataofjapan/land の変換データを",
             "簡略化・加工して作成",
             page_url]
    for i, ln in enumerate(lines):
        parts.append(f'<text x="20" y="{foot_y + i*18}" font-size="12" fill="#444">{t(ln)}</text>')
    parts.append("</svg>")
    return "".join(parts), W


def render_pngs(snap: Snapshot, label_date: str, geo_path: Path, out_dir: Path,
                source_url: str, page_url: str) -> dict[str, str]:
    """PNGを out_dir に出力し、{キー: 'img/xxx.png'} を返す。cairosvg と日本語フォントが必要。"""
    import cairosvg
    geo = _load_geo(geo_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    made = {}
    for region in [None] + REGIONS:
        key = region["key"] if region else "japan"
        svg, w = _png_svg(snap, geo, region, label_date, source_url, page_url)
        path = out_dir / f"map_{key}.png"
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(path),
                         output_width=int(w * (2.0 if region else 1.6)))
        made[key] = f"img/{path.name}"
    return made


# ----------------------------------------------------------------- HTML
def _diff_events(history: list[dict]) -> list[dict]:
    events = []
    for prev, cur in zip(history, history[1:]):
        added, removed = [], []
        for pref in PREFECTURES:
            a = list(cur["facilities"].get(pref, []))
            b = list(prev["facilities"].get(pref, []))
            for f in b:
                if f in a:
                    a.remove(f)
                else:
                    removed.append((pref, f))
            added += [(pref, f) for f in a]
        events.append({"date": cur["date"], "added": added, "removed": removed,
                       "total": cur["total"], "prev_total": prev["total"]})
    return list(reversed(events))


def render(snap: Snapshot, history: list[dict], checked_at: str, geo_path: Path,
           out_path: Path, source_url: str, png_files: dict[str, str] | None = None) -> None:
    png_files = png_files or {}
    counts = snap.counts
    e = html.escape
    geo = _load_geo(geo_path)
    links = _links(snap, source_url)

    nat_proj = _national_proj(geo)
    nat_svg = _svg_doc(_map_inner(snap, geo, nat_proj, links=links), nat_proj,
                       "都道府県別エンバーミングセンター数の色分け地図（全国）")

    figs = []
    for r in REGIONS:
        proj = _region_proj(r)
        svg = _svg_doc(_map_inner(snap, geo, proj, bbox=r["bbox"], links=links,
                                  label_size=20, stroke=1.0), proj, f"{r['name']}の拡大図")
        sub = sum(counts.get(p, 0) for p in r["core"])
        png = (f' <a class="dl" href="{e(png_files[r["key"]])}" download>PNG</a>'
               if r["key"] in png_files else "")
        figs.append(f'<figure><figcaption><b>{e(r["name"])}</b>（{e(r["desc"])}）計{sub}センター{png}'
                    f'</figcaption>{svg}</figure>')

    legend = "".join(
        f'<li><span class="sw" style="background:{b[3]}"></span>{e(b[2])}</li>' for b in BINS)

    order = sorted(PREFECTURES, key=lambda p: (-counts.get(p, 0), PREFECTURES.index(p)))
    rows = []
    for p in order:
        n = counts.get(p, 0)
        if n == 0:
            continue
        co = "、".join(e(c) for c in snap.companies(p))
        rows.append(f'<tr><th scope="row"><a href="{e(links[p])}" target="_blank" '
                    f'rel="noopener noreferrer">{e(p)}</a></th><td class="n">{n}</td><td>{co}</td></tr>')
    zero = [p for p in PREFECTURES if counts.get(p, 0) == 0]

    ev_html = ""
    events = _diff_events(history)[:10]
    if events:
        items = []
        for ev in events:
            ch = [f"＋ {e(p)}：{e(f.split('｜',1)[-1])}" for p, f in ev["added"]]
            ch += [f"－ {e(p)}：{e(f.split('｜',1)[-1])}" for p, f in ev["removed"]]
            items.append(f"<li><b>{e(ev['date'])}</b>（{ev['prev_total']}→{ev['total']}センター）<br>"
                         + "<br>".join(ch) + "</li>")
        ev_html = "<h2>変更履歴（直近）</h2><ul class='ev'>" + "".join(items) + "</ul>"
    first = history[0]["date"] if history else checked_at

    png_nat = (f' 　<a class="dl" href="{e(png_files["japan"])}" download>全国図をPNG画像で保存</a>'
               if "japan" in png_files else "")
    png_hint = ("（画像を開いて右クリック→「画像をコピー」でも貼り付けできます）" if png_files else "")

    doc = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>エンバーミングセンター分布マップ（IFSA公表情報）</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--line:#ddd;--link:#0b5cad}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181d;--fg:#e8e8ea;--mut:#9a9aa2;--line:#33363d;--link:#7db7ff}}}}
body{{margin:0;padding:1rem;background:var(--bg);color:var(--fg);font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif;line-height:1.6}}
main{{max-width:960px;margin:auto}}
a{{color:var(--link)}}
h1{{font-size:1.35rem;margin:.2rem 0}} h2{{font-size:1.1rem;margin-top:2rem}}
.meta{{color:var(--mut);font-size:.85rem}}
svg{{width:100%;height:auto;max-height:80vh}}
svg a{{cursor:pointer}} svg a:hover path{{stroke:#000;stroke-width:1.8}}
.legend{{list-style:none;display:flex;flex-wrap:wrap;gap:.4rem 1rem;padding:0;font-size:.85rem}}
.sw{{display:inline-block;width:1em;height:1em;border:1px solid #666;margin-right:.3em;vertical-align:-.15em}}
.zooms{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:1rem}}
figure{{margin:0}} figcaption{{font-size:.9rem;margin-bottom:.2rem}}
.dl{{font-size:.85rem;margin-left:.4rem}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}
th,td{{border-bottom:1px solid var(--line);padding:.35rem .5rem;text-align:left;vertical-align:top}}
td.n{{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}}
.ev{{font-size:.9rem}} .note{{font-size:.85rem;color:var(--mut)}}
</style></head><body><main>
<h1>エンバーミングセンター分布マップ</h1>
<p class="meta">全国 {len(snap.facilities)}都道府県・{snap.total}センター／最終確認日：{e(checked_at)}／記録開始：{e(first)}<br>
出典：<a href="{e(source_url)}">一般社団法人 日本遺体衛生保全協会（IFSA）公式サイト「IFSA組織案内」</a>（ページ記載の施設数を都道府県別に集計）</p>
<p class="note">色のついた県（図形または数字）をクリック／タップすると、IFSA公式ページのその県の一覧が別タブで開きます。{png_nat}{e(png_hint)}</p>
{nat_svg}
<ul class="legend" aria-label="凡例">{legend}</ul>
<p class="note">沖縄県は位置を移して枠内に表示しています。掲載のない県（{e('・'.join(zero))}）は0件として灰色で示していますが、
「IFSAの公表ページに掲載がない」という意味であり、その県でエンバーミングが実施できないことを意味しません。</p>
<h2>地域拡大図</h2>
<div class="zooms">{''.join(figs)}</div>
<h2>都道府県別センター数</h2>
<table><thead><tr><th>都道府県</th><th>センター数</th><th>運営会社（IFSA掲載名）</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{ev_html}
<h2>about</h2>
<p class="note">地図の都道府県境界は、「地球地図日本」（国土地理院）をもとに、<a href="https://github.com/dataofjapan/land">dataofjapan/land</a>で公開されている変換データを簡略化・加工して作成しました。出典：<a href="http://www.gsi.go.jp/kankyochiri/gm_jpn.html">国土地理院ウェブサイト</a>。
本ページはIFSAの公表情報を機械的に集計した非公式の資料で、IFSAおよび各社とは無関係です。
掲載内容はIFSAのページ更新に追従しますが、正確・最新の情報は必ず上記の公式サイトでご確認ください。
集計値がページ記載の合計と一致しない場合は更新を中止する仕組みにしています。</p>
</main></body></html>"""
    out_path.write_text(doc, encoding="utf-8")
