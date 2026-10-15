"""センター数の推移（Wayback Machine の保存 ＋ 毎週の自動確認）を、グラフと表にする。

データの出どころ:
  * data/wayback_history.json : tools/wayback_history.py が Internet Archive から作る過去の記録
  * data/history.json         : 毎週の自動更新が記録する、これからの記録

表現の方針:
  * 点は「その日にIFSAのページがその数字を載せていた」という観測。点と点の間は結ぶだけで、
    その間に何があったかは分からない（保存の間隔が180日を超える区間は破線にする）。
  * ページ記載の合計と照合できた点は塗りつぶし、照合できなかった点は白抜きにする。
  * 増減の理由（新設・閉鎖・掲載基準の変更など）はデータから分からないので、何も主張しない。
"""
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

GAP_DAYS = 180   # これを超える間隔は破線で結ぶ


def _d(s: str) -> date:
    s = s.replace("-", "")
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def load_wayback(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    raw = json.loads(Path(path).read_text(encoding="utf-8")).get("snapshots", [])
    return [r for r in raw if r.get("status") in ("ok", "unverified") and "total" in r]


def build_series(wayback: list[dict], history: list[dict]) -> list[dict]:
    """古い順の点列。{d, total, prefs, ok, kind}"""
    pts = [{"d": _d(r["timestamp"][:8]), "total": r["total"], "prefs": r["prefectures"],
            "ok": r["status"] == "ok", "kind": "wb"} for r in wayback]
    pts.sort(key=lambda p: p["d"])
    last = pts[-1]["d"] if pts else None
    for h in history or []:
        d = _d(h["date"])
        if last is None or d > last:
            pts.append({"d": d, "total": h["total"], "prefs": len(h["counts"]),
                        "ok": True, "kind": "live"})
    pts.sort(key=lambda p: p["d"])
    return pts


def change_points(series: list[dict]) -> list[dict]:
    """センター数または都道府県数が前の点から変わった点（最初の点を含む）。"""
    out, prev = [], None
    for p in series:
        key = (p["total"], p["prefs"])
        if prev is None or key != (prev["total"], prev["prefs"]):
            out.append({**p, "prev": prev})
        prev = p
    return out


def _fmt(d: date) -> str:
    return d.isoformat()


def chart_svg(series: list[dict]) -> str:
    W, H, L, R, T, B = 900, 380, 62, 24, 24, 56
    d0 = date(series[0]["d"].year, 1, 1)
    d1 = date(series[-1]["d"].year + 1, 1, 1)
    span = (d1 - d0).days
    ymax = ((max(p["total"] for p in series) + 9) // 10) * 10
    px = lambda d: L + (d - d0).days / span * (W - L - R)          # noqa: E731
    py = lambda v: T + (1 - v / ymax) * (H - T - B)                 # noqa: E731

    g = []
    for v in range(0, ymax + 1, 10):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{py(v):.1f}" y2="{py(v):.1f}" class="tg"/>'
                 f'<text x="{L - 8}" y="{py(v) + 7:.1f}" text-anchor="end" class="tt">{v}</text>')
    for y in range(d0.year, d1.year + 1):
        if (y - d0.year) % 2 == 0:
            x = px(date(y, 1, 1))
            g.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{H - B}" y2="{H - B + 6}" class="ta"/>'
                     f'<text x="{x:.1f}" y="{H - B + 30}" text-anchor="middle" class="tt">{y}</text>')
    g.append(f'<line x1="{L}" x2="{W - R}" y1="{H - B}" y2="{H - B}" class="ta"/>')

    segs = []
    for a, b in zip(series, series[1:]):
        dash = ' stroke-dasharray="7 6"' if (b["d"] - a["d"]).days > GAP_DAYS else ""
        segs.append(f'<line x1="{px(a["d"]):.1f}" y1="{py(a["total"]):.1f}" '
                    f'x2="{px(b["d"]):.1f}" y2="{py(b["total"]):.1f}" class="ln"{dash}/>')

    marks, placed = [], []          # placed: 数字ラベルの位置 (x, y, 値)

    def put_label(x, y, v):
        """点の上に数字を置く。他のラベルと重なるなら下に置く。それでも重なるなら省く。"""
        for dy in (-12, 30):
            ly = y + dy
            if all(not (abs(x - ox) < 40 and abs(ly - oy) < 26) for ox, oy, _ in placed):
                placed.append((x, ly, v))
                marks.append(f'<text x="{x:.1f}" y="{ly:.1f}" text-anchor="middle" class="tv">{v}</text>')
                return

    cps = {(c["d"], c["total"]) for c in change_points(series)}
    for p in series:
        x, y = px(p["d"]), py(p["total"])
        cls = "mk" if p["ok"] else "mk open"
        if p["kind"] == "live":
            marks.append(f'<rect x="{x - 4.5:.1f}" y="{y - 4.5:.1f}" width="9" height="9" class="{cls}"/>')
        else:
            marks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" class="{cls}"/>')
    for p in series:
        if (p["d"], p["total"]) in cps:
            put_label(px(p["d"]), py(p["total"]), p["total"])
    last = series[-1]
    if not any(v == last["total"] and abs(px(last["d"]) - ox) < 90 for ox, _, v in placed):
        put_label(px(last["d"]), py(last["total"]), last["total"])

    label = (f"エンバーミングセンター数の推移（{_fmt(series[0]['d'])}から{_fmt(series[-1]['d'])}、"
             f"{series[0]['total']}から{series[-1]['total']}センター）")
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(label)}" class="trend">'
            '<style>.tg{stroke:var(--line);stroke-width:1}.ta{stroke:var(--mut);stroke-width:1.2}'
            '.tt{fill:var(--mut);font-size:22px}.tv{fill:var(--fg);font-size:22px;font-weight:700}'
            '.ln{stroke:var(--link);stroke-width:2;fill:none}'
            '.mk{fill:var(--link);stroke:var(--link);stroke-width:2}'
            '.mk.open{fill:var(--bg)}</style>'
            + "".join(g) + "".join(segs) + "".join(marks) + "</svg>")


def section_html(series: list[dict]) -> str:
    if len(series) < 2:
        return ""
    e = html.escape
    cps = change_points(series)
    n_ok = sum(1 for p in series if p["ok"] and p["kind"] == "wb")
    n_wb = sum(1 for p in series if p["kind"] == "wb")
    n_live = len(series) - n_wb
    cnt = f"Wayback Machineの保存{n_wb}件" + (f"と毎週の自動確認{n_live}件" if n_live else "")
    rows = []
    for c in cps:
        if c["prev"] is None:
            diff, when = "—", "最古の保存"
        else:
            dv = c["total"] - c["prev"]["total"]
            diff = f"{dv:+d}"
            when = f'{_fmt(c["prev"]["d"])} 〜 {_fmt(c["d"])}'
        chk = "一致" if c["ok"] else "照合不可"
        src = "（毎週の自動確認）" if c["kind"] == "live" else ""
        rows.append(f'<tr><td>{_fmt(c["d"])}{src}</td><td class="n">{c["total"]}</td>'
                    f'<td class="n">{diff}</td><td class="n">{c["prefs"]}</td>'
                    f'<td>{when}</td><td>{chk}</td></tr>')
    return (
        '<h2 id="trend">センター数の推移</h2>'
        f'<p class="note">{_fmt(series[0]["d"])}から{_fmt(series[-1]["d"])}までの、IFSA「組織案内」ページに載っていた'
        f'センター数です（{cnt}）。2015年3月より前は、Internet Archiveに保存がなく、'
        '分かりません（スマホでは、図を横にスクロールできます）。</p>'
        '<div class="tscroll chart">' + chart_svg(series) + '</div>' +
        '<p class="note">● ページ記載の合計と一致を確認できた点　○ 照合できなかった点（ページに合計表記がない時期）　'
        '■ 毎週の自動確認による点　破線は保存の間隔が半年を超える区間（その間の動きは分かりません）。</p>'
        '<h3 class="sub">数字が変わった時点</h3>'
        '<div class="tscroll"><table class="pt nw"><thead><tr><th>最初に確認できた保存日</th><th>センター数</th><th>前回比</th>'
        '<th>都道府県数</th><th>変更があった時期</th><th>ページ記載との照合</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table></div>'
        '<p class="note">「変更があった時期」は、数字が変わる前の最後の保存日から、変わったことを確認した保存日までの間です。'
        'この範囲のどこかで、IFSAのページの掲載が変わりました。'
        '点は、Internet Archive（Wayback Machine）が保存した日にページに載っていた数字を、'
        '現在のIFSAページと同じ方法で集計したものです。'
        f'ページ記載の合計と照合できたのは、Wayback由来の{n_wb}件のうち{n_ok}件で、'
        'それ以前の保存は照合手段がなく、参考値です。'
        'ここで分かるのは<b>IFSAのページの掲載内容の変化</b>で、実際の開設・閉鎖の日付、'
        'および増減の理由は、このデータからは分かりません。'
        '出典：<a href="https://web.archive.org/web/*/https://www.embalming.jp/organization/">'
        'Internet Archive Wayback Machine</a>。</p>')


# ---------------------------------------------------------------------------
# 年間実施件数（IFSA公表）との対比
# ---------------------------------------------------------------------------

def load_cases(path: Path) -> dict | None:
    if not Path(path).exists():
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _man(v: int) -> str:
    return "0" if v == 0 else f"{v // 10000}万"


def cases_chart_svg(series: list[dict], cases: dict) -> str:
    W, H, L, R = 900, 650, 70, 24
    P1 = (36, 236)        # センター数パネルの上端・下端
    P2 = (340, 596)       # 実施件数パネルの上端・下端
    d0, d1 = date(1988, 1, 1), date(2027, 1, 1)
    span = (d1 - d0).days
    px = lambda d: L + (d - d0).days / span * (W - L - R)                      # noqa: E731
    ymax1 = ((max(p["total"] for p in series) + 9) // 10) * 10
    ymax2 = ((max(r["cases"] for r in cases["annual"]) + 29999) // 30000) * 30000
    py1 = lambda v: P1[1] - v / ymax1 * (P1[1] - P1[0])                         # noqa: E731
    py2 = lambda v: P2[1] - v / ymax2 * (P2[1] - P2[0])                         # noqa: E731
    mid = lambda y: date(y, 7, 1)                                               # noqa: E731

    g = []
    for y in range(1988, 2027, 4):
        x = px(date(y, 1, 1))
        g.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{P1[0]}" y2="{P1[1]}" class="tg"/>'
                 f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{P2[0]}" y2="{P2[1]}" class="tg"/>'
                 f'<text x="{x:.1f}" y="{P2[1] + 32}" text-anchor="middle" class="tt">{y}</text>')
    for v in range(0, ymax1 + 1, 20):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{py1(v):.1f}" y2="{py1(v):.1f}" class="tg"/>'
                 f'<text x="{L - 8}" y="{py1(v) + 7:.1f}" text-anchor="end" class="tt">{v}</text>')
    for v in range(0, ymax2 + 1, 30000):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{py2(v):.1f}" y2="{py2(v):.1f}" class="tg"/>'
                 f'<text x="{L - 8}" y="{py2(v) + 7:.1f}" text-anchor="end" class="tt">{_man(v)}</text>')
    g.append(f'<line x1="{L}" x2="{W - R}" y1="{P1[1]}" y2="{P1[1]}" class="ta"/>'
             f'<line x1="{L}" x2="{W - R}" y1="{P2[1]}" y2="{P2[1]}" class="ta"/>')
    g.append(f'<text x="{L}" y="22" class="tp">センター数（組織案内ページの保存日時点）</text>'
             f'<text x="{L}" y="{P2[0] - 14}" class="tp">年間の実施件数（件）</text>')

    # センター数: データのない期間
    xs = px(series[0]["d"])
    g.append(f'<rect x="{L}" y="{P1[0]}" width="{xs - L:.1f}" height="{P1[1] - P1[0]}" class="nd"/>'
             f'<text x="{(L + xs) / 2:.1f}" y="{(P1[0] + P1[1]) / 2:.1f}" text-anchor="middle" class="tt">'
             f'センター数の保存なし</text>')
    segs, marks = [], []
    for a, b in zip(series, series[1:]):
        dash = ' stroke-dasharray="7 6"' if (b["d"] - a["d"]).days > GAP_DAYS else ""
        segs.append(f'<line x1="{px(a["d"]):.1f}" y1="{py1(a["total"]):.1f}" x2="{px(b["d"]):.1f}" '
                    f'y2="{py1(b["total"]):.1f}" class="ln"{dash}/>')
    for p in series:
        x, y = px(p["d"]), py1(p["total"])
        cls = "mk" if p["ok"] else "mk open"
        if p["kind"] == "live":
            marks.append(f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" class="{cls}"/>')
        else:
            marks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.8" class="{cls}"/>')
    # IFSA本文の表に書かれたセンター数（◇）
    offs = {2017: ("middle", 0, -14), 2024: ("end", -12, 6), 2025: ("start", 12, 6)}
    for r in cases.get("text_table", []):
        if r.get("centers") is None or not (d0 <= mid(r["year"]) <= d1):
            continue
        x, y = px(mid(r["year"])), py1(r["centers"])
        marks.append(f'<path d="M{x:.1f},{y - 6:.1f} L{x + 6:.1f},{y:.1f} L{x:.1f},{y + 6:.1f} '
                     f'L{x - 6:.1f},{y:.1f} Z" class="dm"/>')
        anc, dx, dy = offs.get(r["year"], ("middle", 0, -14))
        marks.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anc}" class="tv2">{r["centers"]}</text>')

    # 実施件数（棒）
    bars, labeled = [], {1988, 1996, 2004, 2012, 2020, 2025}
    for r in cases["annual"]:
        x = px(mid(r["year"]))
        y = py2(r["cases"])
        cls = "bar txt" if r.get("from") == "text" else "bar"
        bars.append(f'<rect x="{x - 7:.1f}" y="{y:.1f}" width="14" height="{P2[1] - y:.1f}" class="{cls}"/>')
        if r["year"] in labeled:
            bars.append(f'<text x="{x:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="tv">{r["cases"]:,}</text>')

    label = ("エンバーミングの年間実施件数（1988年191件から2025年88,531件）と、"
             "IFSA組織案内ページに載っていたセンター数の推移を、同じ時間軸に並べたグラフ")
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(label)}" class="trend">'
            '<style>.tg{stroke:var(--line);stroke-width:1}.ta{stroke:var(--mut);stroke-width:1.2}'
            '.tt{fill:var(--mut);font-size:21px}.tp{fill:var(--fg);font-size:22px;font-weight:700}'
            '.tv{fill:var(--fg);font-size:19px;font-weight:700}.tv2{fill:var(--fg);font-size:19px}'
            '.nd{fill:var(--line);opacity:.35}'
            '.ln{stroke:var(--link);stroke-width:2;fill:none}'
            '.mk{fill:var(--link);stroke:var(--link);stroke-width:2}.mk.open{fill:var(--bg)}'
            '.dm{fill:none;stroke:var(--fg);stroke-width:2}'
            '.bar{fill:var(--link);opacity:.85}.bar.txt{opacity:.5}</style>'
            + "".join(g) + "".join(segs) + "".join(marks) + "".join(bars) + "</svg>")


def cases_section_html(series: list[dict], cases: dict | None) -> str:
    if not cases or not cases.get("annual") or len(series) < 2:
        return ""
    # 表: IFSA本文の表の記載 と、同じ年に組織案内ページの保存で確認できた範囲
    rows = []
    for r in cases.get("text_table", []):
        y = r["year"]
        inyear = [p for p in series if p["d"].year == y]
        if r.get("centers") is None:
            ours = "—"
        elif not inyear:
            ours = "保存なし"
        else:
            def rng(vals):
                lo, hi = min(vals), max(vals)
                return f"{lo}" if lo == hi else f"{lo}〜{hi}"
            ours = f'{rng([p["prefs"] for p in inyear])}都道府県{rng([p["total"] for p in inyear])}センター'
        c = "—" if r.get("centers") is None else f'{r["prefectures"]}都道府県{r["centers"]}センター'
        cum = "—" if r.get("cumulative") is None else format(r["cumulative"], ",")
        rows.append(f'<tr><td>{y}</td><td class="n">{r["cases"]:,}</td><td class="n">{cum}</td>'
                    f'<td>{c}</td><td>{ours}</td></tr>')
    return (
        '<h2 id="cases">実施件数との対比</h2>'
        '<p class="note">上段は、IFSA「組織案内」ページに載っていたセンター数（前の節と同じ）、'
        '下段は、IFSAが公表しているエンバーミング処置の年間件数です。同じ時間軸に並べただけで、'
        '両者の関係についての判断は、ご覧になる方にお任せします（スマホでは、図を横にスクロールできます）。</p>'
        '<div class="tscroll chart">' + cases_chart_svg(series, cases) + '</div>'
        '<p class="note">棒＝年間実施件数（暦年。各年の中央に置いています）。1988〜2016年と2018〜2025年はグラフ画像の数値ラベル（2年おきと2025年）、'
        '薄い棒の2017年は同ページ本文の表の値です。◇＝同ページ本文の表に書かれたセンター数。'
        '●○■と破線は前の節と同じ意味です。センター数は保存日時点の値、実施件数は年間の値で、時点が異なります。</p>'
        '<h3 class="sub">IFSA本文の表の記載と、組織案内ページの保存との比較</h3>'
        '<div class="tscroll"><table class="pt nw"><thead><tr><th>年</th><th>年間実施件数</th><th>累計件数</th>'
        '<th>IFSA本文の表のセンター数</th><th>同じ年の組織案内ページの保存で確認できた範囲</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table></div>'
        '<p class="note">IFSAの2つのページで、同じ年のセンター数が一致しない場合があります（上の表）。'
        '理由（数え方の違い、表の書き直しなど）は、公表されている情報からは分かりません。'
        '実施件数・センター数とも、IFSAが自ら公表した数字で、第三者による検証はありません。'
        '出典：<a href="' + html.escape(cases["source_url"]) + '">IFSA「医療従事者の立場から」</a>'
        f'（{html.escape(cases["retrieved"])}確認）。</p>')
