"""2003年ページ取得道具のテスト（ネットワークは使わない）。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE))
import wayback_2003 as w3  # noqa: E402
from test_wayback import FakeResp  # noqa: E402

MAP = '<html><body><h1>エンバーミングセンター案内</h1><a href="0602-1.html"><img alt="北海道"></a></body></html>'
PAGE = "<html><body><table><tr><td>株式会社テスト</td><td>北海道札幌市</td></tr></table><script>x()</script></body></html>"


class Sess:
    def __init__(self, missing=()):
        self.headers, self.calls, self.missing = {}, [], missing

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        name = url.rsplit("/", 1)[1].removesuffix(".html")
        if name in self.missing and "20030820110753" in url:
            return FakeResp(status=404)
        if name in self.missing and "/2003id_/" in url:
            return FakeResp(status=404)
        body = MAP if name == "0602" else PAGE
        return FakeResp(content=body.encode("cp932"))


def test_to_text_extracts_cells_links_and_skips_script():
    t, links = w3.to_text(MAP)
    assert "エンバーミングセンター案内" in t and ("0602-1.html", "北海道") in links
    t2, _ = w3.to_text(PAGE)
    assert "株式会社テスト" in t2 and "x()" not in t2


def test_run_fetches_13_pages_and_records_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(w3.wb.time, "sleep", lambda s: None)
    monkeypatch.setattr(w3.time, "sleep", lambda s: None)
    rep = w3.run(Sess(missing={"0602-7"}), out_dir=tmp_path, sleep=0)
    assert len(rep) == 13 and rep["0602-7"].startswith("取得失敗")
    assert (tmp_path / "0602.html").exists() and not (tmp_path / "0602-7.html").exists()
    txt = (tmp_path / "ifsa_2003.txt").read_text(encoding="utf-8")
    assert "0602-12.html" in txt and "株式会社テスト" in txt and "取得失敗" in txt
