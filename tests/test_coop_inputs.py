"""The co-op input loaders fall back instead of crashing (scripts/coop_inputs.py). No network: downloads are faked."""
from __future__ import annotations

import io
import shutil
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import coop_inputs  # noqa: E402


def nursery_frame(**cols):
    data = {"NURSERY_NA": ["A Nursery", "B Nursery"], "SPONSOR_NA": ["A Club", "B Club"], "COUNTY": ["Erie", "Centre"], "ID": [1, 2]}
    data.update(cols)
    return gpd.GeoDataFrame(data, geometry=[Point(-80.1, 42.1), Point(-77.8, 40.9)], crs="EPSG:4326")


def zipped_shapefile(g, tmp_path):
    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    g.to_file(shp_dir / "nurseries.shp")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for f in shp_dir.iterdir():
            z.write(f, f.name)
    return buf.getvalue()


def boom(url):
    raise AssertionError("must not download")


def test_local_file_is_used_without_downloading(tmp_path):
    nursery_frame().to_file(tmp_path / "Coop_nurseries.geojson", driver="GeoJSON")
    g = coop_inputs.load_coop_nurseries(tmp_path, fetch=boom)
    assert len(g) == 2 and {"NURSERY_NA", "SPONSOR_NA", "COUNTY", "ID"} <= set(g.columns)


def test_missing_file_with_downloading_off_returns_none(tmp_path):
    assert coop_inputs.load_coop_nurseries(tmp_path, download=False, fetch=boom) is None


def test_failed_download_returns_none_not_an_exception(tmp_path):
    def fail(url):
        raise ConnectionError("no network")
    assert coop_inputs.load_coop_nurseries(tmp_path, fetch=fail) is None


def test_a_non_zip_download_is_rejected(tmp_path):
    assert coop_inputs.load_coop_nurseries(tmp_path, fetch=lambda url: b"<html>error page</html>") is None
    assert not (tmp_path / "pasda_coop_nurseries").exists(), "a bad download must not be saved"


def test_download_is_saved_untouched_with_a_manifest_row_and_normalized(tmp_path):
    lower = nursery_frame().rename(columns={"NURSERY_NA": "nursery_na", "SPONSOR_NA": "sponsor_na", "COUNTY": "county"}).drop(columns="ID")
    data = zipped_shapefile(lower, tmp_path)
    g = coop_inputs.load_coop_nurseries(tmp_path, fetch=lambda url: data)
    assert len(g) == 2 and {"NURSERY_NA", "SPONSOR_NA", "COUNTY", "ID"} <= set(g.columns), "field names are upper-cased and ID is added"
    saved = list((tmp_path / "pasda_coop_nurseries").glob("*/*.zip"))
    assert len(saved) == 1 and saved[0].read_bytes() == data, "raw download is kept byte for byte"
    manifest = pd.read_csv(tmp_path / "manifest.csv")
    assert manifest.iloc[-1]["url"] == coop_inputs.PASDA_ZIP and manifest.iloc[-1]["records"] == 2


def test_an_earlier_download_is_reused_without_downloading_again(tmp_path):
    data = zipped_shapefile(nursery_frame(), tmp_path)
    coop_inputs.load_coop_nurseries(tmp_path, fetch=lambda url: data)
    again = coop_inputs.load_coop_nurseries(tmp_path, fetch=boom)
    assert len(again) == 2


def test_a_layer_without_nursery_names_is_unavailable(tmp_path):
    g = nursery_frame().rename(columns={"NURSERY_NA": "SOMETHING_ELSE"})
    assert coop_inputs.load_coop_nurseries(tmp_path, fetch=lambda url: zipped_shapefile(g, tmp_path)) is None


def xlsx_bytes():
    buf = io.BytesIO()
    rows = [[None] * 8] * 3 + [["sponsor", "nursery", "county", "stream", "section", "BK", "BN", "RB"], ["S", "N", "Erie", "Some Creek", 1, "X", "", ""]]
    pd.DataFrame(rows).to_excel(buf, index=False, header=False)
    return buf.getvalue()


def test_stockings_spreadsheet_local_copy_wins(tmp_path):
    p = tmp_path / "pfbc_coop" / "2026-09-27" / "cnu-stockings-website.xlsx"
    p.parent.mkdir(parents=True)
    p.write_bytes(xlsx_bytes())
    assert coop_inputs.latest_coop_stockings(tmp_path, fetch=boom) == p


def test_stockings_spreadsheet_downloads_when_missing_and_returns_none_on_failure(tmp_path):
    path = coop_inputs.latest_coop_stockings(tmp_path, fetch=lambda url: xlsx_bytes())
    assert path is not None and path.name == "cnu-stockings-website.xlsx" and path.exists()
    assert pd.read_csv(tmp_path / "manifest.csv").iloc[-1]["url"] == coop_inputs.PFBC_XLSX
    shutil.rmtree(tmp_path / "pfbc_coop")

    def fail(url):
        raise TimeoutError("slow")
    assert coop_inputs.latest_coop_stockings(tmp_path, fetch=fail) is None
    assert coop_inputs.latest_coop_stockings(tmp_path, download=False, fetch=boom) is None


def test_the_real_nursery_file_loads_with_the_columns_the_scripts_use():
    real = Path(__file__).resolve().parents[1] / "data" / "raw"
    if not (real / "Coop_nurseries.geojson").exists():
        pytest.skip("data/raw is git-ignored; this machine has no local copy")
    g = coop_inputs.load_coop_nurseries(real, download=False)
    assert len(g) == 165 and {"NURSERY_NA", "SPONSOR_NA", "COUNTY", "ID"} <= set(g.columns)


def script_03():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "scripts" / "03_coop_stockings.py"
    spec = importlib.util.spec_from_file_location("coop_script_03", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_03_leaves_nursery_coordinates_empty_when_locations_are_unavailable(monkeypatch):
    mod = script_03()
    monkeypatch.setattr(mod, "load_coop_nurseries", lambda: None)
    d = pd.DataFrame({"nursery": ["N"], "sponsor": ["S"]})
    out = mod.add_nursery_distance(d, gpd.GeoSeries([None]))
    assert out["nursery_lat"].isna().all() and out["nursery_lon"].isna().all() and out["nursery_to_water_mi"].isna().all()
    assert out["nursery_located_by"].isna().all()


def test_script_03_skips_cleanly_when_the_stocking_listing_is_unavailable(monkeypatch, tmp_path):
    mod = script_03()
    monkeypatch.setattr(mod, "latest_coop_stockings", lambda: None)
    monkeypatch.setattr(mod, "setup_logging", lambda name: None)
    monkeypatch.setattr(mod, "PROCESSED_DIR", tmp_path)
    mod.main()
    assert list(tmp_path.iterdir()) == [], "nothing is written when the co-op inputs are unavailable"
