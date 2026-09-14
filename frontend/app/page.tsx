import Map3DWrapper from "@/components/Map3DWrapper";

export default function Home() {
  return (
    <main className="min-h-screen w-full bg-white p-3 sm:p-4 md:p-6 flex flex-col items-center justify-center">
      <div className="w-full h-[calc(100vh-2rem)] sm:h-[calc(100vh-3rem)] rounded-2xl overflow-hidden border border-gray-200 shadow-xl relative bg-slate-950">
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
