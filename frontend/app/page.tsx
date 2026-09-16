'use client';

import React, { useState } from 'react';
import Map3DWrapper from '@/components/Map3DWrapper';
import Sidebar from '@/components/Sidebar';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function Home() {
  const [selectedPanchayatId, setSelectedPanchayatId] = useState<string>('KL_PANCH_0001');
  const [availableVillages, setAvailableVillages] = useState<any[]>([]);

  const handleSelectPanchayat = (id: string) => {
    setSelectedPanchayatId(id);
  };

  const handleVillagesLoaded = (villages: any[]) => {
    setAvailableVillages(villages);
  };

  return (
    <main className="min-h-screen w-full bg-white p-1 md:p-2 flex flex-col items-center justify-center">
      <div className="flex flex-col md:flex-row gap-2 md:gap-3 w-full h-[calc(100vh-0.5rem)] md:h-[calc(100vh-1rem)]">
        {/* Left Sidebar with squircle rounding, hover transition, 3-day forecast moving pills, advisory card, & language toggle */}
        <Sidebar
          panchayatId={selectedPanchayatId}
          backendUrl={BACKEND_URL}
          onSelectPanchayat={handleSelectPanchayat}
          availableVillages={availableVillages}
        />

        {/* 3D Map Container with squircle rounding & hover transition */}
        <div className="flex-1 h-full rounded-[4rem] [corner-shape:squircle] overflow-hidden border border-gray-200 relative bg-slate-950 transition-all duration-300 hover:border-gray-300">
          <Map3DWrapper
            initialCenter={[76.27, 10.85]}
            initialZoom={7}
            initialPitch={45}
            initialBearing={-15}
            backendUrl={BACKEND_URL}
            selectedPanchayatId={selectedPanchayatId}
            onSelectPanchayat={handleSelectPanchayat}
            onVillagesLoaded={handleVillagesLoaded}
          />
        </div>
      </div>
    </main>
  );
}
