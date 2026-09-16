'use client';

import dynamic from 'next/dynamic';

import { Globe } from '@phosphor-icons/react';

const Map3D = dynamic(() => import('./Map3D'), {
  ssr: false,
  loading: () => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', width: '100vw', background: '#ffffff', color: '#0f172a', fontFamily: 'var(--font-sans, Poppins, sans-serif)' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 24, marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <Globe size={28} color="#0284c7" />
          <span>3D Terrain & Agro Engine</span>
        </div>
        <div style={{ fontSize: 13, color: '#64748b' }}>Loading MapLibre WebGL & Elevation Meshes...</div>
      </div>
    </div>
  ),
});

export default function Map3DWrapper(props: any) {
  return <Map3D {...props} />;
}




