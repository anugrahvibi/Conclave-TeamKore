"""
Spatial Service for managing village boundaries, centroids, and nearest-station lookups.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from backend.app.config import settings
from backend.app.services.data_service import KERALA_BLOCK_STATIONS, data_service

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great circle distance in kilometers."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = np.sin(delta_phi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0) ** 2
    return float(R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a)))


class SpatialService:
    def __init__(self):
        self.villages: Dict[str, Dict[str, Any]] = {}
        self.village_by_panchayat: Dict[str, str] = {}
        self.village_by_name: Dict[str, str] = {}
        self.geometries: Dict[str, Any] = {}
        self.block_tree: Optional[cKDTree] = None
        self.block_ids_ordered: List[str] = []
        self._initialize()

    def _initialize(self):
        """Loads and cross-indexes villages, static features, and GeoJSON boundaries."""
        # 1. Load geometries from GeoJSON
        if settings.KERALA_GEOJSON.exists():
            with open(settings.KERALA_GEOJSON, "r", encoding="utf-8") as f:
                geo_data = json.load(f)
            for feat in geo_data.get("features", []):
                osm_id = feat.get("properties", {}).get("@id")
                if osm_id:
                    self.geometries[osm_id] = feat.get("geometry")

        # 2. Build KDTree for nearest block lookup
        block_coords = []
        self.block_ids_ordered = []
        for bid, binfo in KERALA_BLOCK_STATIONS.items():
            self.block_ids_ordered.append(bid)
            block_coords.append([binfo["lat"], binfo["lon"]])
        self.block_tree = cKDTree(np.array(block_coords))

        # 3. Load metadata and static features
        if not settings.VILLAGE_METADATA_CSV.exists() or not settings.VILLAGE_STATIC_FEATURES_CSV.exists():
            raise FileNotFoundError("Village metadata or static features CSV is missing.")

        df_meta = pd.read_csv(settings.VILLAGE_METADATA_CSV)
        df_static = pd.read_csv(settings.VILLAGE_STATIC_FEATURES_CSV)
        merged = pd.merge(df_meta, df_static, on="village_id", how="left")

        # Load village_soil_data.csv at startup if present (cached batch data)
        soil_csv_path = getattr(settings, "VILLAGE_SOIL_DATA_CSV", None)
        if not (soil_csv_path and Path(soil_csv_path).exists()):
            for alt in [
                settings.PROJECT_ROOT / "data" / "village_soil_data.csv",
                settings.MLDEV1_DATA_DIR / "village_soil_data.csv",
                Path.cwd() / "data" / "village_soil_data.csv"
            ]:
                if alt.exists():
                    soil_csv_path = alt
                    break

        if soil_csv_path and Path(soil_csv_path).exists():
            try:
                df_soil = pd.read_csv(soil_csv_path)
                if not df_soil.empty and "village_id" in df_soil.columns:
                    merged = pd.merge(merged, df_soil, on="village_id", how="left")
                    logger.info(f"Loaded soil data from {soil_csv_path} for {len(df_soil)} villages.")
            except Exception as e:
                logger.warning(f"Could not load soil data from {soil_csv_path} ({e}); proceeding without soil.")
        else:
            logger.warning("village_soil_data.csv not found at startup; proceeding without soil data.")

        for _, row in merged.iterrows():
            vid = str(row["village_id"])
            pid = str(row["panchayat_id"])
            name = str(row["name"])
            name_ml = str(row.get("name_ml", "")) if pd.notna(row.get("name_ml")) else None
            lat = float(row["lat"])
            lon = float(row["lon"])
            osm_id = str(row.get("osm_id", ""))
            
            # Find nearest block
            nearest_bid = self._find_nearest_block_id(lat, lon)
            nearest_block = KERALA_BLOCK_STATIONS.get(nearest_bid, {})

            elevation = float(row.get("elevation", 100.0))
            dist_to_water = float(row.get("dist_to_water", 5000.0))
            land_cover = str(row.get("land_cover", "mixed_agroforestry"))

            # Boundary polygon if available
            geom = self.geometries.get(osm_id)

            static_features: Dict[str, Any] = {
                "elevation_m": elevation,
                "dist_to_water_km": round(dist_to_water / 1000.0, 2),
                "land_cover": land_cover
            }

            # Attach soil features if available
            ph_val = row.get("ph")
            clay_val = row.get("clay_pct")
            sand_val = row.get("sand_pct")
            oc_val = row.get("organic_carbon")
            if pd.notna(ph_val) and pd.notna(clay_val) and pd.notna(sand_val):
                try:
                    static_features["ph"] = float(ph_val)
                    static_features["soil_ph"] = float(ph_val)
                    static_features["clay_pct"] = float(clay_val)
                    static_features["sand_pct"] = float(sand_val)
                    if pd.notna(oc_val) and str(oc_val).strip() != "":
                        static_features["organic_carbon"] = float(oc_val)
                except (ValueError, TypeError):
                    pass

            village_record = {
                "village_id": vid,
                "panchayat_id": pid,
                "name": name,
                "name_ml": name_ml,
                "district": nearest_block.get("district", "Kerala"),
                "lat": lat,
                "lon": lon,
                "osm_id": osm_id,
                "nearest_block_id": nearest_bid,
                "nearest_block_name": nearest_block.get("name", nearest_bid),
                "nearest_block_dist_km": round(haversine_km(lat, lon, nearest_block["lat"], nearest_block["lon"]), 2),
                "static_features": static_features,
                "geometry": geom
            }

            self.villages[vid] = village_record
            self.village_by_panchayat[pid.upper()] = vid
            self.village_by_name[name.lower()] = vid

    def _find_nearest_block_id(self, lat: float, lon: float) -> str:
        """Finds nearest block station ID using KDTree."""
        if self.block_tree is None:
            return "BLK_TVM_NED"
        _, idx = self.block_tree.query([lat, lon], k=1)
        return self.block_ids_ordered[idx]

    def get_village(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Lookup a village by village_id (e.g. VIL_0001), panchayat_id (e.g. KL_PANCH_0001),
        or name (e.g. Vorkady).
        """
        clean_id = identifier.strip()
        # By village_id
        if clean_id in self.villages:
            return self.villages[clean_id]
        
        # By panchayat_id
        if clean_id.upper() in self.village_by_panchayat:
            vid = self.village_by_panchayat[clean_id.upper()]
            return self.villages[vid]
        
        # By name
        if clean_id.lower() in self.village_by_name:
            vid = self.village_by_name[clean_id.lower()]
            return self.villages[vid]
        
        return None

    def get_villages(
        self,
        district: Optional[str] = None,
        block_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Returns filtered list of villages."""
        results = list(self.villages.values())

        if district:
            d_clean = district.strip().lower()
            results = [v for v in results if v.get("district", "").lower() == d_clean]

        if block_id:
            b_clean = block_id.strip()
            results = [v for v in results if v.get("nearest_block_id") == b_clean]

        if search:
            s_clean = search.strip().lower()
            results = [
                v for v in results
                if s_clean in v["name"].lower()
                or s_clean in v["panchayat_id"].lower()
                or s_clean in v["village_id"].lower()
            ]

        if offset > 0:
            results = results[offset:]
        if limit is not None and limit > 0:
            results = results[:limit]

        return results

    def get_villages_geojson(
        self,
        district: Optional[str] = None,
        block_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Returns GeoJSON FeatureCollection with polygon boundaries and properties."""
        villages = self.get_villages(district=district, block_id=block_id, search=search, limit=limit, offset=offset)
        features = []
        for v in villages:
            features.append({
                "type": "Feature",
                "id": v["village_id"],
                "properties": {
                    "village_id": v["village_id"],
                    "panchayat_id": v["panchayat_id"],
                    "name": v["name"],
                    "name_ml": v["name_ml"],
                    "district": v["district"],
                    "nearest_block_id": v["nearest_block_id"],
                    "nearest_block_name": v["nearest_block_name"],
                    "centroid": {"lat": v["lat"], "lon": v["lon"]},
                    "elevation_m": v["static_features"]["elevation_m"],
                    "dist_to_water_km": v["static_features"]["dist_to_water_km"],
                    "land_cover": v["static_features"]["land_cover"]
                },
                "geometry": v.get("geometry")
            })

        return {
            "type": "FeatureCollection",
            "total_features": len(features),
            "features": features
        }

    def get_villages_for_block(self, block_id: str) -> List[Dict[str, Any]]:
        """Returns all villages associated with a given block station."""
        return [v for v in self.villages.values() if v.get("nearest_block_id") == block_id]

    @property
    def total_villages(self) -> int:
        return len(self.villages)


spatial_service = SpatialService()
