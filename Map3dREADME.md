# 3D Crop Map

An interactive 3D crop and terrain visualization for the Mount Diablo area. Terraced mountain crop parcels (with NDVI, soil moisture, and acreage data) are rendered as extruded 3D prisms on top of a real 3D elevation terrain mesh, with nearby villages shown as risk-level markers.

Built with Next.js, React, MapLibre GL JS, and AWS Mapzen Terrarium elevation tiles.

## Features

- **3D terrain** — GPU-displaced elevation mesh with hillshade relief, up to 85° pitch and 8× height exaggeration
- **Crop parcels in 3D** — GeoJSON parcel boundaries extruded as prisms with floating badge pins
- **Village markers** — point markers with risk-level styling and inspection popups
- **Camera controls** — real-time tilt, rotation, and exaggeration sliders, cinematic 360° auto-orbit, and fly-to presets (Mount Diablo, Grand Canyon, Austrian Alps, Mount Rainier)
- **Basemap switcher** — Esri World Imagery (satellite), OpenStreetMap/OpenFreeMap, and Carto Voyager

## Tech Stack

| Layer | Technology |
| --- | --- |
| Framework | [Next.js](https://nextjs.org/) (App Router) + Turbopack |
| UI | [React](https://react.dev/) 19, TypeScript |
| Map engine | [MapLibre GL JS](https://maplibre.org/) via [react-map-gl](https://visgl.github.io/react-map-gl/) |
| Elevation | AWS Mapzen Terrarium tiles |
| Basemaps | Esri World Imagery, OSM / OpenFreeMap, Carto Voyager |

For the full stack reference, see [STACK.md](STACK.md).

## Getting Started

### Prerequisites

- Node.js 18.18 or later

### Installation

```bash
npm install
```

The `postinstall` script copies MapLibre's web worker bundles into `public/`.

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production build

```bash
npm run build
npm start
```

## Project Structure

```
src/
├── app/
│   ├── api/terrain/[...slug]/route.ts   # Elevation tile proxy (adds CORS headers)
│   ├── layout.tsx                       # Root layout
│   └── page.tsx                         # Main page
├── components/
│   ├── Map3D.tsx                        # 3D map component
│   └── Map3DWrapper.tsx                 # Client-side wrapper
└── data/
    └── crops.json                       # Crop parcel GeoJSON (NDVI, moisture, acreage)
```

## Data

The crop dataset (`src/data/crops.json`) is a GeoJSON `FeatureCollection` of terraced mountain parcels along the Mount Diablo slopes. Each feature carries:

- **NDVI** vegetation index
- **Soil moisture**
- **Field acreage**
- **Prism height** used for the 3D extrusion

Village locations live in [`villages.geojson`](villages.geojson) at the repo root.

## Elevation Proxy

Mapzen Terrarium tiles are fetched through the internal route `/api/terrain/{z}/{x}/{y}.png`. The route adds `Access-Control-Allow-Origin: *` headers so WebGL can decode elevation pixels without tainting the canvas, which is what enables the 3D terrain displacement.

## Using as a Reusable Component

The map ships as a drop-in React component: `Map3D` (the map + HUD) and `Map3DWrapper` (same component, pre-wrapped in `next/dynamic` with `ssr: false` so it never renders on the server — use this one in Next.js App Router apps).

### Props

| Prop | Type | Default | Description |
| --- | --- | --- | --- |
| `initialCenter` | `[number, number]` | `[-121.865, 37.855]` | Starting `[lng, lat]` (Mount Diablo terraced parcels) |
| `initialZoom` | `number` | `13.0` | Starting zoom level |
| `initialPitch` | `number` | `50` | Starting tilt, 0–85 |
| `initialBearing` | `number` | `-45` | Starting rotation, -180–180 |
| `className` | `string` | `''` | Class applied to the map container div |
| `villageData` | GeoJSON `FeatureCollection` | `undefined` | Optional village points; renders risk-level circles, badges, and a village list |

### Usage in a Next.js App

Import the wrapper (client-side rendering is handled for you), fill the parent with a sized container, and pass your GeoJSON data:

```tsx
// app/page.tsx
import fs from 'fs';
import path from 'path';
import Map3DWrapper from '@/components/Map3DWrapper';

export default function Home() {
  const villageData = JSON.parse(
    fs.readFileSync(path.join(process.cwd(), 'villages.geojson'), 'utf8')
  );

  return (
    <main style={{ position: 'relative', width: '100vw', height: '100vh' }}>
      <Map3DWrapper
        initialCenter={[-121.865, 37.855]}
        initialZoom={13}
        initialPitch={50}
        initialBearing={-45}
        villageData={villageData}
      />
    </main>
  );
}
```

Or with your own GeoJSON imported directly:

```tsx
import Map3DWrapper from '@/components/Map3DWrapper';
import villageData from '@/data/villages.geojson';

<Map3DWrapper villageData={villageData} initialZoom={11} initialPitch={70} />
```

### Minimal usage (crops only)

All props are optional — omitting `villageData` renders just the crop parcels and their badges:

```tsx
<Map3DWrapper />
```

### What to Copy into Your Project

Copy these files from this repo, keeping the same paths inside `src/`:

| # | File to copy | Destination in your app | Required? |
| --- | --- | --- | --- |
| 1 | `src/components/Map3D.tsx` | `src/components/Map3D.tsx` | ✅ Yes — the map + HUD itself |
| 2 | `src/components/Map3DWrapper.tsx` | `src/components/Map3DWrapper.tsx` | ✅ Yes — SSR-safe `dynamic` wrapper |
| 3 | `src/app/api/terrain/[...slug]/route.ts` | `src/app/api/terrain/[...slug]/route.ts` | ✅ Yes — elevation proxy for 3D terrain |
| 4 | `src/data/crops.json` | `src/data/crops.json` | ✅ Yes (or your own GeoJSON in the same shape) |
| 5 | `villages.geojson` (repo root) | anywhere you like, passed as `villageData` | ⬜ Optional — only for village markers |
| 6 | `src/global.d.ts` | `src/global.d.ts` | ⬜ Optional — needed only if you `import` `.geojson` files directly in TypeScript |

Then make these two changes in the host app:

1. **Copy the `postinstall` script** from this repo's `package.json` — it copies MapLibre's worker bundles (`maplibre-gl-worker*` / `maplibre-gl-shared*`) into `public/`, which `Map3D` loads via `maplibregl.setWorkerUrl`. After copying, run `npm install` once so the workers land in `public/`.
2. **Install the dependencies:**

   ```bash
   npm install maplibre-gl react-map-gl
   ```

   (The component targets React 19; the rest of the app is a standard Next.js App Router + TypeScript setup.)

That's it — the component, its data, and the terrain proxy are self-contained after that. No CSS files need copying: `Map3D.tsx` imports `maplibre-gl/dist/maplibre-gl.css` itself, and all HUD styling is inline.

### Important Notes for Reuse

The component currently depends on a few pieces of app context that must come along with it:

1. **Crop data** — `src/data/crops.json` is imported directly by the component. Copy it (or replace it with your own GeoJSON in the same shape: `properties` with `cropType`, `variety`, `farmer`, `fieldAreaAcres`, `ndvi`, `healthStatus`, `moistureLevel`, `soilType`, `color`, `id`).
2. **Elevation proxy route** — the terrain source points at `/api/terrain/{z}/{x}/{y}.png`. Copy `src/app/api/terrain/[...slug]/route.ts` into your app's `app/api/terrain/[...slug]/route.ts`. Without it, the 3D terrain and hillshade layers fail (the map still renders with basemap + parcels).
3. **MapLibre workers** — the component calls `maplibregl.setWorkerUrl('/maplibre-gl-worker.mjs')`, which relies on the `postinstall` script in `package.json` that copies `maplibre-gl-worker*` / `maplibre-gl-shared*` bundles into `public/`. Keep that script (or the copied files) in the host app.
4. **Dependencies** — install `maplibre-gl` and `react-map-gl` alongside React 19.

The component fills its parent, so wrap it in a container with explicit width/height (e.g. `height: '100vh'`).

### Troubleshooting: 3D Terrain Mesh Not Rendering

If you have copied the component to a new project and the map renders but the **3D terrain mesh is completely flat** (i.e. no mountains or elevation displacement), it is almost always caused by one of two issues:

1. **Missing Web Worker Files in `public/` (Most Common)**
   - **Why it happens:** MapLibre v6 uses a web worker to decode elevation data. If the worker fails to load, the map will stay flat without any error in the console.
   - **Fix:** Ensure you copied the exact `postinstall` script from this repo's `package.json` to your new project's `package.json`:
     ```json
     "scripts": {
       "postinstall": "node -e \"const fs=require('fs'); fs.mkdirSync('public',{recursive:true}); fs.readdirSync('node_modules/maplibre-gl/dist').filter(f=>f.startsWith('maplibre-gl-worker')||f.startsWith('maplibre-gl-shared')).forEach(f=>fs.copyFileSync('node_modules/maplibre-gl/dist/'+f,'public/'+f))\""
     }
     ```
     After adding it, run `npm install` and verify that `maplibre-gl-worker.mjs` (and any related files) exist in your `public/` directory.

2. **Missing or Broken Terrain API Proxy Route**
   - **Why it happens:** The map fetches elevation tiles via `/api/terrain/{z}/{x}/{y}.png`. If this route is missing or fails, no elevation data can be fetched.
   - **Fix:** Verify you copied `src/app/api/terrain/[...slug]/route.ts` precisely and that it works by navigating to `http://localhost:3000/api/terrain/5/8/11.png` in your browser. It should return a valid PNG image.

## License

ISC
