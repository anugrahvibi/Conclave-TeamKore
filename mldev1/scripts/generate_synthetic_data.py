"""
Phase 0: Synthetic Data Generation for Kerala Block Forecasts & Village Centroids
Generates realistic block-level forecasts and village-level ground truth incorporating
topographic and coastal microclimate features of Kerala.
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Fix seed for reproducibility
np.random.seed(42)

# Kerala approximate bounds: Lat 8.3° to 12.8° N, Lon 75.0° to 77.4° E
# Realistic Block Centers across major agro-climatic zones in Kerala
KERALA_BLOCKS = [
    {"block_id": "BLK_TVM_01", "name": "Nedumangad", "lat": 8.601, "lon": 76.998, "base_elev": 110},
    {"block_id": "BLK_TVM_02", "name": "Parassala", "lat": 8.344, "lon": 77.155, "base_elev": 45},
    {"block_id": "BLK_KLM_01", "name": "Kottarakkara", "lat": 9.001, "lon": 76.772, "base_elev": 75},
    {"block_id": "BLK_KLM_02", "name": "Punalur", "lat": 9.018, "lon": 76.928, "base_elev": 140},
    {"block_id": "BLK_ALP_01", "name": "Ambalapuzha", "lat": 9.382, "lon": 76.355, "base_elev": 2},
    {"block_id": "BLK_ALP_02", "name": "Chengannur", "lat": 9.317, "lon": 76.612, "base_elev": 22},
    {"block_id": "BLK_PTA_01", "name": "Ranni", "lat": 9.382, "lon": 76.786, "base_elev": 130},
    {"block_id": "BLK_KTM_01", "name": "Pala", "lat": 9.711, "lon": 76.684, "base_elev": 60},
    {"block_id": "BLK_IDK_01", "name": "Munnar", "lat": 10.088, "lon": 77.060, "base_elev": 1530},
    {"block_id": "BLK_IDK_02", "name": "Thodupuzha", "lat": 9.896, "lon": 76.712, "base_elev": 50},
    {"block_id": "BLK_IDK_03", "name": "Nedumkandam", "lat": 9.837, "lon": 77.147, "base_elev": 920},
    {"block_id": "BLK_EKM_01", "name": "Aluva", "lat": 10.108, "lon": 76.357, "base_elev": 15},
    {"block_id": "BLK_EKM_02", "name": "Muvattupuzha", "lat": 9.983, "lon": 76.578, "base_elev": 35},
    {"block_id": "BLK_TSR_01", "name": "Chalakudy", "lat": 10.307, "lon": 76.333, "base_elev": 30},
    {"block_id": "BLK_TSR_02", "name": "Wadakkanchery", "lat": 10.662, "lon": 76.241, "base_elev": 45},
    {"block_id": "BLK_PLK_01", "name": "Palakkad", "lat": 10.786, "lon": 76.654, "base_elev": 85},
    {"block_id": "BLK_PLK_02", "name": "Mannarkkad", "lat": 10.989, "lon": 76.458, "base_elev": 110},
    {"block_id": "BLK_PLK_03", "name": "Attappady", "lat": 11.085, "lon": 76.683, "base_elev": 750},
    {"block_id": "BLK_MLP_01", "name": "Perinthalmanna", "lat": 10.976, "lon": 76.225, "base_elev": 65},
    {"block_id": "BLK_MLP_02", "name": "Nilambur", "lat": 11.277, "lon": 76.226, "base_elev": 80},
    {"block_id": "BLK_KKD_01", "name": "Koduvally", "lat": 11.357, "lon": 75.912, "base_elev": 55},
    {"block_id": "BLK_KKD_02", "name": "Vadakara", "lat": 11.603, "lon": 75.590, "base_elev": 10},
    {"block_id": "BLK_WYD_01", "name": "Kalpetta", "lat": 11.608, "lon": 76.083, "base_elev": 780},
    {"block_id": "BLK_WYD_02", "name": "Mananthavady", "lat": 11.803, "lon": 76.003, "base_elev": 760},
    {"block_id": "BLK_WYD_03", "name": "Sulthan Bathery", "lat": 11.662, "lon": 76.257, "base_elev": 930},
    {"block_id": "BLK_KNR_01", "name": "Taliparamba", "lat": 12.046, "lon": 75.358, "base_elev": 35},
    {"block_id": "BLK_KNR_02", "name": "Iritty", "lat": 11.982, "lon": 75.667, "base_elev": 105},
    {"block_id": "BLK_KSD_01", "name": "Kanhangad", "lat": 12.308, "lon": 75.093, "base_elev": 18},
    {"block_id": "BLK_KSD_02", "name": "Kasargod", "lat": 12.510, "lon": 74.985, "base_elev": 15}
]

def generate_village_centroids(num_villages_per_block=6):
    """Generates village centroids clustered realistically around block centers."""
    villages = []
    v_idx = 1
    
    for blk in KERALA_BLOCKS:
        # Generate 4-8 villages per block
        n_v = np.random.randint(4, num_villages_per_block + 3)
        for i in range(n_v):
            # Spread villages within ~5-25 km radius (0.05° to 0.22° approx)
            lat_offset = np.random.uniform(-0.15, 0.15)
            lon_offset = np.random.uniform(-0.15, 0.15)
            
            v_lat = round(blk["lat"] + lat_offset, 5)
            v_lon = round(blk["lon"] + lon_offset, 5)
            
            villages.append({
                "village_id": f"VIL_{v_idx:04d}",
                "panchayat_id": f"PANCH_{blk['block_id']}_{i+1:02d}",
                "lat": v_lat,
                "lon": v_lon,
                "parent_block_id": blk["block_id"]
            })
            v_idx += 1
            
    df_villages = pd.DataFrame(villages)
    return df_villages

def generate_forecast_and_ground_truth(df_villages, num_days=5):
    """
    Generates time-series weather data for blocks (block_forecast)
    and corresponding ground truth for villages (mock_ground_truth) with realistic
    microclimate variations.
    """
    start_time = datetime(2026, 9, 15, 0, 0, 0)
    timestamps = [start_time + timedelta(hours=6 * step) for step in range(num_days * 4)]
    
    block_records = []
    
    # 1. Generate Block Weather
    for blk in KERALA_BLOCKS:
        b_elev = blk["base_elev"]
        b_lat = blk["lat"]
        
        # Base temperature influenced by altitude (-6.5°C per 1000m) and latitude
        base_temp = 32.0 - (b_elev / 1000.0) * 6.5 - (b_lat - 8.5) * 0.4
        
        for ts in timestamps:
            hour = ts.hour
            # Diurnal cycle: peak heat at 12:00-14:00, coolest at 06:00
            diurnal = 4.5 * np.sin((hour - 8) * np.pi / 12)
            
            temp = base_temp + diurnal + np.random.normal(0, 0.7)
            
            # Rainfall: higher probability in afternoons/evenings and high elevation (orographic)
            rain_prob = 0.25 + (b_elev / 3000.0)
            if np.random.rand() < rain_prob:
                rainfall = round(max(0.0, np.random.exponential(scale=6.0 + b_elev / 400.0)), 1)
            else:
                rainfall = 0.0
                
            # Humidity: inverse to temperature, elevated with rainfall
            humidity = np.clip(82.0 - diurnal * 3.0 + (10.0 if rainfall > 0 else 0) + np.random.normal(0, 3.0), 45.0, 98.0)
            
            # Wind speed: higher in gaps/coast, calm in dense hills
            wind = np.clip(8.5 + np.random.normal(0, 2.5) + (3.0 if "PLK" in blk["block_id"] else 0), 1.0, 35.0)
            
            block_records.append({
                "block_id": blk["block_id"],
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "temp": round(float(temp), 2),
                "rainfall": round(float(rainfall), 2),
                "humidity": round(float(humidity), 2),
                "wind": round(float(wind), 2),
                "lat": blk["lat"],
                "lon": blk["lon"]
            })
            
    df_block_forecast = pd.DataFrame(block_records)
    
    # 2. Generate Village Ground Truth (Simulating physical downscaling truth)
    # Village ground truth contains local microclimatic bias (elevation gradient, forest cover, coastal breezes)
    village_records = []
    
    # Precompute village elevations & coastal proximity
    village_meta = {}
    for _, v in df_villages.iterrows():
        # High elevation towards East (Western Ghats: lon > 76.5)
        eastness = max(0.0, v["lon"] - 75.2) / 2.0
        elev = np.clip(eastness * 1200.0 + np.random.normal(0, 80), 5.0, 2400.0)
        dist_coast_km = max(5.0, (v["lon"] - 75.0) * 110.0)
        village_meta[v["village_id"]] = {"elevation": elev, "dist_coast": dist_coast_km}
        
    for ts in timestamps:
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        hour = ts.hour
        
        for _, v in df_villages.iterrows():
            vid = v["village_id"]
            meta = village_meta[vid]
            elev = meta["elevation"]
            dist_coast = meta["dist_coast"]
            
            # Find closest block's forecast for this timestamp to derive base state
            blk_rows = df_block_forecast[
                (df_block_forecast["block_id"] == v["parent_block_id"]) & 
                (df_block_forecast["timestamp"] == ts_str)
            ]
            if len(blk_rows) > 0:
                b_fc = blk_rows.iloc[0]
            else:
                b_fc = df_block_forecast[df_block_forecast["timestamp"] == ts_str].iloc[0]
                
            # Physics-based local signal (ground truth microclimate):
            # Lapse rate delta: -6.5C per 1000m difference from block center
            parent_elev = [b["base_elev"] for b in KERALA_BLOCKS if b["block_id"] == v["parent_block_id"]][0]
            delta_elev = elev - parent_elev
            lapse_delta = - (delta_elev / 1000.0) * 6.5
            
            # True local temperature
            temp_true = b_fc["temp"] + lapse_delta + np.random.normal(0, 0.3)
            
            # True local rainfall (orographic enhancement on higher elevations)
            orographic_mult = 1.0 + max(0.0, delta_elev / 800.0)
            if b_fc["rainfall"] > 0:
                rain_true = b_fc["rainfall"] * orographic_mult + np.random.exponential(1.2)
            else:
                # Isolated localized mountain shower
                rain_true = np.random.exponential(2.5) if (elev > 600 and np.random.rand() < 0.15) else 0.0
                
            # True local humidity (marine layer near coast, damp mountain forests)
            marine_effect = max(0.0, (50 - dist_coast) / 10.0)
            humid_true = np.clip(b_fc["humidity"] + marine_effect + (delta_elev / 200.0) + np.random.normal(0, 1.5), 40.0, 99.0)
            
            # True local wind
            wind_true = np.clip(b_fc["wind"] - (elev / 1500.0) * 1.5 + np.random.normal(0, 0.8), 0.5, 40.0)
            
            village_records.append({
                "village_id": vid,
                "timestamp": ts_str,
                "temp_true": round(float(temp_true), 2),
                "rainfall_true": round(float(rain_true), 2),
                "humidity_true": round(float(humid_true), 2),
                "wind_true": round(float(wind_true), 2),
                "lat": v["lat"],
                "lon": v["lon"]
            })
            
    df_ground_truth = pd.DataFrame(village_records)
    return df_block_forecast, df_ground_truth

def main():
    os.makedirs("mldev1/data", exist_ok=True)
    print("Generating village centroids...")
    df_villages = generate_village_centroids(num_villages_per_block=6)
    
    # Save clean village centroids (schema: village_id, panchayat_id, lat, lon)
    df_villages_clean = df_villages[["village_id", "panchayat_id", "lat", "lon"]]
    df_villages_clean.to_csv("mldev1/data/village_centroids.csv", index=False)
    print(f"Saved {len(df_villages_clean)} villages to mldev1/data/village_centroids.csv")
    
    print("Generating block forecasts and synthetic ground truth...")
    df_blocks, df_truth = generate_forecast_and_ground_truth(df_villages, num_days=5)
    
    df_blocks.to_csv("mldev1/data/block_forecast.csv", index=False)
    print(f"Saved {len(df_blocks)} block forecast records to mldev1/data/block_forecast.csv")
    
    df_truth.to_csv("mldev1/data/mock_ground_truth.csv", index=False)
    print(f"Saved {len(df_truth)} ground truth records to mldev1/data/mock_ground_truth.csv")
    
    print("Phase 0 data generation complete!")

if __name__ == "__main__":
    main()
