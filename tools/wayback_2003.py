"""2003年8月20日保存の IFSA「エンバーミングセンター案内」（地図ページ＋リンク先12ページ）を取得する一回限りの道具。

使い方（GitHub Actions の wayback2003.yml が実行します。手元でも動きます）:
    python tools/wayback_2003.py

出力:
    data/raw2003/<ページ名>.html   … 取得した生のHTML（そのまま）
    data/raw2003/ifsa_2003.txt     … 全ページの本文テキスト（人が読む用。解析前の素材）

方針:
  * 保存日時 20030820110753 の版を優先して取得する。取れなければ、2003年に最も近い保存で再試行する。
  * 読み取り（会社名・施設数の判定）はここでは行わない。本文テキストを人が確認してから、別途データ化する。
  * Internet Archive に負荷をかけないよう、1件ごとに待機する。
"""
from __future__ import annotations

import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wayback_history as wb  # noqa: E402

TS = "20030820110753"
BASE = "http://www.embalming.jp/html/{name}.html"
NAMES = ["0602"] + [f"0602-{i}" for i in range(1, 13)]
OUT_DIR = ROOT / "data" / "raw2003"


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._skip = 0
        self._href = None
        self._label: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("br", "p", "tr", "div", "li", "table", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")
        if tag in ("td", "th"):
            self.parts.append(" | ")
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._label = []
        if tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self.parts.append(f"[画像:{alt}]")
                self._label.append(alt)

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag == "a" and self._href:
            self.links.append((self._href, "".join(self._label).strip()))
            self._href = None

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)
            self._label.append(data)


def to_text(html: str) -> tuple[str, list[tuple[str, str]]]:
    p = _Text()
    p.feed(html)
    txt = "".join(p.parts)
    txt = re.sub(r"[ \t　]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt).strip()
    return txt, p.links


def fetch_page(session, name: str, sleep: float) -> tuple[bytes | None, str]:
    url = BASE.format(name=name)
    tried = []
    for stamp in (TS, "2003"):
        raw = f"https://web.archive.org/web/{stamp}id_/{url}"
        try:
            r = wb._get(session, raw)
            time.sleep(sleep)
            return r.content, f"{stamp}（{'指定の版' if stamp == TS else '2003年に最も近い保存'}）"
        except RuntimeError as e:
            tried.append(f"{stamp}: {e}")
            time.sleep(sleep)
    return None, "取得失敗: " + " / ".join(tried)


def run(session, out_dir: Path = OUT_DIR, sleep: float = wb.SLEEP) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    sections, report = [], {}
    for name in NAMES:
        content, how = fetch_page(session, name, sleep)
        report[name] = how
        if content is None:
            sections.append(f"===== {name}.html =====\n（{how}）\n")
            continue
        (out_dir / f"{name}.html").write_bytes(content)
        text, links = to_text(wb.decode(content))
        link_lines = "\n".join(f"  {label or '(ラベルなし)'} -> {href}" for href, label in links)
        sections.append(f"===== {name}.html（{how}）=====\n{text}\n\n--- リンク ---\n{link_lines}\n")
    (out_dir / "ifsa_2003.txt").write_text("\n".join(sections), encoding="utf-8")
    return report


def main() -> int:
    report = run(wb.make_session())
    for k, v in report.items():
        print(f"{k}: {v}")
    ng = [k for k, v in report.items() if v.startswith("取得失敗")]
    print(f"\n取得 {len(report) - len(ng)}/{len(report)} ページ。失敗: {ng or 'なし'}")
    return 0 if len(ng) < len(report) else 1


if __name__ == "__main__":
    sys.exit(main())
