#!/usr/bin/env python3
"""
ISRIC SoilGrids v2.0 Batch Data Fetcher for Kerala Villages.

Standalone batch job to fetch topsoil properties (0-5cm) from ISRIC SoilGrids v2.0 REST API:
- phh2o (pH x 10 -> converted to pH)
- clay (g/kg -> converted to %)
- sand (g/kg -> converted to %)
- soc (dg/kg -> converted to g/kg organic carbon)

CRITICAL:
- Respects fair-use rate limit of 5 requests/minute (12.0s delay between calls).
- Zero live calls from any API endpoints.
- Supports incremental resume from data/village_soil_data.csv so interrupted runs
  can be resumed safely without redundant API queries.
"""

import argparse
import csv
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import urllib.parse
import urllib.request

# Ensure IPv4 resolution to prevent IPv6 routing stalls with rest.isric.org
orig_getaddrinfo = socket.getaddrinfo

def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _getaddrinfo_ipv4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("fetch_soil_data")

BASE_DIR = Path(__file__).resolve().parent
SOILGRIDS_ENDPOINT = "https://rest.isric.org/soilgrids/v2.0/properties/query"
DEFAULT_OUTPUT_CSV = BASE_DIR / "data" / "village_soil_data.csv"
PROPERTIES = ["phh2o", "clay", "sand", "soc"]
CSV_COLUMNS = ["village_id", "ph", "clay_pct", "sand_pct", "organic_carbon"]


def load_village_centroids() -> List[Dict[str, Any]]:
    """
    Loads all 1,031 village centroids from spatial_service or direct CSVs.
    Returns list of dicts with keys: village_id, lat, lon.
    """
    # Attempt 1: From spatial_service if available
    try:
        sys.path.insert(0, str(BASE_DIR))
        from backend.app.services.spatial_service import spatial_service
        villages = []
        for vid, vdata in spatial_service.villages.items():
            villages.append({
                "village_id": vid,
                "lat": float(vdata["lat"]),
                "lon": float(vdata["lon"]),
                "name": vdata.get("name", "")
            })
        if villages:
            logger.info(f"Loaded {len(villages)} villages via spatial_service.")
            return villages
    except Exception as e:
        logger.debug(f"Could not load via spatial_service ({e}); falling back to CSV.")

    # Attempt 2: Direct CSV loading
    csv_candidates = [
        BASE_DIR / "mldev1" / "data" / "village_metadata_kerala.csv",
        BASE_DIR / "mldev1" / "data" / "village_centroids.csv",
        BASE_DIR / "data" / "village_metadata_kerala.csv",
    ]
    for p in csv_candidates:
        if p.exists():
            villages = []
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    vid = row.get("village_id")
                    lat = row.get("lat")
                    lon = row.get("lon")
                    if vid and lat and lon:
                        villages.append({
                            "village_id": vid,
                            "lat": float(lat),
                            "lon": float(lon),
                            "name": row.get("name", "")
                        })
            if villages:
                logger.info(f"Loaded {len(villages)} villages from {p}.")
                return villages

    raise FileNotFoundError("Could not find village centroids data in spatial_service or mldev1/data.")


def load_existing_completed_villages(csv_path: Path) -> Set[str]:
    """Returns set of village_ids already completed in the output CSV."""
    if not csv_path.exists():
        return set()
    completed = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = row.get("village_id")
            if vid:
                completed.add(vid.strip())
    return completed


_last_request_time: float = 0.0


def _rate_limited_wait(delay_seconds: float = 12.0):
    """Ensures at least delay_seconds has elapsed since the last SoilGrids API request."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < delay_seconds:
        sleep_dur = delay_seconds - elapsed
        time.sleep(sleep_dur)
    _last_request_time = time.time()


def query_soilgrids_api(lat: float, lon: float, timeout: float = 30.0, delay_seconds: float = 12.0) -> Dict[str, Any]:
    """
    Queries SoilGrids v2.0 REST API for 0-5cm depth mean properties.
    Uses curl with timeout to ensure IPv4 resolution and robust HTTP handling.
    Enforces minimum delay since last request to prevent 503 rate-limiting.
    """
    _rate_limited_wait(delay_seconds)

    params = [
        ("lon", f"{lon:.5f}"),
        ("lat", f"{lat:.5f}"),
        ("property", "phh2o"),
        ("property", "clay"),
        ("sand", "sand"),
        ("property", "sand"),
        ("property", "soc"),
        ("depth", "0-5cm"),
        ("value", "mean"),
    ]
    # Ensure correct property params
    params = [
        ("lon", f"{lon:.5f}"),
        ("lat", f"{lat:.5f}"),
        ("property", "phh2o"),
        ("property", "clay"),
        ("property", "sand"),
        ("property", "soc"),
        ("depth", "0-5cm"),
        ("value", "mean"),
    ]
    query_string = urllib.parse.urlencode(params)
    url = f"{SOILGRIDS_ENDPOINT}?{query_string}"

    cmd = [
        "curl", "-4", "-s", "-S",
        "--max-time", str(int(timeout)),
        "-H", "User-Agent: AgroAdvisoryKerala/1.0 (academic research; rate-limited)",
        "-H", "Accept: application/json",
        url
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"curl error (code {res.returncode}): {res.stderr.strip()}")

    stdout_clean = res.stdout.strip()
    if not stdout_clean:
        raise RuntimeError("Empty response received from SoilGrids API")
    if stdout_clean.startswith("<") or "503 Service" in stdout_clean or "429 Too Many" in stdout_clean:
        raise RuntimeError(f"SoilGrids rate-limited or error response: {stdout_clean[:100]}")

    try:
        data = json.loads(stdout_clean)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Invalid JSON from SoilGrids: {err}")

    return data


def parse_soilgrids_response(data: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Parses and converts integer-scaled SoilGrids v2.0 values to conventional units:
    - phh2o: returned as pH * 10 -> divide by 10
    - clay: returned as g/kg -> divide by 10 for percentage (%)
    - sand: returned as g/kg -> divide by 10 for percentage (%)
    - soc: returned as dg/kg -> divide by 10 for g/kg
    """
    raw_vals: Dict[str, float] = {}

    layers = data.get("properties", {}).get("layers", [])
    for layer in layers:
        prop_name = layer.get("name")
        depths = layer.get("depths", [])
        for d in depths:
            label = d.get("label", "")
            rng = d.get("range", {})
            if label == "0-5cm" or (rng.get("top_depth") == 0 and rng.get("bottom_depth") == 5):
                vals = d.get("values")
                if vals and isinstance(vals, dict):
                    mean_val = vals.get("mean")
                    if mean_val is not None:
                        raw_vals[prop_name] = float(mean_val)
                break

    ph = round(raw_vals["phh2o"] / 10.0, 2) if "phh2o" in raw_vals else None
    clay_pct = round(raw_vals["clay"] / 10.0, 2) if "clay" in raw_vals else None
    sand_pct = round(raw_vals["sand"] / 10.0, 2) if "sand" in raw_vals else None
    organic_carbon = round(raw_vals["soc"] / 10.0, 2) if "soc" in raw_vals else None

    return ph, clay_pct, sand_pct, organic_carbon


def fetch_village_soil_with_retry(
    village: Dict[str, Any],
    timeout: float = 30.0,
    delay_seconds: float = 12.0
) -> Optional[Dict[str, Any]]:
    """
    Attempts to fetch and parse SoilGrids data for a village.
    Retries once after delay_seconds upon timeout or HTTP failure.
    If fetch fails or values cannot be obtained, logs and returns None.
    """
    global _last_request_time
    vid = village["village_id"]
    lat, lon = village["lat"], village["lon"]

    for attempt in (1, 2):
        try:
            raw_data = query_soilgrids_api(lat, lon, timeout=timeout, delay_seconds=delay_seconds)
            ph, clay, sand, soc = parse_soilgrids_response(raw_data)
            if ph is None and clay is None and sand is None:
                raise RuntimeError("No property layer values returned (offshore or unmapped point)")
            return {
                "village_id": vid,
                "ph": ph if ph is not None else "",
                "clay_pct": clay if clay is not None else "",
                "sand_pct": sand if sand is not None else "",
                "organic_carbon": soc if soc is not None else ""
            }
        except Exception as e:
            _last_request_time = time.time()
            if attempt == 1:
                logger.warning(f"[{vid}] Attempt 1 failed ({e}). Waiting {delay_seconds}s before retry...")
                time.sleep(delay_seconds)
            else:
                logger.error(f"[{vid}] Attempt 2 failed ({e}). Skipping village.")
                return None


def run_batch_fetch(
    output_path: Path = DEFAULT_OUTPUT_CSV,
    limit: Optional[int] = None,
    delay_seconds: float = 12.0,
    retry_delay: float = 5.0,
    timeout: float = 20.0
):
    """
    Executes the batch fetch over all village centroids.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    villages = load_village_centroids()
    total_villages = len(villages)
    logger.info(f"Loaded {total_villages} total village centroids.")

    completed_ids = load_existing_completed_villages(output_path)
    if completed_ids:
        logger.info(f"Found {len(completed_ids)} already fetched villages in {output_path}. Resuming...")

    pending_villages = [v for v in villages if v["village_id"] not in completed_ids]
    if limit is not None and limit > 0:
        pending_villages = pending_villages[:limit]
        logger.info(f"Limiting execution to {len(pending_villages)} villages.")

    if not pending_villages:
        logger.info("All requested villages have already been fetched! Nothing to do.")
        print(f"\nSummary: All {len(completed_ids)}/{total_villages} villages present in {output_path}.")
        return

    # Prepare output file and CSV writer
    file_exists = output_path.exists() and output_path.stat().st_size > 0
    f = open(output_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
    if not file_exists:
        writer.writeheader()
        f.flush()

    successful_count = 0
    failed_count = 0
    total_to_fetch = len(pending_villages)

    logger.info(f"Starting batch fetch for {total_to_fetch} villages (Rate limit delay: {delay_seconds:.1f}s/req)...")

    try:
        for idx, village in enumerate(pending_villages, start=1):
            vid = village["village_id"]
            lat, lon = village["lat"], village["lon"]

            logger.info(f"[{idx}/{total_to_fetch}] Fetching {vid} ({lat:.4f}, {lon:.4f})...")
            result = fetch_village_soil_with_retry(village, timeout=timeout, delay_seconds=delay_seconds)

            if result is not None:
                writer.writerow(result)
                f.flush()
                successful_count += 1
                logger.info(
                    f"[{idx}/{total_to_fetch}] OK {vid} -> pH={result['ph']}, "
                    f"clay={result['clay_pct']}%, sand={result['sand_pct']}%, "
                    f"soc={result['organic_carbon']} g/kg"
                )
            else:
                failed_count += 1

            # Respect rate limit of 5 requests/min (12.0s delay between calls)
            if idx < total_to_fetch:
                elapsed = time.time() - start_t
                sleep_time = max(0.0, delay_seconds - elapsed)
                time.sleep(sleep_time)

    finally:
        f.close()

    # Final Summary
    logger.info("Batch fetch run completed.")
    print("\n" + "=" * 50)
    print("ISRIC SoilGrids Batch Fetch Summary")
    print("=" * 50)
    print(f"Total villages in dataset:      {total_villages}")
    print(f"Previously cached villages:     {len(completed_ids)}")
    print(f"Villages fetched in this run:   {successful_count}")
    print(f"Villages failed in this run:    {failed_count}")
    total_now = len(load_existing_completed_villages(output_path))
    print(f"Total villages now in CSV:      {total_now} / {total_villages}")
    print(f"Output file:                    {output_path}")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="One-time batch fetcher for Kerala village soil data from ISRIC SoilGrids v2.0."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT_CSV})"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=12.0,
        help="Delay in seconds between requests to respect 5 req/min rate limit (default: 12.0s)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of villages to fetch (for testing/dry-runs)"
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=5.0,
        help="Delay before retry on failure in seconds (default: 5.0s)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30.0s)"
    )

    args = parser.parse_args()
    run_batch_fetch(
        output_path=args.output,
        limit=args.limit,
        delay_seconds=args.delay,
        retry_delay=args.retry_delay,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()
