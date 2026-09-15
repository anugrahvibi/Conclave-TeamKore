'use client';

import dynamic from 'next/dynamic';

const Map3D = dynamic(() => import('./Map3D'), {
  ssr: false,
  loading: () => (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      width: '100%',
      background: 'linear-gradient(135deg, #020617 0%, #0f172a 100%)',
      color: '#fff',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <style>{`
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
      `}</style>
      <div style={{
        width: 48,
        height: 48,
        border: '3px solid rgba(56, 189, 248, 0.2)',
        borderTop: '3px solid #38bdf8',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
        marginBottom: 16
      }} />
      <div style={{ fontSize: 16, fontWeight: 600, color: '#f8fafc', letterSpacing: '0.025em' }}>
        Initializing 3D Terrain Engine
      </div>
      <div style={{ fontSize: 12, color: '#64748b', marginTop: 6 }}>
        Loading elevation tiles & WebGL shaders...
      </div>
    </div>
  ),
});

export default function Map3DWrapper(props: any) {
  return <Map3D {...props} />;
}

