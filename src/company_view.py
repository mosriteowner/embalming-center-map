"""「社別」の一覧（五十音順）。IFSAページの会社名表記だけに基づく。件数順ではなく、読みの五十音順に並べる。

* 読みは data/company_readings.json（国税庁の法人番号公表サイトのフリガナなど、根拠つき）から引く。
* 読みが未登録の事業者は、末尾に「読み未登録」としてまとめる（更新は止めない）。
* 並べ替えは、小さい仮名を大きい仮名として扱い、長音符・中点・濁点半濁点の違いを無視した読みの順（一次比較）、
  同じ場合は元の読みの順とする。
"""
from __future__ import annotations

import html
import json
import unicodedata
from pathlib import Path

from companies import company_stats

_SMALL = str.maketrans("ァィゥェォッャュョヮ", "アイウエオツヤユヨワ")


def norm_name(s: str) -> str:
    return "".join(unicodedata.normalize("NFKC", s).split())


_ROWS = {"ア": "アカサタナハマヤラワガザダバパァ", "イ": "イキシチニヒミリギジヂビピィ", "ウ": "ウクスツヌフムユルグズヅブプゥヴ",
         "エ": "エケセテネヘメレゲゼデベペェ", "オ": "オコソトノホモヨロヲゴゾドボポォ"}
_VOWEL = {c: v for v, cs in _ROWS.items() for c in cs}


def kana_key(kana: str) -> tuple[str, str]:
    """五十音順の一次キー。長音符は直前の仮名の母音に置き換え（オーム＝オオム）、中点は無視、濁点・半濁点の違いは無視する。"""
    s = unicodedata.normalize("NFKC", kana).translate(_SMALL).replace("・", "")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    out = []
    for c in s:
        out.append(_VOWEL.get(out[-1], "") if c == "ー" and out else c)
    return "".join(out), kana


def load_readings(path: Path) -> dict | None:
    if not Path(path).exists():
        return None
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "companies": {norm_name(r["name"]): r for r in d.get("companies", [])},
        "groups": {norm_name(r["name"]): r for r in d.get("groups", [])},
    }


def build(snap, readings: dict | None) -> tuple[list[dict], list[str]]:
    """並べ替え済みの行と、読み未登録の事業者名を返す。"""
    readings = readings or {"companies": {}, "groups": {}}
    missing: list[str] = []

    def lookup(table: dict, name: str):
        r = table.get(norm_name(name))
        if r is None:
            missing.append(name)
        return r

    items = []
    for e in company_stats(snap):
        mem = []
        for m in e["members"]:
            r = lookup(readings["companies"], m["name"])
            mem.append({**m, "kana": r["kana"] if r else None})
        mem.sort(key=lambda m: (m["kana"] is None, kana_key(m["kana"] or ""), m["name"]))
        if e["is_group"]:
            r = lookup(readings["groups"], e["name"])
            kana = r["kana"] if r else None
        else:
            kana = mem[0]["kana"]
        items.append({**e, "members": mem, "kana": kana})
    items.sort(key=lambda x: (x["kana"] is None, kana_key(x["kana"] or ""), x["name"]))
    return items, sorted(set(missing))


def view_html(snap, readings: dict | None) -> tuple[str, list[str]]:
    e = html.escape
    items, missing = build(snap, readings)

    def short(p):
        return p if p == "北海道" else p[:-1]

    def prefs(d):
        return "・".join(f"{e(short(p))}{n}" for p, n in d.items())

    def kana_html(k):
        return f'<span class="sm">{e(k)}</span>' if k else '<span class="sm">読み未登録</span>'

    body = []
    for x in items:
        rows = []
        if x["is_group"]:
            rows.append(f'<tr class="gh"><th scope="row">{e(x["name"])}<br>{kana_html(x["kana"])}</th>'
                        f'<td class="n">{x["total"]}</td><td>{prefs(x["prefs"])}</td></tr>')
            for m in x["members"]:
                rows.append(f'<tr class="gm"><th scope="row">{e(m["name"])}<br>{kana_html(m["kana"])}</th>'
                            f'<td class="n">{m["total"]}</td><td>{prefs(m["prefs"])}</td></tr>')
        else:
            m = x["members"][0]
            rows.append(f'<tr><th scope="row">{e(m["name"])}<br>{kana_html(m["kana"])}</th>'
                        f'<td class="n">{m["total"]}</td><td>{prefs(m["prefs"])}</td></tr>')
        body.append("<tbody>" + "".join(rows) + "</tbody>")
    n_co = sum(len(x["members"]) for x in items)
    inner = (
        '<h2>事業者別（読みの五十音順）</h2>'
        f'<p class="note">IFSA「組織案内」ページに記載された事業者（{n_co}社）を、読みの五十音順に並べています。'
        'センター数の多い順ではありません。「○○グループ」の表記はIFSAのページの記載に従ってまとめたもので、'
        '資本関係などの実態は反映していません。同じ会社名は、ページのどこに出ても同一の事業者として数えています。'
        '読みは、国税庁の法人番号公表サイトのフリガナを基本とし、一部は登記や会社サイトの表記によります。'
        'IFSAの表記と法人の正式名称が異なる場合があります。県名の後の数字はセンター数です。</p>'
        '<div class="tscroll"><table class="pt co"><thead><tr><th>事業者（読み）</th><th>センター数</th>'
        '<th>県別の内訳</th></tr></thead>' + "".join(body) + '</table></div>')
    return inner, missing
