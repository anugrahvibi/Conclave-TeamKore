import Map3DWrapper from "@/components/Map3DWrapper";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function fetchVillages() {
  try {
    const res = await fetch(`${BACKEND_URL}/villages?format=json&limit=300`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    const data = await res.json();

    // Transform flat village list → GeoJSON FeatureCollection of Points
    const features = (data.villages || []).map((v: any) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [v.lon, v.lat],
      },
      properties: {
        village_id: v.village_id,
        panchayat_id: v.panchayat_id,
        panchayat_name: v.name,
        name_ml: v.name_ml || "",
        district: v.district,
        block_id: v.nearest_block_id,
        block_name: v.nearest_block_name,
        elevation_m: v.static_features?.elevation_m ?? 100,
        land_cover: v.static_features?.land_cover ?? "agriculture",
        // risk_level will be lazily fetched on click; default to 'low'
        current_risk_level: "low",
      },
    }));

    return { type: "FeatureCollection", features };
  } catch {
    return null;
  }
}

export default async function Home() {
  const villageData = await fetchVillages();

  return (
    <main className="min-h-screen w-full bg-white p-1 md:p-2 flex flex-col items-center justify-center">
      <div className="w-full h-[calc(100vh-0.5rem)] md:h-[calc(100vh-1rem)] rounded-[4rem] [corner-shape:squircle] overflow-hidden border border-gray-200 shadow-xl relative bg-slate-950">
        <Map3DWrapper
          initialCenter={[76.27, 10.85]}
          initialZoom={7}
          initialPitch={45}
          initialBearing={-15}
          villageData={villageData}
          backendUrl={BACKEND_URL}
        />
      </div>
    </main>
  );
}
