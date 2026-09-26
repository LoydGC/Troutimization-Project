import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common  # noqa: E402

LAYER = "https://example.test/arcgis/rest/services/X/MapServer/0"


class FakeResponse:
    def __init__(self, body, status=200):
        self.status_code = status
        self.content = json.dumps(body).encode()
        self.headers = {"Content-Type": "application/json"}
        self.from_cache = False

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        raise RuntimeError(f"HTTP {self.status_code}")


def make_features(n):
    return [{"type": "Feature", "id": i, "properties": {"OBJECTID": i},
             "geometry": {"type": "Point", "coordinates": [0, 0]}} for i in range(1, n + 1)]


class FakeArcGIS:
    """Serves layer metadata, a count, and pages of features, like an ArcGIS MapServer layer."""

    def __init__(self, n=5, max_records=2, reported_count=None, pagination=True, fmt="JSON, geoJSON"):
        self.features = make_features(n)
        self.max_records, self.pagination, self.fmt = max_records, pagination, fmt
        self.reported_count = n if reported_count is None else reported_count
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        if url == LAYER:
            return FakeResponse({"maxRecordCount": self.max_records, "objectIdField": "OBJECTID",
                                 "supportedQueryFormats": self.fmt,
                                 "advancedQueryCapabilities": {"supportsPagination": self.pagination},
                                 "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}]})
        if params.get("returnCountOnly") == "true":
            return FakeResponse({"count": self.reported_count})
        start, size = params["resultOffset"], params["resultRecordCount"]
        return FakeResponse({"type": "FeatureCollection", "features": self.features[start:start + size]})


def test_fetch_layer_pages_and_saves_raw(tmp_path):
    server = FakeArcGIS(n=5, max_records=2)
    fc = common.fetch_layer(LAYER, "src", "layer", session=server, raw_dir=tmp_path)

    assert [f["id"] for f in fc["features"]] == [1, 2, 3, 4, 5]
    page_calls = [p for u, p in server.calls if "resultOffset" in p]
    assert [p["resultOffset"] for p in page_calls] == [0, 2, 4]
    assert all(p["resultRecordCount"] == 2 and p["outSR"] == "4326" and p["f"] == "geojson" for p in page_calls)

    saved = sorted(p.name for p in tmp_path.glob("src/*/*"))
    assert saved == ["layer_count.json", "layer_meta.json", "layer_page000.geojson",
                     "layer_page001.geojson", "layer_page002.geojson"]
    rows = list(csv.DictReader((tmp_path / "manifest.csv").open()))
    assert len(rows) == 5
    assert [r["records"] for r in rows if r["path"].endswith(".geojson")] == ["2", "2", "1"]
    assert all(r["url"].startswith(LAYER) for r in rows)


def test_fetch_layer_count_mismatch_raises(tmp_path):
    server = FakeArcGIS(n=5, reported_count=6)
    with pytest.raises(AssertionError, match="server count 6, downloaded 5"):
        common.fetch_layer(LAYER, "src", "layer", session=server, raw_dir=tmp_path)


@pytest.mark.parametrize("kwargs, message", [({"pagination": False}, "pagination"), ({"fmt": "JSON"}, "geojson")])
def test_fetch_layer_rejects_unsupported_layers(tmp_path, kwargs, message):
    with pytest.raises(common.ArcGISError, match=message):
        common.fetch_layer(LAYER, "src", "layer", session=FakeArcGIS(**kwargs), raw_dir=tmp_path)


def test_save_raw_is_idempotent(tmp_path):
    for _ in range(2):
        path = common.save_raw("src", "a.json", "{}", "https://x.test/a", records=0, raw_dir=tmp_path, date="2026-01-01")
    assert path == tmp_path / "src" / "2026-01-01" / "a.json"
    assert len(list(csv.DictReader((tmp_path / "manifest.csv").open()))) == 1


def test_polite_session_retries_arcgis_error_then_stops(monkeypatch):
    sleeps = []
    monkeypatch.setattr(common.time, "sleep", sleeps.append)
    session = common.PoliteSession(max_retries=2, cache_path=None)
    monkeypatch.setattr(session.http, "get", lambda *a, **k: FakeResponse({"error": {"code": 500}}))
    with pytest.raises(common.ServerRefused):
        session.get(LAYER)
    assert [s for s in sleeps if s >= 1] == [1.0, 2.0]  # backoff between the 3 attempts


def test_polite_session_waits_between_requests_to_same_host(monkeypatch):
    clock = {"t": 100.0}
    sleeps = []
    monkeypatch.setattr(common.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(common.time, "sleep", sleeps.append)
    session = common.PoliteSession(cache_path=None)
    monkeypatch.setattr(session.http, "get", lambda *a, **k: FakeResponse({"ok": 1}))
    session.get(LAYER)
    clock["t"] += 0.25
    session.get(LAYER)
    assert sleeps == [pytest.approx(0.75)]
