"""集計結果から、色分け地図つきの静的HTMLを生成する。外部ライブラリ・JS不要。"""
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

# 数字ラベルの位置（経度, 緯度）。未指定の県は最大ポリゴンの外接矩形の中心。
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

OKINAWA_SHIFT = (-3.0, 5.8)   # 沖縄を九州の西の海上に移して表示する(経度, 緯度)
SCALE = 55.0                  # px / 緯度1度
LON_FACTOR = math.cos(math.radians(37.0))


def bin_of(n: int):
    for b in BINS:
        if b[0] <= n <= b[1]:
            return b
    return BINS[-1]


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


def _tf(pref: str, lon: float, lat: float):
    if pref == "沖縄県":
        lon += OKINAWA_SHIFT[0]
        lat += OKINAWA_SHIFT[1]
    return lon, lat


def _svg(snap: Snapshot, geo_path: Path) -> str:
    geo = _load_geo(geo_path)
    xs, ys = [], []
    for pref, rings in geo.items():
        for ring in rings:
            for lon, lat in ring:
                x, y = _tf(pref, lon, lat)
                xs.append(x); ys.append(y)
    lon0, lon1, lat0, lat1 = min(xs), max(xs), min(ys), max(ys)

    def px(pref, lon, lat):
        x, y = _tf(pref, lon, lat)
        return ((x - lon0) * SCALE * LON_FACTOR + 10, (lat1 - y) * SCALE + 10)

    width = (lon1 - lon0) * SCALE * LON_FACTOR + 20
    height = (lat1 - lat0) * SCALE + 20
    counts = snap.counts
    parts = [f'<svg viewBox="0 0 {width:.0f} {height:.0f}" xmlns="http://www.w3.org/2000/svg" '
             f'role="img" aria-label="都道府県別エンバーミングセンター数の色分け地図">']
    for pref in PREFECTURES:
        n = counts.get(pref, 0)
        fill = bin_of(n)[3]
        d = []
        for ring in geo.get(pref, []):
            pts = [px(pref, lon, lat) for lon, lat in ring]
            d.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
        parts.append(f'<path d="{"".join(d)}" fill="{fill}" stroke="#666" stroke-width="0.5">'
                     f'<title>{html.escape(pref)}：{n}センター</title></path>')
    # 沖縄の枠（先島諸島まで含む実際の範囲から自動計算）
    okx = [px("沖縄県", lon, lat) for ring in geo.get("沖縄県", []) for lon, lat in ring]
    if okx:
        pad = 8
        fx0, fx1 = min(x for x, _ in okx) - pad, max(x for x, _ in okx) + pad
        fy0, fy1 = min(y for _, y in okx) - pad, max(y for _, y in okx) + pad
        parts.append(f'<rect x="{fx0:.0f}" y="{fy0:.0f}" width="{fx1-fx0:.0f}" height="{fy1-fy0:.0f}" '
                     f'fill="none" stroke="#888" stroke-width="0.8" stroke-dasharray="4 3"/>')
    # 数字ラベル
    for pref in PREFECTURES:
        n = counts.get(pref, 0)
        if n == 0 or pref not in LABEL_POS:
            continue
        x, y = px(pref, *LABEL_POS[pref])
        color = bin_of(n)[4]
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" '
                     f'font-size="{13 if n < 10 else 11}" font-weight="700" fill="{color}" pointer-events="none">{n}</text>')
    parts.append("</svg>")
    return "".join(parts)


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


def render(snap: Snapshot, history: list[dict], checked_at: str,
           geo_path: Path, out_path: Path, source_url: str) -> None:
    counts = snap.counts
    e = html.escape
    legend = "".join(
        f'<li><span class="sw" style="background:{b[3]}"></span>{e(b[2])}</li>' for b in BINS)

    order = sorted(PREFECTURES, key=lambda p: (-counts.get(p, 0), PREFECTURES.index(p)))
    rows = []
    for p in order:
        n = counts.get(p, 0)
        if n == 0:
            continue
        co = "、".join(e(c) for c in snap.companies(p))
        rows.append(f"<tr><th scope='row'>{e(p)}</th><td class='n'>{n}</td><td>{co}</td></tr>")
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

    doc = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>エンバーミングセンター分布マップ（IFSA公表情報）</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--line:#ddd}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181d;--fg:#e8e8ea;--mut:#9a9aa2;--line:#33363d}}}}
body{{margin:0;padding:1rem;background:var(--bg);color:var(--fg);font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif;line-height:1.6}}
main{{max-width:960px;margin:auto}}
h1{{font-size:1.35rem;margin:.2rem 0}} h2{{font-size:1.1rem;margin-top:2rem}}
.meta{{color:var(--mut);font-size:.85rem}}
svg{{width:100%;height:auto;max-height:80vh}}
.legend{{list-style:none;display:flex;flex-wrap:wrap;gap:.4rem 1rem;padding:0;font-size:.85rem}}
.sw{{display:inline-block;width:1em;height:1em;border:1px solid #666;margin-right:.3em;vertical-align:-.15em}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}
th,td{{border-bottom:1px solid var(--line);padding:.35rem .5rem;text-align:left;vertical-align:top}}
td.n{{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}}
.ev{{font-size:.9rem}} .note{{font-size:.85rem;color:var(--mut)}}
</style></head><body><main>
<h1>エンバーミングセンター分布マップ</h1>
<p class="meta">全国 {len(snap.facilities)}都道府県・{snap.total}センター／最終確認日：{e(checked_at)}／記録開始：{e(first)}<br>
出典：<a href="{e(source_url)}">一般社団法人 日本遺体衛生保全協会（IFSA）公式サイト「IFSA組織案内」</a>（ページ記載の施設数を都道府県別に集計）</p>
{_svg(snap, geo_path)}
<ul class="legend" aria-label="凡例">{legend}</ul>
<p class="note">沖縄県は位置を移して枠内に表示しています。掲載のない県（{e('・'.join(zero))}）は0件として灰色で示していますが、
「IFSAの公表ページに掲載がない」という意味であり、その県でエンバーミングが実施できないことを意味しません。</p>
<h2>都道府県別センター数</h2>
<table><thead><tr><th>都道府県</th><th>センター数</th><th>運営会社（IFSA掲載名）</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{ev_html}
<h2>about</h2>
<p class="note">本ページはIFSAの公表情報を機械的に集計した非公式の資料で、IFSAおよび各社とは無関係です。
掲載内容はIFSAのページ更新に追従しますが、正確・最新の情報は必ず上記の公式サイトでご確認ください。
集計値がページ記載の合計と一致しない場合は更新を中止する仕組みにしています。</p>
</main></body></html>"""
    out_path.write_text(doc, encoding="utf-8")
