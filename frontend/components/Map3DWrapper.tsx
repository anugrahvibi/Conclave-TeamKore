'use client';

import dynamic from 'next/dynamic';

const Map3D = dynamic(() => import('./Map3D'), {
  ssr: false,
});

export default function Map3DWrapper(props: any) {
  return <Map3D {...props} />;
}



