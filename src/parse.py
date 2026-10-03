"""IFSA「組織案内」ページから、都道府県別のエンバーミングセンター一覧を取り出す。

方針:
  * 都道府県名の見出し(h3/h4/h5)の直後の表を、その県の表とみなす。
  * 表のセルのうち「本社」を含むものは会社名セル、それ以外の非空セルは施設名セル。
    （rowspan で会社名セルが省略された行や、会社名だけの行が混ざっても数えられる）
  * ページ自身が書く合計「(33都道府県・事業会社36社・94センター)」と集計が
    一致しなければ ParseError を出し、誤った地図を公開しない。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

DECLARED_RE = re.compile(
    r"(\d+)\s*都道府県\s*[・･]\s*事業会社\s*(\d+)\s*社\s*[・･]\s*(\d+)\s*センター"
)


class ParseError(RuntimeError):
    pass


@dataclass
class Snapshot:
    # 県名 -> ["会社名｜施設名 所在地", ...]（ページ記載順・重複も保持）
    facilities: dict[str, list[str]] = field(default_factory=dict)
    declared: tuple[int, int, int] | None = None  # (都道府県数, 会社数, センター数)

    @property
    def counts(self) -> dict[str, int]:
        return {p: len(v) for p, v in self.facilities.items()}

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def companies(self, pref: str) -> list[str]:
        seen: list[str] = []
        for f in self.facilities.get(pref, []):
            c = f.split("｜", 1)[0]
            if c and c not in seen:
                seen.append(c)
        return seen


def _norm(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", s).strip()


def parse(html: str) -> Snapshot:
    soup = BeautifulSoup(html, "html.parser")
    text = _norm(soup.get_text(" ", strip=True))
    m = DECLARED_RE.search(text)
    snap = Snapshot(declared=tuple(int(x) for x in m.groups()) if m else None)

    for table in soup.find_all("table"):
        head = table.find_previous(["h2", "h3", "h4", "h5"])
        pref = _norm(head.get_text()) if head else ""
        if pref not in PREFECTURES:
            continue
        company = ""
        rows: list[str] = snap.facilities.setdefault(pref, [])
        for tr in table.find_all("tr"):
            if tr.find("th"):
                continue
            for td in tr.find_all("td"):
                t = _norm(td.get_text(" ", strip=True))
                if not t or t in ("会社名", "施設名"):
                    continue
                if "本社" in t:
                    company = _norm(t.split("本社")[0])
                else:
                    rows.append(f"{company}｜{t}")
    snap.facilities = {p: v for p, v in snap.facilities.items() if v}
    validate(snap)
    return snap


def validate(snap: Snapshot) -> None:
    if snap.declared is None:
        raise ParseError("ページ内に合計表記（○都道府県・事業会社○社・○センター）が見つかりません。"
                         "ページの書式が変わった可能性があります。")
    n_pref, _n_co, n_center = snap.declared
    if snap.total != n_center:
        raise ParseError(f"センター数の不一致: 集計={snap.total} / ページ記載={n_center}")
    if len(snap.facilities) != n_pref:
        raise ParseError(f"都道府県数の不一致: 集計={len(snap.facilities)} / ページ記載={n_pref}")
