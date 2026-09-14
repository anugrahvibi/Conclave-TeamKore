'use client';

import dynamic from 'next/dynamic';

const Map3D = dynamic(() => import('./Map3D'), {
  ssr: false,
  loading: () => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', width: '100%', background: '#1a1a1a', color: '#fff', fontFamily: 'sans-serif' }}>
      Loading 3D Map Engine...
    </div>
  ),
});

export default function Map3DWrapper(props: any) {
  return <Map3D {...props} />;
}
