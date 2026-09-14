import Map3DWrapper from "@/components/Map3DWrapper";

export default function Home() {
  return (
    <main className="min-h-screen w-full bg-white p-1 md:p-2 flex flex-col items-center justify-center">
      <div className="w-full h-[calc(100vh-0.5rem)] md:h-[calc(100vh-1rem)] rounded-[4rem] [corner-shape:squircle] overflow-hidden border border-gray-200 shadow-xl relative bg-slate-950">
        <Map3DWrapper 
          initialCenter={[-121.865, 37.855]}
          initialZoom={13}
          initialPitch={50}
          initialBearing={-45}
        />
      </div>
    </main>
  );
}
