'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import cropData from '../data/crops.json';

interface Map3DProps {
  initialCenter?: [number, number];
  initialZoom?: number;
  initialPitch?: number;
  initialBearing?: number;
  className?: string;
  villageData?: any;
}

const BASEMAP_TILES = {
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  osm: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  carto: 'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
};

// 3D Mountain Showcase Locations
const LOCATIONS = [
  {
    name: '🌾 Diablo Terraced Crops',
    center: [-121.865, 37.855] as [number, number],
    zoom: 13.0,
    pitch: 50,
    bearing: -45,
    desc: 'High-elevation mountain terraced crop parcels climbing up Mount Diablo',
  },
  {
    name: '🏔️ Mount Diablo Summit',
    center: [-121.914, 37.881] as [number, number],
    zoom: 12.8,
    pitch: 78,
    bearing: -55,
    desc: '3,849 ft peak directly overlooking the California valley',
  },
  {
    name: '🏜️ Grand Canyon',
    center: [-112.14, 36.06] as [number, number],
    zoom: 12.2,
    pitch: 80,
    bearing: 45,
    desc: 'Massive 1,500m deep vertical canyon walls & ridges',
  },
  {
    name: '🏔️ Austrian Alps (Innsbruck)',
    center: [11.39, 47.26] as [number, number],
    zoom: 12.0,
    pitch: 82,
    bearing: 60,
    desc: 'Towering 3,000m European alpine summits',
  },
  {
    name: '🌋 Mount Rainier',
    center: [-121.76, 46.85] as [number, number],
    zoom: 11.5,
    pitch: 80,
    bearing: -20,
    desc: '14,411 ft massive volcanic peak with glaciers and steep valleys',
  },
];

export default function Map3D({
  initialCenter = [-121.865, 37.855], // Mount Diablo terraced crop parcels
  initialZoom = 13.0,
  initialPitch = 50,
  initialBearing = -45,
  className = '',
  villageData,
}: Map3DProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [selectedCrop, setSelectedCrop] = useState<any>(null);
  const [currentBasemap, setCurrentBasemap] = useState<'osm' | 'satellite' | 'carto'>('satellite');
  const [terrainProvider, setTerrainProvider] = useState<'terrarium' | 'maplibre'>('terrarium');

  // Camera & Telemetry state
  const [pitch, setPitch] = useState<number>(initialPitch);
  const [bearing, setBearing] = useState<number>(initialBearing);
  const [isOrbiting, setIsOrbiting] = useState<boolean>(false);
  const [currentElevation, setCurrentElevation] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState<boolean>(false);
  const orbitFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    if (typeof window !== 'undefined') {
      maplibregl.setWorkerUrl(`${origin}/maplibre-gl-worker.mjs`);
    }

    // 1. Initialize Map with Built-in 3D Terrain & Hillshade Relief
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'basemap-source': {
            type: 'raster',
            tiles: [BASEMAP_TILES[currentBasemap]],
            tileSize: 256,
            attribution: '© OpenStreetMap / Esri / OpenFreeMap contributors',
          },
          'terrain-dem-terrarium': {
            type: 'raster-dem',
            tiles: [`${origin}/api/terrain/{z}/{x}/{y}.png`],
            encoding: 'terrarium',
            tileSize: 256,
            maxzoom: 15,
          },
          'hillshade-dem-terrarium': {
            type: 'raster-dem',
            tiles: [`${origin}/api/terrain/{z}/{x}/{y}.png`],
            encoding: 'terrarium',
            tileSize: 256,
            maxzoom: 15,
          },
          'terrain-dem-maplibre': {
            type: 'raster-dem',
            tiles: ['https://demotiles.maplibre.org/terrain-tiles/{z}/{x}/{y}.png'],
            encoding: 'mapbox',
            tileSize: 256,
            maxzoom: 14,
          },
        },
        layers: [
          {
            id: 'basemap-layer',
            type: 'raster',
            source: 'basemap-source',
            minzoom: 0,
            maxzoom: 20,
          },
          {
            id: 'hillshade-layer',
            type: 'hillshade',
            source: 'hillshade-dem-terrarium',
            paint: {
              'hillshade-exaggeration': 0.95,
              'hillshade-shadow-color': '#020617',
              'hillshade-highlight-color': '#ffffff',
              'hillshade-illumination-direction': 315,
            },
          },
        ],
        terrain: {
          source: 'terrain-dem-terrarium',
          exaggeration: 1,
        },
        projection: {
          type: 'globe',
        },
        sky: {
          'sky-color': '#0284c7',
          'sky-horizon-blend': 0.8,
          'horizon-color': '#e0f2fe',
          'horizon-fog-blend': 1.0,
          'fog-color': '#ffffff',
          'fog-ground-blend': 1.0,
          'atmosphere-blend': 0.85,
        },
      },
      center: initialCenter,
      zoom: initialZoom,
      pitch: initialPitch,
      bearing: initialBearing,
      maxPitch: 85,
      minPitch: 0,
      minZoom: 0,
      dragRotate: true,
      touchPitch: true,
    });

    mapRef.current = map;
    (window as any).__map = map;
    console.log('[Map3D] Map initialized');

    // Error listener to catch any tile or WebGL issues
    map.on('error', (e) => {
      if (e && e.error) {
        console.warn('MapLibre engine notice:', e.error.message || e.error);
      }
    });

    // Track camera angle updates and live terrain elevation
    const updateTelemetry = () => {
      setBearing(Math.round(map.getBearing()));
      setPitch(Math.round(map.getPitch()));
      try {
        const center = map.getCenter();
        const ele = map.queryTerrainElevation(center);
        if (ele !== null && !isNaN(ele)) {
          setCurrentElevation(Math.round(ele));
        }
      } catch (err) {
        // terrain query not ready
      }
    };

    map.on('rotate', updateTelemetry);
    map.on('pitch', updateTelemetry);
    map.on('move', updateTelemetry);
    map.on('render', updateTelemetry);

    map.on('load', () => {
      map.resize();
      setIsLoaded(true);

      // --- 3. ADD 3D CROP PARCELS DATA SOURCE ---
      if (!map.getSource('crops-source')) {
        map.addSource('crops-source', {
          type: 'geojson',
          data: cropData as any,
        });

        // 1. 2D Solid Ground Fill
        map.addLayer({
          id: 'crops-2d-fill',
          type: 'fill',
          source: 'crops-source',
          paint: {
            'fill-color': ['get', 'color'],
            'fill-opacity': 0.75,
          },
        });

        // 2. Thick White Outlines (draped on surface)
        map.addLayer({
          id: 'crops-outline',
          type: 'line',
          source: 'crops-source',
          paint: {
            'line-color': '#ffffff',
            'line-width': 3,
            'line-opacity': 1.0,
          },
        });

        // --- 3.5. ADD VILLAGES DATA SOURCE ---
        if (villageData) {
          map.addSource('villages-source', {
            type: 'geojson',
            data: villageData as any,
          });

          map.addLayer({
            id: 'villages-points',
            type: 'circle',
            source: 'villages-source',
            paint: {
              'circle-radius': 6,
              'circle-color': [
                'match',
                ['get', 'current_risk_level'],
                'high', '#ef4444',
                'medium', '#f59e0b',
                'low', '#10b981',
                '#888888'
              ],
              'circle-stroke-width': 2,
              'circle-stroke-color': '#ffffff'
            }
          });
        }
      }

      // --- 4. ADD FLOATING HTML BADGE PINS ---
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      cropData.features.forEach((feature) => {
        const props = feature.properties;
        const coords = feature.geometry.coordinates[0][0] as [number, number];

        // Create Badge Element
        const el = document.createElement('div');
        el.className = 'crop-badge';
        el.style.backgroundColor = props.color;
        el.style.color = '#ffffff';
        el.style.padding = '5px 10px';
        el.style.borderRadius = '14px';
        el.style.fontSize = '12px';
        el.style.fontWeight = '700';
        el.style.fontFamily = 'system-ui, sans-serif';
        el.style.boxShadow = '0 6px 16px rgba(0,0,0,0.6)';
        el.style.border = '2px solid #ffffff';
        el.style.cursor = 'pointer';
        el.style.whiteSpace = 'nowrap';
        el.innerText = `${props.cropType} (${props.fieldAreaAcres}ac)`;

        el.addEventListener('click', () => {
          setSelectedCrop(props);
          map.flyTo({ center: coords, zoom: 14.5, pitch: 50, duration: 1000 });
        });

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat(coords)
          .addTo(map);

        markersRef.current.push(marker);
      });

      // Village badges
      if (villageData && villageData.features) {
        (villageData as any).features.forEach((feature: any) => {
          const props = feature.properties;
          const coords = feature.geometry.coordinates as [number, number];

          const el = document.createElement('div');
        el.className = 'village-badge';
        el.style.backgroundColor = props.current_risk_level === 'high' ? '#ef4444' : props.current_risk_level === 'medium' ? '#f59e0b' : '#10b981';
        el.style.color = '#ffffff';
        el.style.padding = '4px 8px';
        el.style.borderRadius = '12px';
        el.style.fontSize = '11px';
        el.style.fontWeight = '700';
        el.style.fontFamily = 'system-ui, sans-serif';
        el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.5)';
        el.style.border = '2px solid #ffffff';
        el.style.cursor = 'pointer';
        el.style.whiteSpace = 'nowrap';
        el.innerText = `${props.panchayat_name}`;

        el.addEventListener('click', () => {
          setSelectedCrop(props); // Using same state for convenience
          map.flyTo({ center: coords, zoom: 12, pitch: 45, duration: 1000 });
        });

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat(coords)
          .addTo(map);

          markersRef.current.push(marker);
        });
      }

      // Interactive Click on 2D Crop Parcel
      map.on('click', 'crops-2d-fill', (e) => {
        if (e.features && e.features[0]) {
          const props = e.features[0].properties;
          setSelectedCrop(props);

          new maplibregl.Popup({ offset: 25, closeButton: false })
            .setLngLat(e.lngLat)
            .setHTML(`
              <div style="font-family: sans-serif; padding: 6px 10px; color: #111;">
                <strong style="font-size: 15px; color: ${props.color};">${props.cropType} (${props.variety})</strong>
                <div style="font-size: 12px; margin-top: 4px; color: #555;">Farmer: <b>${props.farmer}</b></div>
                <div style="font-size: 12px; color: #555;">Area: <b>${props.fieldAreaAcres} Acres</b></div>
                <div style="font-size: 12px; color: #555;">NDVI Score: <b>${props.ndvi}</b> | Health: <b>${props.healthStatus}</b></div>
              </div>
            `)
            .addTo(map);
        }
      });

      map.on('mouseenter', 'crops-2d-fill', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'crops-2d-fill', () => {
        map.getCanvas().style.cursor = '';
      });

      // Navigation & Official MapLibre 3D Terrain Controls
      map.addControl(
        new maplibregl.NavigationControl({
          visualizePitch: true,
          showZoom: true,
          showCompass: true,
        }),
        'top-right'
      );

      map.addControl(
        new maplibregl.TerrainControl({
          source: 'terrain-dem-terrarium',
          exaggeration: 1,
        }),
        'top-right'
      );

      map.addControl(
        new maplibregl.GlobeControl(),
        'top-right'
      );
    });

    return () => {
      if (orbitFrameRef.current) cancelAnimationFrame(orbitFrameRef.current);
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Basemap switcher
  const switchBasemap = (type: 'osm' | 'satellite' | 'carto') => {
    setCurrentBasemap(type);
    if (!mapRef.current) return;
    const map = mapRef.current;
    const source = map.getSource('basemap-source') as maplibregl.RasterTileSource;
    if (source && typeof (source as any).setTiles === 'function') {
      (source as any).setTiles([BASEMAP_TILES[type]]);
    }
  };

  // Switch DEM Source (AWS Terrarium vs MapLibre RGB)
  const switchTerrain = (provider: 'terrarium' | 'maplibre') => {
    setTerrainProvider(provider);
    if (!mapRef.current) return;
    const map = mapRef.current;
    const sourceId = provider === 'terrarium' ? 'terrain-dem-terrarium' : 'terrain-dem-maplibre';
    map.setTerrain({
      source: sourceId,
      exaggeration: 1,
    });
  };

  // Camera Pitch Adjuster
  const handlePitchChange = (newPitch: number) => {
    setPitch(newPitch);
    if (!mapRef.current) return;
    mapRef.current.setPitch(newPitch);
  };

  // Camera Bearing Adjuster
  const handleBearingChange = (newBearing: number) => {
    setBearing(newBearing);
    if (!mapRef.current) return;
    mapRef.current.setBearing(newBearing);
  };

  // Fly to Location Preset
  const flyToLocation = (loc: (typeof LOCATIONS)[0]) => {
    if (!mapRef.current) return;
    stopOrbit();
    mapRef.current.flyTo({
      center: loc.center,
      zoom: loc.zoom,
      pitch: loc.pitch,
      bearing: loc.bearing,
      duration: 2500,
      essential: true,
    });
  };

  // 360° Cinematic Orbit Animation
  const toggleOrbit = () => {
    if (isOrbiting) {
      stopOrbit();
    } else {
      setIsOrbiting(true);
      const orbit = () => {
        if (!mapRef.current) return;
        const currentB = mapRef.current.getBearing();
        mapRef.current.setBearing((currentB + 0.35) % 360);
        orbitFrameRef.current = requestAnimationFrame(orbit);
      };
      orbitFrameRef.current = requestAnimationFrame(orbit);
    }
  };

  const stopOrbit = () => {
    if (orbitFrameRef.current) {
      cancelAnimationFrame(orbitFrameRef.current);
      orbitFrameRef.current = null;
    }
    setIsOrbiting(false);
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Map Target Canvas */}
      <div
        ref={mapContainer}
        className={className}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
        }}
      />

      {/* Floating HUD Dashboard */}
      <div
        style={{
          position: 'absolute',
          top: 20,
          left: 20,
          background: 'rgba(15, 23, 42, 0.94)',
          backdropFilter: 'blur(12px)',
          borderRadius: 14,
          padding: '16px 18px',
          color: '#fff',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          width: 330,
          zIndex: 10,
          maxHeight: 'calc(100vh - 40px)',
          overflowY: 'auto',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
            🌾 3D Crop Map
          </h2>
          <button
            onClick={toggleOrbit}
            style={{
              background: isOrbiting ? '#ef4444' : '#8b5cf6',
              border: 'none',
              borderRadius: 6,
              color: '#fff',
              fontSize: 11,
              fontWeight: 600,
              padding: '4px 8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            {isOrbiting ? '⏹ Stop' : '🔄 Orbit 360°'}
          </button>
        </div>

        {/* 🏔️ 3D Mountain Mesh Showcase Fly-To Buttons */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#38bdf8', textTransform: 'uppercase', marginBottom: 6 }}>
            🏔️ 3D Terrain & Parcel Locations
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {LOCATIONS.map((loc) => (
              <button
                key={loc.name}
                onClick={() => flyToLocation(loc)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'rgba(255,255,255,0.07)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 6,
                  color: '#e2e8f0',
                  fontSize: 12,
                  padding: '6px 8px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <span style={{ fontWeight: 600 }}>{loc.name}</span>
                <span style={{ fontSize: 10, color: '#94a3b8' }}>Fly ✈️</span>
              </button>
            ))}
          </div>
        </div>

        {/* 3D DEM Provider Selector */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 6 }}>
            3D Elevation Source
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => switchTerrain('terrarium')}
              style={{
                flex: 1,
                background: terrainProvider === 'terrarium' ? '#10b981' : 'rgba(255,255,255,0.08)',
                border: 'none',
                borderRadius: 6,
                color: '#fff',
                fontSize: 11,
                fontWeight: 600,
                padding: '5px 2px',
                cursor: 'pointer',
              }}
            >
              AWS Terrarium (Global)
            </button>
            <button
              onClick={() => switchTerrain('maplibre')}
              style={{
                flex: 1,
                background: terrainProvider === 'maplibre' ? '#10b981' : 'rgba(255,255,255,0.08)',
                border: 'none',
                borderRadius: 6,
                color: '#fff',
                fontSize: 11,
                fontWeight: 600,
                padding: '5px 2px',
                cursor: 'pointer',
              }}
            >
              MapLibre Alps DEM
            </button>
          </div>
        </div>

        {/* Manual 3D Camera Controls */}
        <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 8, padding: 10, marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 8 }}>
            Camera & Terrain Controls
          </div>

          {/* Pitch Slider */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#cbd5e1' }}>
              <span>Tilt (Pitch):</span>
              <b>{pitch}°</b>
            </div>
            <input
              type="range"
              min="0"
              max="85"
              value={pitch}
              onChange={(e) => handlePitchChange(Number(e.target.value))}
              style={{ width: '100%', cursor: 'pointer', accentColor: '#3b82f6' }}
            />
          </div>

          {/* Bearing Slider */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#cbd5e1' }}>
              <span>Rotation (Bearing):</span>
              <b>{bearing}°</b>
            </div>
            <input
              type="range"
              min="-180"
              max="180"
              value={bearing}
              onChange={(e) => handleBearingChange(Number(e.target.value))}
              style={{ width: '100%', cursor: 'pointer', accentColor: '#3b82f6' }}
            />
          </div>
        </div>

        {/* Basemap Switcher */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 6 }}>
            Basemap Style
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {(['satellite', 'osm', 'carto'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => switchBasemap(mode)}
                style={{
                  flex: 1,
                  background: currentBasemap === mode ? '#3b82f6' : 'rgba(255,255,255,0.08)',
                  border: 'none',
                  borderRadius: 6,
                  color: '#fff',
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '5px 2px',
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {mode === 'osm' ? 'Vector/OSM' : mode}
              </button>
            ))}
          </div>
        </div>

        {/* Live Elevation Telemetry Status */}
        <div
          style={{
            background: 'rgba(56, 189, 248, 0.1)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: 8,
            padding: '8px 10px',
            marginBottom: 12,
            fontSize: 11,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#38bdf8', fontWeight: 600 }}>
            <span>📡 3D Mesh Status:</span>
            <span>{isLoaded ? '🟢 Loaded & Active' : '🟡 Initializing...'}</span>
          </div>
          <div style={{ color: '#cbd5e1', marginTop: 4 }}>
            Ground Elevation at Center:{' '}
            <b style={{ color: '#fff' }}>
              {currentElevation !== null ? `${currentElevation} meters (${Math.round(currentElevation * 3.28084)} ft)` : 'Scanning...'}
            </b>
          </div>
        </div>

        {/* Crop Field List */}
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: '#e2e8f0' }}>
          Crop Parcels ({cropData.features.length} Fields)
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 110, overflowY: 'auto' }}>
          {cropData.features.map((f) => (
            <div
              key={f.properties.id}
              onClick={() => {
                setSelectedCrop(f.properties);
                const coords = f.geometry.coordinates[0][0] as [number, number];
                mapRef.current?.flyTo({ center: coords, zoom: 14.5, pitch: 50, duration: 1000 });
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '4px 6px',
                borderRadius: 6,
                background: selectedCrop?.id === f.properties.id ? 'rgba(59, 130, 246, 0.35)' : 'rgba(255,255,255,0.05)',
                cursor: 'pointer',
                fontSize: 11,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: f.properties.color }} />
                <span>{f.properties.cropType}</span>
              </div>
              <span style={{ color: '#94a3b8', fontSize: 10 }}>{f.properties.fieldAreaAcres} ac</span>
            </div>
          ))}
        </div>
        {/* Village List */}
        {villageData && villageData.features && (
          <>
            <div style={{ fontSize: 12, fontWeight: 600, marginTop: 12, marginBottom: 6, color: '#e2e8f0' }}>
              Villages ({(villageData as any).features.length} Points)
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 110, overflowY: 'auto' }}>
              {(villageData as any).features.map((f: any) => (
                <div
                  key={f.properties.panchayat_id}
                  onClick={() => {
                    setSelectedCrop(f.properties);
                    const coords = f.geometry.coordinates as [number, number];
                    mapRef.current?.flyTo({ center: coords, zoom: 12, pitch: 45, duration: 1000 });
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '4px 6px',
                    borderRadius: 6,
                    background: selectedCrop?.panchayat_id === f.properties.panchayat_id ? 'rgba(59, 130, 246, 0.35)' : 'rgba(255,255,255,0.05)',
                    cursor: 'pointer',
                    fontSize: 11,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: f.properties.current_risk_level === 'high' ? '#ef4444' : f.properties.current_risk_level === 'medium' ? '#f59e0b' : '#10b981' }} />
                    <span>{f.properties.panchayat_name}</span>
                  </div>
                  <span style={{ color: '#94a3b8', fontSize: 10 }}>{f.properties.district}</span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Parcel/Village Inspection Details */}
        {selectedCrop && (
          <div
            style={{
              marginTop: 10,
              paddingTop: 8,
              borderTop: '1px solid rgba(255,255,255,0.12)',
              fontSize: 11,
            }}
          >
            {selectedCrop.cropType ? (
              <>
                <div style={{ fontWeight: 700, color: selectedCrop.color, fontSize: 13 }}>
                  {selectedCrop.cropType} — {selectedCrop.variety}
                </div>
                <div style={{ color: '#cbd5e1', marginTop: 2 }}>Farmer: {selectedCrop.farmer}</div>
                <div style={{ color: '#cbd5e1' }}>NDVI Score: <b>{selectedCrop.ndvi}</b> ({selectedCrop.healthStatus})</div>
                <div style={{ color: '#cbd5e1' }}>Moisture: <b>{selectedCrop.moistureLevel}</b> | Soil: {selectedCrop.soilType}</div>
              </>
            ) : (
              <>
                <div style={{ fontWeight: 700, color: selectedCrop.current_risk_level === 'high' ? '#ef4444' : selectedCrop.current_risk_level === 'medium' ? '#f59e0b' : '#10b981', fontSize: 13 }}>
                  {selectedCrop.panchayat_name} ({selectedCrop.panchayat_id})
                </div>
                <div style={{ color: '#cbd5e1', marginTop: 2 }}>District: {selectedCrop.district}</div>
                <div style={{ color: '#cbd5e1' }}>Block ID: <b>{selectedCrop.block_id}</b></div>
                <div style={{ color: '#cbd5e1' }}>Risk Level: <b>{selectedCrop.current_risk_level}</b></div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Bottom Floating Shortcut Cheat Sheet */}
      <div
        style={{
          position: 'absolute',
          bottom: 20,
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(8px)',
          borderRadius: 20,
          padding: '6px 16px',
          color: '#94a3b8',
          fontSize: 12,
          fontFamily: 'system-ui, sans-serif',
          display: 'flex',
          gap: 16,
          zIndex: 10,
          border: '1px solid rgba(255, 255, 255, 0.1)',
          pointerEvents: 'none',
        }}
      >
        <span>🖱️ <b>Right-Click + Drag</b> (or <b>Ctrl + Drag</b>) to rotate & pitch</span>
        <span>📜 <b>Scroll</b> to Zoom</span>
        <span>🖱️ <b>Left-Click + Drag</b> to Pan</span>
      </div>
    </div>
  );
}
