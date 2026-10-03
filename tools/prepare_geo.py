"""開発用：元の都道府県GeoJSONを簡略化して data/japan_simplified.geojson を作る。

使い方:
    pip install shapely
    python tools/prepare_geo.py 元のjapan.geojson

元データ: https://github.com/dataofjapan/land （japan.geojson）
※ 公開前に、元データのライセンス/利用条件を必ずご自身で確認してください。
"""
import json
import sys

from shapely.geometry import MultiPolygon, mapping, shape

TOLERANCE = 0.012  # 度。大きいほど粗く・軽くなる


def _round(c):
    if isinstance(c[0], (list, tuple)):
        return [_round(x) for x in c]
    return [round(c[0], 4), round(c[1], 4)]


def main(src: str, dst: str = "data/japan_simplified.geojson") -> None:
    gj = json.load(open(src, encoding="utf-8"))
    feats = []
    for ft in gj["features"]:
        geom = shape(ft["geometry"])
        parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        kept = []
        for p in parts:
            if p.area < 0.0004:  # 極小の島は除く
                continue
            q = p.simplify(TOLERANCE, preserve_topology=True)
            if not q.is_empty and q.geom_type == "Polygon":
                kept.append(q)
        if not kept:
            continue
        m = mapping(MultiPolygon(kept))
        feats.append({
            "type": "Feature",
            "properties": {"name": ft["properties"]["nam_ja"]},
            "geometry": {"type": m["type"], "coordinates": _round(m["coordinates"])},
        })
    json.dump({"type": "FeatureCollection", "features": feats},
              open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("wrote", dst, len(feats), "features")


if __name__ == "__main__":
    main(*sys.argv[1:])
