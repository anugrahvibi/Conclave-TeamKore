"""Temporary profiler: times each stage of the village forecast + advisory path."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

t0 = time.perf_counter()
from backend.app.services.spatial_service import spatial_service
t1 = time.perf_counter()
from backend.app.services.forecast_service import forecast_service
t2 = time.perf_counter()
from backend.app.services.advisory_service import advisory_service
t3 = time.perf_counter()

print(f"import spatial:   {t1-t0:8.3f}s")
print(f"import forecast:  {t2-t1:8.3f}s")
print(f"import advisory:  {t3-t2:8.3f}s")

village = spatial_service.get_village("KL_PANCH_0001")
print(f"village lookup:   {time.perf_counter()-t3:8.3f}s")

# Time a single forecast
tf = time.perf_counter()
fc = forecast_service.get_forecast_for_village("KL_PANCH_0001")
t_fc = time.perf_counter() - tf
print(f"one forecast:     {t_fc:8.3f}s")

# Time second forecast (warm)
tf = time.perf_counter()
forecast_service.get_forecast_for_village("KL_PANCH_0002")
print(f"second forecast:  {time.perf_counter()-tf:8.3f}s")

# Time one advisory
ta = time.perf_counter()
advisory_service.get_advisory_for_village("KL_PANCH_0001")
t_adv = time.perf_counter() - ta
print(f"one advisory:     {t_adv:8.3f}s (forecast part ~{t_fc:.3f}s)")

# Break down forecast internals for one village
import numpy as np
from backend.app.services.forecast_service import haversine_km
from backend.app.config import settings

v = spatial_service.get_village("KL_PANCH_0003")
tA = time.perf_counter()
steps = 0
for ts in forecast_service.timestamps:
    ts_df = forecast_service.df_blocks[forecast_service.df_blocks["timestamp"] == ts]
    dists = np.array([haversine_km(v["lat"], v["lon"], slat, slon) for slat, slon in zip(ts_df["lat"].values, ts_df["lon"].values)])
    steps += 1
tB = time.perf_counter()
print(f"IDW part only:    {tB-tA:8.3f}s ({steps} steps, {len(ts_df)} stations/step)")

tC = time.perf_counter()
n = 0
for ts in forecast_service.timestamps:
    ts_df = forecast_service.df_blocks[forecast_service.df_blocks["timestamp"] == ts]
    feat = {"temp_c": 25.0, "rain_mm": 2.0, "humidity_pct": 75.0}
    stat = {"elevation_m": v["static_features"]["elevation_m"], "dist_to_water_km": v["static_features"]["dist_to_water_km"], "land_cover": v["static_features"]["land_cover"]}
    if forecast_service.pipeline.correction_model.is_trained:
        forecast_service.pipeline.correction_model.predict(feat, stat)
    n += 1
tD = time.perf_counter()
print(f"ML predict only:  {tD-tC:8.3f}s ({n} predicts)")
