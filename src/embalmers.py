"""エンバーマー（遺体衛生保全の技術者）の人数に関する、報道・公表資料の記載を、点グラフと表にする。

データ: data/ifsa_embalmers.json（手で書き足す）。
表現の方針:
  * 数え方（活動中／資格・認定／区分不明）と基準時点は出所ごとに違うので、点を線で結ばない。
  * 形＝数え方、塗りつぶし＝IFSA自身の文書（または記事が「IFSAによると」と明記）、白抜き＝それ以外。
  * 増減の理由や需給についての判断はしない。数字と出所だけを示す。
"""
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

KIND_ORDER = ["active", "certified", "unclear"]
KIND_SHORT = {"active": "活動中", "certified": "資格・認定", "unclear": "区分不明"}


def load_embalmers(path: Path) -> dict | None:
    if not Path(path).exists():
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for r in data.get("entries", []):
        y, m, d = (int(x) for x in r["asof"].split("-"))
        r["_d"] = date(y, m, d)
    data["entries"] = sorted(data.get("entries", []), key=lambda r: (r["_d"], r["kind"]))
    return data


def _shape(kind: str, x: float, y: float, filled: bool) -> str:
    cls = "mk" if filled else "mk open"
    if kind == "active":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" class="{cls}"/>'
    if kind == "certified":
        return (f'<path d="M{x:.1f},{y - 8:.1f} L{x + 8:.1f},{y:.1f} L{x:.1f},{y + 8:.1f} '
                f'L{x - 8:.1f},{y:.1f} Z" class="{cls}"/>')
    return (f'<path d="M{x:.1f},{y - 8:.1f} L{x + 8:.1f},{y + 6:.1f} L{x - 8:.1f},{y + 6:.1f} Z" class="{cls}"/>')


def chart_svg(entries: list[dict]) -> str:
    W, H, L, R = 900, 380, 60, 24
    top, bot = 30, 320
    d0, d1 = date(2006, 1, 1), date(2027, 1, 1)
    span = (d1 - d0).days
    px = lambda d: L + (d - d0).days / span * (W - L - R)                       # noqa: E731
    ymax = ((max(r["count"] for r in entries) + 99) // 100) * 100
    py = lambda v: bot - v / ymax * (bot - top)                                 # noqa: E731

    g = []
    for y in range(2006, 2027, 2):
        x = px(date(y, 1, 1))
        g.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{bot}" class="tg"/>'
                 f'<text x="{x:.1f}" y="{bot + 30}" text-anchor="middle" class="tt">{y}</text>')
    for v in range(0, ymax + 1, 100):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{py(v):.1f}" y2="{py(v):.1f}" class="tg"/>'
                 f'<text x="{L - 8}" y="{py(v) + 7:.1f}" text-anchor="end" class="tt">{v}</text>')
    g.append(f'<line x1="{L}" x2="{W - R}" y1="{bot}" y2="{bot}" class="ta"/>')
    g.append(f'<text x="{L}" y="20" class="tp">記載されたエンバーマーの人数（人）</text>')

    marks, labeled, boxes = [], [], []
    pts = [(px(r["_d"]), py(r["count"])) for r in entries]
    FS = 19

    def box(x, y, anc, w):
        x0 = x - w / 2 if anc == "middle" else (x - w if anc == "end" else x)
        return (x0, y - FS, x0 + w, y + 4)

    def hit(a, b):
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    for r, (x, y) in zip(entries, pts):
        marks.append(_shape(r["kind"], x, y, r["origin"] == "ifsa"))
    for r, (x, y) in zip(entries, pts):
        # 同じ値で近い時期の点は、ラベルを重ねない
        if any(v == r["count"] and abs((r["_d"] - dd).days) < 250 for v, dd in labeled):
            continue
        txt = ("約" if r.get("approx") else "") + str(r["count"])
        w = len(txt) * 11.5 + 4
        # 候補: 上、下、左、右（他のラベル・点に重ならない最初の位置）
        for anc, dx, dy in (("middle", 0, -14), ("middle", 0, 31), ("end", -14, 6), ("start", 14, 6)):
            b = box(x + dx, y + dy, anc, w)
            if any(hit(b, o) for o in boxes):
                continue
            if any(hit(b, (px_ - 9, py_ - 9, px_ + 9, py_ + 9)) for px_, py_ in pts):
                continue
            boxes.append(b)
            marks.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anc}" class="tv">{txt}</text>')
            labeled.append((r["count"], r["_d"]))
            break

    label = ("新聞・雑誌記事やIFSAのプレスリリースに記載されたエンバーマーの人数の点グラフ（2008年約70人から2025年237人）。"
             "数え方は出所により異なります。")
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(label)}" class="trend">'
            '<style>.tg{stroke:var(--line);stroke-width:1}.ta{stroke:var(--mut);stroke-width:1.2}'
            '.tt{fill:var(--mut);font-size:21px}.tp{fill:var(--fg);font-size:22px;font-weight:700}'
            '.tv{fill:var(--fg);font-size:19px;font-weight:700}'
            '.mk{fill:var(--link);stroke:var(--link);stroke-width:2}.mk.open{fill:var(--bg)}</style>'
            + "".join(g) + "".join(marks) + "</svg>")


def _legend() -> str:
    def sh(kind: str, filled: bool) -> str:
        return (f'<svg viewBox="-10 -10 20 20" width="16" height="16" aria-hidden="true" class="lg">'
                '<style>.mk{fill:var(--link);stroke:var(--link);stroke-width:2}.mk.open{fill:var(--bg)}</style>'
                + _shape(kind, 0, 0, filled).replace('r="6.5"', 'r="6"') + '</svg>')
    items = [f'<li>{sh("active", True)} 活動中</li>', f'<li>{sh("certified", True)} 資格・認定</li>',
             f'<li>{sh("unclear", True)} 区分不明</li>',
             f'<li>{sh("active", True)} 塗りつぶし＝IFSA自身の文書、または記事が「IFSAによると」と明記</li>',
             f'<li>{sh("active", False)} 白抜き＝それ以外（出所の明記がない、またはIFSA関係者の談話が併記されている）</li>']
    return '<ul class="legend" aria-label="凡例">' + "".join(items) + '</ul>'


def section_html(data: dict | None) -> str:
    if not data or not data.get("entries"):
        return ""
    ents = data["entries"]
    rows = []
    for r in ents:
        pub = r["published"].replace("-", "/")
        med = html.escape(r["medium"])
        if r.get("url"):
            med = f'<a href="{html.escape(r["url"])}">{med}</a>'
        page = f'　{html.escape(r["page"])}' if r.get("page") else ""
        note = html.escape(r.get("note", ""))
        n = ("約" if r.get("approx") else "") + str(r["count"])
        rows.append(
            f'<tr><td class="nw">{html.escape(r["asof"].replace("-", "/"))}<br>'
            f'<span class="sm">{html.escape(r["asof_note"])}</span></td>'
            f'<td class="n">{n}</td><td>{html.escape(data["kinds"][r["kind"]])}</td>'
            f'<td>{html.escape(data["origins"][r["origin"]])}</td>'
            f'<td>{med}　{pub}{page}<br><span class="sm">{html.escape(r["headline"])}</span></td>'
            f'<td>{note}</td></tr>')
    return (
        '<h2 id="embalmers">エンバーマーの人数（報道・公表資料の記載）</h2>'
        '<p class="note">IFSAは、エンバーマーの人数を継続して公表していません。ここでは、新聞・雑誌記事とIFSAのプレスリリースに'
        '記載のあった人数を、出所ごとに点として並べています。数え方（活動中か、資格・認定を持つ人か）と基準時点が出所ごとに違うため、'
        '点は線で結ばず、数字の大小の比較や増減の判断は、ご覧になる方にお任せします（スマホでは、図を横にスクロールできます）。</p>'
        + _legend() +
        '<div class="tscroll chart">' + chart_svg(ents) + '</div>'
        '<p class="note">横軸は、記載された基準時点（基準時点の記載がないものは、記事の掲載日）です。'
        '「約」は、記事が概数で書いているものです。2025年4月の350人（資格保有者）と237人（そのうち活動している人）は、同じ記事の記載です。</p>'
        '<h3 class="sub">記載の一覧</h3>'
        '<div class="tscroll"><table class="pt nw"><thead><tr><th>基準時点</th><th>人数</th><th>数えているもの</th>'
        '<th>出所の書かれ方</th><th>媒体・掲載日・紙面</th><th>備考</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table></div>'
        '<p class="note">記事は新聞・雑誌記事横断検索データベースで確認し（' + html.escape(data["retrieved"]) +
        '）、見出しと紙面は記事のとおりに記録しています。記事本文は転載していません。'
        '数字はいずれも報道・発表の記載であり、第三者による検証はありません。'
        '個別の会社の人数や、教育に関わった人数などは含めていません。</p>')
