'use client';

import React, { useState } from 'react';
import Map3DWrapper from '@/components/Map3DWrapper';
import Sidebar from '@/components/Sidebar';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// Stable constants: Map3D re-creates the whole map when these array/object props
// change identity, so they must not be re-allocated on every Home render.
const INITIAL_CENTER: [number, number] = [76.27, 10.85];
const INITIAL_ZOOM = 7;
const INITIAL_PITCH = 45;
const INITIAL_BEARING = -15;

export default function Home() {
  const [selectedPanchayatId, setSelectedPanchayatId] = useState<string>('');
  const [availableVillages, setAvailableVillages] = useState<any[]>([]);

  const handleSelectPanchayat = (id: string) => {
    setSelectedPanchayatId(id);
  };

  const handleVillagesLoaded = (villages: any[]) => {
    setAvailableVillages(villages);
  };

  return (
    <main className="min-h-screen w-full bg-slate-200 p-1 md:p-2 flex flex-col items-center justify-center">
      <div className="flex flex-col md:flex-row gap-2 md:gap-3 w-full h-[calc(100vh-0.5rem)] md:h-[calc(100vh-1rem)]">
        {/* Left Sidebar with squircle rounding, hover transition, 3-day forecast moving pills, advisory card, & language toggle */}
        <Sidebar
          panchayatId={selectedPanchayatId}
          backendUrl={BACKEND_URL}
          onSelectPanchayat={handleSelectPanchayat}
          availableVillages={availableVillages}
        />

        {/* 3D Map Container with squircle rounding & hover transition */}
        <div className="flex-1 h-full rounded-[4rem] [corner-shape:squircle] overflow-hidden relative bg-slate-950 transition-all duration-300">
          <Map3DWrapper
            initialCenter={INITIAL_CENTER}
            initialZoom={INITIAL_ZOOM}
            initialPitch={INITIAL_PITCH}
            initialBearing={INITIAL_BEARING}
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
