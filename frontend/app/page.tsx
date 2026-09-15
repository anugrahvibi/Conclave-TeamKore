import Map3DWrapper from "@/components/Map3DWrapper";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function Home() {
  return (
    <main className="min-h-screen w-full bg-white p-1 md:p-2 flex flex-col items-center justify-center">
      <div className="w-full h-[calc(100vh-0.5rem)] md:h-[calc(100vh-1rem)] rounded-[4rem] [corner-shape:squircle] overflow-hidden border border-gray-200 relative bg-slate-950">
        <Map3DWrapper
          initialCenter={[76.27, 10.85]}
          initialZoom={7}
          initialPitch={45}
          initialBearing={-15}
          backendUrl={BACKEND_URL}
        />
      </div>
    </main>
  );
}

