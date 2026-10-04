"""事業者別の集計。IFSAページの会社名表記だけに基づく（資本関係などは考慮しない）。

* 「○○グループ ○○株式会社」のように、会社名の前に「…グループ」が付く表記は、
  そのグループ名でまとめ、内訳として会社名を併記する。
* 空白の有無だけが違う表記（例: 「ＳＯＵセレモニー株式会社」と「ＳＯＵセレモニー 株式会社」）は
  同じ事業者として数える。
* 同一の会社名はページ内のどこに出ても同一事業者として数える（IFSAの「事業会社36社」の数え方と
  一致することを確認済み）。
"""
from __future__ import annotations

import re

from parse import PREFECTURES, Snapshot

_GROUP_RE = re.compile(r"^(\S+?グループ)\s+(\S.*)$")
_SUFFIX_ONLY = {"株式会社", "有限会社", "合同会社", "一般社団法人"}


def split_company(raw: str) -> tuple[str | None, str]:
    """'燦ホールディングスグループ 株式会社公益社' -> ('燦ホールディングスグループ', '株式会社公益社')"""
    raw = raw.strip()
    m = _GROUP_RE.match(raw)
    if m and re.sub(r"\s+", "", m.group(2)) not in _SUFFIX_ONLY:
        group, name = m.group(1), m.group(2)
    else:
        group, name = None, raw
    return group, re.sub(r"\s+", "", name)


def _pref_sorted(prefs: dict[str, int]) -> dict[str, int]:
    return dict(sorted(prefs.items(), key=lambda kv: (-kv[1], PREFECTURES.index(kv[0]))))


def company_stats(snap: Snapshot) -> list[dict]:
    """事業者(またはグループ)ごとの集計。センター数の多い順。

    各要素: {name, is_group, total, prefs{県:数}, members[{name,total,prefs}]}
    """
    members: dict[str, dict] = {}
    for pref, facs in snap.facilities.items():
        for f in facs:
            raw = f.split("｜", 1)[0]
            group, name = split_company(raw)
            m = members.setdefault(name, {"name": name, "group": None, "prefs": {}})
            if group and not m["group"]:
                m["group"] = group
            m["prefs"][pref] = m["prefs"].get(pref, 0) + 1

    entries: dict[str, dict] = {}
    for m in members.values():
        key = m["group"] or m["name"]
        e = entries.setdefault(key, {"name": key, "is_group": False, "prefs": {}, "members": []})
        e["is_group"] = e["is_group"] or bool(m["group"])
        for p, n in m["prefs"].items():
            e["prefs"][p] = e["prefs"].get(p, 0) + n
        e["members"].append({"name": m["name"], "total": sum(m["prefs"].values()),
                             "prefs": _pref_sorted(m["prefs"])})

    out = []
    for e in entries.values():
        e["total"] = sum(e["prefs"].values())
        e["prefs"] = _pref_sorted(e["prefs"])
        e["members"].sort(key=lambda x: (-x["total"], x["name"]))
        out.append(e)
    out.sort(key=lambda x: (-x["total"], x["name"]))
    return out


def count_companies(entries: list[dict]) -> int:
    return sum(len(e["members"]) for e in entries)
