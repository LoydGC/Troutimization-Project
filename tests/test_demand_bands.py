"""Proximity band logic in scripts/08_demand.py: where an empty distance band's share goes (decision 2026-10-04)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("demand_08", SCRIPTS / "08_demand.py")
demand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demand)


def test_empty_band_goes_to_next_band_out():
    # bands 0 and 2 empty: 0 -> 1, 2 -> 3
    has = np.array([[False, True, False, True]])
    assert demand.band_targets(has).tolist() == [[1, 1, 3, 3]]


def test_empty_bands_past_the_last_live_band_go_in():
    # nothing beyond band 1: bands 2 and 3 fall back to band 1
    has = np.array([[True, True, False, False]])
    assert demand.band_targets(has).tolist() == [[0, 1, 1, 1]]


def test_rates_place_every_angler_day_once():
    # origin 0: nothing within band 0, so its 0.5 near share all lands on band 1's section, not spread over bands 1-2
    band = np.array([[1, 2, 2], [0, 1, 2]])
    length = np.array([2.0, 1.0, 3.0])
    shares = np.array([[0.5, 0.3, 0.2], [0.5, 0.3, 0.2]])
    rate = demand.per_mile_rates(band, length, shares)
    assert np.allclose(rate @ length, 1)
    assert np.isclose(rate[0, 0] * length[0], 0.8)  # band 1 gets its own 0.3 + band 0's 0.5
    assert np.isclose(rate[0, 1] * length[1] + rate[0, 2] * length[2], 0.2)
    assert np.allclose(rate[1] * length, shares[1])  # no empty band: shares unchanged
