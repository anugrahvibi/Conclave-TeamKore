"""
Data service for ingestion and normalization of block-level weather forecasts.
"""

from typing import Dict, List, Optional
import pandas as pd
from backend.app.config import settings

# 31 Agro-Climatic Block Stations across all 14 Districts of Kerala
KERALA_BLOCK_STATIONS: Dict[str, Dict] = {
    "BLK_TVM_NED": {"name": "Nedumangad", "district": "Thiruvananthapuram", "lat": 8.601, "lon": 76.998},
    "BLK_TVM_CTY": {"name": "Thiruvananthapuram City", "district": "Thiruvananthapuram", "lat": 8.524, "lon": 76.936},
    "BLK_KLM_PUN": {"name": "Punalur", "district": "Kollam", "lat": 9.018, "lon": 76.928},
    "BLK_KLM_KOT": {"name": "Kottarakkara", "district": "Kollam", "lat": 9.001, "lon": 76.772},
    "BLK_PTA_RAN": {"name": "Ranni", "district": "Pathanamthitta", "lat": 9.382, "lon": 76.786},
    "BLK_PTA_ADO": {"name": "Adoor", "district": "Pathanamthitta", "lat": 9.153, "lon": 76.736},
    "BLK_ALP_AMB": {"name": "Ambalapuzha", "district": "Alappuzha", "lat": 9.382, "lon": 76.355},
    "BLK_ALP_CHE": {"name": "Chengannur", "district": "Alappuzha", "lat": 9.317, "lon": 76.612},
    "BLK_KTM_PAL": {"name": "Pala", "district": "Kottayam", "lat": 9.711, "lon": 76.684},
    "BLK_KTM_KAN": {"name": "Kanjirappally", "district": "Kottayam", "lat": 9.558, "lon": 76.786},
    "BLK_IDK_MUN": {"name": "Munnar", "district": "Idukki", "lat": 10.088, "lon": 77.060},
    "BLK_IDK_THO": {"name": "Thodupuzha", "district": "Idukki", "lat": 9.896, "lon": 76.712},
    "BLK_IDK_DEV": {"name": "Devikulam", "district": "Idukki", "lat": 10.063, "lon": 77.104},
    "BLK_EKM_ALU": {"name": "Aluva", "district": "Ernakulam", "lat": 10.108, "lon": 76.357},
    "BLK_EKM_MUV": {"name": "Muvattupuzha", "district": "Ernakulam", "lat": 9.983, "lon": 76.578},
    "BLK_TSR_CHA": {"name": "Chalakudy", "district": "Thrissur", "lat": 10.307, "lon": 76.333},
    "BLK_TSR_WAD": {"name": "Wadakkanchery", "district": "Thrissur", "lat": 10.662, "lon": 76.241},
    "BLK_PLK_CTY": {"name": "Palakkad City", "district": "Palakkad", "lat": 10.786, "lon": 76.654},
    "BLK_PLK_MAN": {"name": "Mannarkkad", "district": "Palakkad", "lat": 10.989, "lon": 76.458},
    "BLK_PLK_ATT": {"name": "Attappady", "district": "Palakkad", "lat": 11.085, "lon": 76.683},
    "BLK_MLP_PER": {"name": "Perinthalmanna", "district": "Malappuram", "lat": 10.976, "lon": 76.225},
    "BLK_MLP_NIL": {"name": "Nilambur", "district": "Malappuram", "lat": 11.277, "lon": 76.226},
    "BLK_KKD_KOD": {"name": "Koduvally", "district": "Kozhikode", "lat": 11.357, "lon": 75.912},
    "BLK_KKD_VAD": {"name": "Vadakara", "district": "Kozhikode", "lat": 11.603, "lon": 75.590},
    "BLK_WYD_KAL": {"name": "Kalpetta", "district": "Wayanad", "lat": 11.608, "lon": 76.083},
    "BLK_WYD_MAN": {"name": "Mananthavady", "district": "Wayanad", "lat": 11.803, "lon": 76.003},
    "BLK_WYD_SUL": {"name": "Sulthan Bathery", "district": "Wayanad", "lat": 11.662, "lon": 76.257},
    "BLK_KNR_TAL": {"name": "Taliparamba", "district": "Kannur", "lat": 12.046, "lon": 75.358},
    "BLK_KNR_IRI": {"name": "Iritty", "district": "Kannur", "lat": 11.982, "lon": 75.667},
    "BLK_KSD_KAN": {"name": "Kanhangad", "district": "Kasargod", "lat": 12.308, "lon": 75.093},
    "BLK_KSD_KAS": {"name": "Kasargod", "district": "Kasargod", "lat": 12.510, "lon": 74.985},
}


class DataService:
    def __init__(self):
        self.df_blocks: Optional[pd.DataFrame] = None
        self._load_data()

    def _load_data(self):
        """Loads initial block forecast dataset (from live service or fallback)."""
        from backend.app.services.live_weather_service import live_weather_service
        try:
            self.df_blocks = live_weather_service.get_forecast_dataframe()
        except Exception:
            if settings.BLOCK_FORECAST_CSV.exists():
                df = pd.read_csv(settings.BLOCK_FORECAST_CSV)
                df["block_name"] = df["block_id"].apply(
                    lambda bid: KERALA_BLOCK_STATIONS.get(bid, {}).get("name", bid)
                )
                df["district"] = df["block_id"].apply(
                    lambda bid: KERALA_BLOCK_STATIONS.get(bid, {}).get("district", "Kerala")
                )
                self.df_blocks = df
            else:
                raise

    def update_forecast_dataframe(self, df: pd.DataFrame):
        """Dynamically updates the active in-memory block forecast dataframe."""
        self.df_blocks = df

    def get_all_blocks(self) -> List[Dict]:
        """Returns metadata for all 31 agro-climatic block stations."""
        result = []
        for bid, info in KERALA_BLOCK_STATIONS.items():
            result.append({
                "block_id": bid,
                "name": info["name"],
                "district": info["district"],
                "lat": info["lat"],
                "lon": info["lon"]
            })
        return result

    def get_block_info(self, block_id: str) -> Optional[Dict]:
        """Returns details for a single block station."""
        if block_id in KERALA_BLOCK_STATIONS:
            info = KERALA_BLOCK_STATIONS[block_id]
            return {
                "block_id": block_id,
                "name": info["name"],
                "district": info["district"],
                "lat": info["lat"],
                "lon": info["lon"]
            }
        return None

    def get_block_forecasts(self, block_id: str) -> List[Dict]:
        """Returns all forecast timestamps for a given block station."""
        if self.df_blocks is None:
            return []
        sub = self.df_blocks[self.df_blocks["block_id"] == block_id]
        if sub.empty:
            return []
        return sub.to_dict("records")

    def get_timestamps(self) -> List[str]:
        """Returns ordered list of forecast timestamps (3-day forecast)."""
        if self.df_blocks is None:
            return []
        return sorted(self.df_blocks["timestamp"].unique().tolist())


data_service = DataService()
