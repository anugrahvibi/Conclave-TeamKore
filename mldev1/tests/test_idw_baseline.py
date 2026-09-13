"""
Unit tests for IDW Interpolation Baseline
"""

import numpy as np
import pytest
from mldev1.models.idw_baseline import haversine_distance, idw_interpolate, IDWBaselineModel

def test_haversine_known_distance():
    # Distance between Kochi (9.9312, 76.2673) and Trivandrum (8.5241, 76.9366) is ~175-185 km
    dist = haversine_distance(9.9312, 76.2673, np.array([8.5241]), np.array([76.9366]))
    assert 170 < dist[0] < 195

def test_idw_exact_match():
    # Target coincides with one of the source points
    target_lat, target_lon = 10.0, 76.0
    source_lats = np.array([10.0, 10.5, 11.0])
    source_lons = np.array([76.0, 76.5, 77.0])
    source_values = np.array([28.5, 31.0, 33.0])

    val = idw_interpolate(target_lat, target_lon, source_lats, source_lons, source_values)
    assert abs(val - 28.5) < 1e-4

def test_idw_equidistant_points():
    # Target is in the exact center of two points
    # Point 1: (10.0, 76.0), Point 2: (10.0, 77.0), Target: (10.0, 76.5)
    source_lats = np.array([10.0, 10.0])
    source_lons = np.array([76.0, 77.0])
    source_values = np.array([20.0, 30.0])

    val = idw_interpolate(10.0, 76.5, source_lats, source_lons, source_values, power=2.0)
    # Since equidistant, average should be exactly 25.0
    assert pytest.approx(val, rel=1e-3) == 25.0

def test_idw_k_nearest_limiting():
    # 5 points, target close to first 2 points, distant from others
    source_lats = np.array([10.01, 10.02, 12.0, 13.0, 14.0])
    source_lons = np.array([76.01, 76.02, 76.0, 76.0, 76.0])
    source_values = np.array([25.0, 26.0, 100.0, 100.0, 100.0])

    # With k=2, only first 2 points should be considered; distant 100.0 values ignored
    val = idw_interpolate(10.0, 76.0, source_lats, source_lons, source_values, k_nearest=2)
    assert 24.0 <= val <= 27.0
