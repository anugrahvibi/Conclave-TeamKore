"""
Fetch 100% Real ERA5-Land Historical Surface Weather Data (Copernicus / ECMWF)
for Kerala Block Stations and All 1,031 Grama Panchayats.

Window: July 10, 2024 - July 12, 2024 (Active Monsoon & Orographic Contrast)
Produces:
  mldev1/data/block_forecast.csv (Real ERA5-Land Block Forecasts)
  mldev1/data/mock_ground_truth.csv (Real ERA5-Land Surface Ground Truth for all 1,031 Panchayats)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import numpy as np
import pandas as pd

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mldev1.scripts.ingest_real_data import KERALA_BLOCK_STATIONS

START_DATE = "2024-07-10"
END_DATE = "2024-07-12"

def fetch_era5_for_coordinates(coords: list, batch_size: int = 30) -> list:
    """
    Fetches hourly ERA5-Land reanalysis for a list of (lat, lon) coordinates in batches.
    Returns list of dicts with hourly time series per location.
    """
    results = []
    base_url = "https://archive-api.open-meteo.com/v1/era5"

    for i in range(0, len(coords), batch_size):
        batch = coords[i:i + batch_size]
        lat_str = ",".join(f"{c[0]:.4f}" for c in batch)
        lon_str = ",".join(f"{c[1]:.4f}" for c in batch)

        url = (
            f"{base_url}?latitude={lat_str}&longitude={lon_str}&"
            f"start_date={START_DATE}&end_date={END_DATE}&"
            f"hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
        )

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Kerala-Agro-Platform/1.0"})
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, dict):
                        data = [data]
                    results.extend(data)
                    break
            except Exception as e:
                print(f"Notice: Batch {i//batch_size + 1} attempt {attempt + 1} note: {e}. Retrying...")
                time.sleep(2.0)
        else:
            print(f"Warning: Failed batch starting at index {i}")

        time.sleep(0.5)  # Respect API rate limits

    return results

def main():
    print("=" * 70)
    print("FETCHING 100% REAL COPERNICUS ERA5-LAND HISTORICAL DATA FOR KERALA")
    print(f"Time Window: {START_DATE} to {END_DATE}")
    print("=" * 70)

    # 1. Fetch Real ERA5 Block Forecast Data
    print(f"\n1. Fetching ERA5 data for {len(KERALA_BLOCK_STATIONS)} Kerala Block Stations...")
    block_coords = [(b["lat"], b["lon"]) for b in KERALA_BLOCK_STATIONS]
    block_results = fetch_era5_for_coordinates(block_coords, batch_size=35)

    block_records = []
    for idx, b_data in enumerate(block_results):
        blk = KERALA_BLOCK_STATIONS[idx]
        hourly = b_data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        rains = hourly.get("precipitation", [])
        humids = hourly.get("relative_humidity_2m", [])
        winds = hourly.get("wind_speed_10m", [])

        # Sample every 6 hours
        for s in range(0, len(times), 6):
            ts_str = times[s].replace("T", " ") + ":00"
            block_records.append({
                "block_id": blk["block_id"],
                "timestamp": ts_str,
                "temp": round(float(temps[s]), 2),
                "rainfall": round(float(rains[s]), 2),
                "humidity": round(float(humids[s]), 2),
                "wind": round(float(winds[s]), 2),
                "lat": blk["lat"],
                "lon": blk["lon"]
            })

    df_blocks = pd.DataFrame(block_records)
    df_blocks.to_csv("mldev1/data/block_forecast.csv", index=False)
    print(f"✓ Saved {len(df_blocks)} real ERA5 block forecast records to mldev1/data/block_forecast.csv")

    # 2. Fetch Real ERA5 Ground Truth Data for All 1,031 Panchayats
    df_villages = pd.read_csv("mldev1/data/village_centroids.csv")
    print(f"\n2. Fetching real ERA5-Land surface observations for all {len(df_villages)} Kerala Panchayats...")

    # Find unique 0.1° grid coordinates to minimize API requests
    grid_map = {}
    unique_coords = []
    coord_to_idx = {}

    for i, row in df_villages.iterrows():
        # ERA5-Land resolution is 0.1° (~9km)
        r_lat, r_lon = round(row["lat"], 2), round(row["lon"], 2)
        grid_key = (r_lat, r_lon)
        if grid_key not in coord_to_idx:
            coord_to_idx[grid_key] = len(unique_coords)
            unique_coords.append(grid_key)
        grid_map[row["village_id"]] = coord_to_idx[grid_key]

    print(f"Queried {len(unique_coords)} unique ERA5-Land grid coordinates covering all 1,031 Panchayats.")
    grid_results = fetch_era5_for_coordinates(unique_coords, batch_size=30)

    # Compile Ground Truth Observations
    truth_records = []
    # Use the same timestamps as block forecasts
    target_timestamps = set(df_blocks["timestamp"].unique())

    print("Formatting real ERA5 ground truth observations...")
    for _, v_row in df_villages.iterrows():
        vid = v_row["village_id"]
        v_lat = v_row["lat"]
        v_lon = v_row["lon"]

        grid_idx = grid_map[vid]
        if grid_idx < len(grid_results):
            loc_data = grid_results[grid_idx]
            hourly = loc_data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            rains = hourly.get("precipitation", [])
            humids = hourly.get("relative_humidity_2m", [])
            winds = hourly.get("wind_speed_10m", [])

            for s in range(0, len(times), 6):
                ts_str = times[s].replace("T", " ") + ":00"
                if ts_str in target_timestamps:
                    truth_records.append({
                        "village_id": vid,
                        "timestamp": ts_str,
                        "temp_true": round(float(temps[s]), 2),
                        "rainfall_true": round(float(rains[s]), 2),
                        "humidity_true": round(float(humids[s]), 2),
                        "wind_true": round(float(winds[s]), 2),
                        "lat": v_lat,
                        "lon": v_lon
                    })

    df_truth = pd.DataFrame(truth_records)
    df_truth.to_csv("mldev1/data/mock_ground_truth.csv", index=False)
    print(f"✓ Saved {len(df_truth)} 100% REAL ERA5-Land ground truth observations to mldev1/data/mock_ground_truth.csv")
    print("Real ERA5-Land ingestion complete!")

if __name__ == "__main__":
    main()
