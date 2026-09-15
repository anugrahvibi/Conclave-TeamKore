'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
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
  backendUrl?: string;
}

const BASEMAP_TILES = {
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  osm: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  carto: 'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
};

// Kerala agro-advisory locations
const LOCATIONS = [
  {
    name: '🌾 Kerala Overview',
    center: [76.27, 10.85] as [number, number],
    zoom: 7.0,
    pitch: 40,
    bearing: -15,
    desc: 'Full Kerala overview — 1031 Panchayats & Municipalities',
  },
  {
    name: '🏔️ Idukki (Highland)',
    center: [77.0, 9.9] as [number, number],
    zoom: 10.5,
    pitch: 72,
    bearing: 30,
    desc: 'High elevation tea & spice plantations in the Western Ghats',
  },
  {
    name: '🌊 Alappuzha (Backwaters)',
    center: [76.34, 9.49] as [number, number],
    zoom: 11.0,
    pitch: 50,
    bearing: -20,
    desc: 'Famous backwaters & paddy fields of Kuttanad',
  },
  {
    name: '🌿 Wayanad (Forest)',
    center: [76.08, 11.6] as [number, number],
    zoom: 10.5,
    pitch: 65,
    bearing: 20,
    desc: 'Dense forest canopy with coffee & cardamom estates',
  },
  {
    name: '🏙️ Thiruvananthapuram',
    center: [76.95, 8.52] as [number, number],
    zoom: 11.0,
    pitch: 45,
    bearing: -10,
    desc: 'State capital with coastal plains & suburban agriculture',
  },
];

export default function Map3D({
  initialCenter = [76.27, 10.85] as [number, number], // Kerala, India
  initialZoom = 7.0,
  initialPitch = 45,
  initialBearing = -15,
  className = '',
  villageData,
  backendUrl = 'http://localhost:8000',
}: Map3DProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [selectedCrop, setSelectedCrop] = useState<any>(null);
  const [selectedVillage, setSelectedVillage] = useState<any>(null);
  const [villageAdvisory, setVillageAdvisory] = useState<any>(null);
  const [advisoryLoading, setAdvisoryLoading] = useState(false);
  const [currentBasemap, setCurrentBasemap] = useState<'osm' | 'satellite' | 'carto'>('satellite');
  const [terrainProvider, setTerrainProvider] = useState<'terrarium' | 'maplibre'>('terrarium');

  const [pitch, setPitch] = useState<number>(initialPitch);
  const [bearing, setBearing] = useState<number>(initialBearing);
  const [isOrbiting, setIsOrbiting] = useState<boolean>(false);
  const [currentElevation, setCurrentElevation] = useState<number | null>(null);
  const [isLoaded, setIsLoaded] = useState<boolean>(false);
  const [loadedVillageData, setLoadedVillageData] = useState<any>(villageData);
  const orbitFrameRef = useRef<number | null>(null);

  // Client-side village fetch fallback if villageData prop is not passed
  useEffect(() => {
    if (villageData) {
      setLoadedVillageData(villageData);
      return;
    }
    let isMounted = true;
    fetch(`${backendUrl}/villages?format=json&limit=300`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data || !data.villages) return;
        const features = data.villages.map((v: any) => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [v.lon, v.lat],
          },
          properties: {
            village_id: v.village_id,
            panchayat_id: v.panchayat_id,
            panchayat_name: v.name,
            name_ml: v.name_ml || '',
            district: v.district,
            block_id: v.nearest_block_id,
            block_name: v.nearest_block_name,
            elevation_m: v.static_features?.elevation_m ?? 100,
            land_cover: v.static_features?.land_cover ?? 'agriculture',
            current_risk_level: 'low',
          },
        }));
        setLoadedVillageData({ type: 'FeatureCollection', features });
      })
      .catch((err) => console.warn('Village fetch notice:', err));

    return () => {
      isMounted = false;
    };
  }, [villageData, backendUrl]);


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

    const setupControls = () => {
      map.resize();
      setIsLoaded(true);

      // Avoid adding controls multiple times
      if (!(map as any).__controlsAdded) {
        (map as any).__controlsAdded = true;
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
      }
    };

    if (map.isStyleLoaded()) {
      setupControls();
    } else {
      map.once('style.load', setupControls);
      map.once('load', setupControls);
    }

    return () => {
      if (orbitFrameRef.current) cancelAnimationFrame(orbitFrameRef.current);
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, [currentBasemap, initialCenter, initialZoom, initialPitch, initialBearing]);

  // Reactive effect to render/update villages GeoJSON source & layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded || !loadedVillageData) return;

    if (map.getSource('villages-source')) {
      (map.getSource('villages-source') as maplibregl.GeoJSONSource).setData(loadedVillageData);
      return;
    }

    map.addSource('villages-source', {
      type: 'geojson',
      data: loadedVillageData as any,
    });

    // Heatmap at low zoom
    if (!map.getLayer('villages-heat')) {
      map.addLayer({
        id: 'villages-heat',
        type: 'heatmap',
        source: 'villages-source',
        maxzoom: 9,
        paint: {
          'heatmap-weight': 1,
          'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 9, 2],
          'heatmap-color': [
            'interpolate', ['linear'], ['heatmap-density'],
            0, 'rgba(16,185,129,0)',
            0.3, '#10b981',
            0.6, '#f59e0b',
            1.0, '#ef4444'
          ],
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 5, 8, 9, 20],
          'heatmap-opacity': 0.75,
        },
      });
    }

    // Circles at zoom >= 8
    if (!map.getLayer('villages-points')) {
      map.addLayer({
        id: 'villages-points',
        type: 'circle',
        source: 'villages-source',
        minzoom: 8,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 4, 12, 9],
          'circle-color': [
            'match',
            ['get', 'current_risk_level'],
            'critical', '#dc2626',
            'high', '#ef4444',
            'medium', '#f59e0b',
            'low', '#10b981',
            '#6b7280'
          ],
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.9,
        },
      });
    }

    // Village name labels at high zoom
    if (!map.getLayer('villages-labels')) {
      map.addLayer({
        id: 'villages-labels',
        type: 'symbol',
        source: 'villages-source',
        minzoom: 11,
        layout: {
          'text-field': ['get', 'panchayat_name'],
          'text-size': 11,
          'text-offset': [0, 1.2],
          'text-anchor': 'top',
          'text-font': ['Open Sans Regular'],
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': 'rgba(0,0,0,0.8)',
          'text-halo-width': 1.5,
        },
      });
    }

    // Click handler → fetch live advisory & ML crop recommendations from backend
    map.on('click', 'villages-points', async (e) => {
      if (!e.features || !e.features[0]) return;
      const props = e.features[0].properties as any;
      const coords = (e.features[0].geometry as any).coordinates as [number, number];
      setSelectedCrop(null);
      setSelectedVillage(props);
      setVillageAdvisory(null);
      setAdvisoryLoading(true);
      map.flyTo({ center: coords, zoom: Math.max(map.getZoom(), 11), pitch: 50, duration: 800 });

      try {
        const targetId = props.panchayat_id || props.village_id || 'KL_PANCH_0001';
        const [advRes, fcRes, cropRes] = await Promise.all([
          fetch(`${backendUrl}/advisory/${targetId}?crop_stage=spraying_window`),
          fetch(`${backendUrl}/forecast/${targetId}`),
          fetch(`${backendUrl}/recommend-crop/${targetId}`),
        ]);
        const adv = advRes.ok ? await advRes.json() : null;
        const fc = fcRes.ok ? await fcRes.json() : null;
        const crops = cropRes.ok ? await cropRes.json() : null;
        setVillageAdvisory({
          advisory: adv,
          forecast: fc,
          crops: crops?.recommendations || [],
        });
      } catch {
        setVillageAdvisory({ error: 'Failed to fetch live data' });
      } finally {
        setAdvisoryLoading(false);
      }
    });

    map.on('mouseenter', 'villages-points', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'villages-points', () => {
      map.getCanvas().style.cursor = '';
    });
  }, [isLoaded, loadedVillageData, backendUrl]);

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
            🌾 Kerala Agro-Advisory
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

        {/* Village count badge */}
        {villageData && (
          <div style={{ fontSize: 11, color: '#38bdf8', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
            <b>{villageData.features?.length ?? 0}</b> Kerala Panchayats loaded from backend
          </div>
        )}

        {/* Risk legend */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
          {[['🔴', 'critical / high', '#ef4444'], ['🟡', 'medium', '#f59e0b'], ['🟢', 'low', '#10b981']].map(([icon, label, color]) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#cbd5e1' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: color as string }} />
              {label}
            </div>
          ))}
        </div>

        {/* Live Village Advisory Panel */}
        {(selectedVillage || advisoryLoading) && (
          <div style={{
            marginBottom: 10,
            padding: '10px 12px',
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16,185,129,0.25)',
            borderRadius: 10,
            fontSize: 11,
          }}>
            {advisoryLoading ? (
              <div style={{ color: '#38bdf8', fontWeight: 600 }}>⏳ Fetching live advisory from backend...</div>
            ) : selectedVillage && (
              <>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6, color:
                  villageAdvisory?.advisory?.advisory?.risk_level === 'critical' ? '#dc2626' :
                  villageAdvisory?.advisory?.advisory?.risk_level === 'high' ? '#ef4444' :
                  villageAdvisory?.advisory?.advisory?.risk_level === 'medium' ? '#f59e0b' : '#10b981'
                }}>
                  📍 {selectedVillage.panchayat_name}
                  <span style={{ marginLeft: 6, fontSize: 10, background: 'rgba(255,255,255,0.1)', borderRadius: 4, padding: '1px 5px', color: '#94a3b8' }}>
                    {selectedVillage.district}
                  </span>
                </div>

                {villageAdvisory?.error && (
                  <div style={{ color: '#ef4444' }}>⚠️ {villageAdvisory.error}</div>
                )}

                {villageAdvisory?.forecast && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 10px', marginBottom: 8 }}>
                    {[
                      ['🌡️', 'Temp', `${villageAdvisory.forecast.summary?.avg_temp_c?.toFixed(1)}°C`],
                      ['🌧️', 'Rain', `${villageAdvisory.forecast.summary?.total_rainfall_mm?.toFixed(1)}mm`],
                      ['💧', 'Humidity', `${villageAdvisory.forecast.summary?.avg_humidity_pct?.toFixed(0)}%`],
                      ['💨', 'Wind', `${villageAdvisory.forecast.summary?.max_wind_kmh?.toFixed(1)} km/h`],
                    ].map(([icon, label, val]) => (
                      <div key={label} style={{ color: '#e2e8f0' }}>
                        <span style={{ color: '#94a3b8' }}>{icon} {label}: </span><b>{val}</b>
                      </div>
                    ))}
                  </div>
                )}

                {villageAdvisory?.advisory?.advisory && (() => {
                  const adv = villageAdvisory.advisory.advisory;
                  const riskColor = adv.risk_level === 'critical' ? '#dc2626' : adv.risk_level === 'high' ? '#ef4444' : adv.risk_level === 'medium' ? '#f59e0b' : '#10b981';
                  return (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                        <span style={{ background: riskColor, color: '#fff', borderRadius: 4, padding: '1px 7px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase' }}>
                          {adv.risk_level} risk
                        </span>
                        <span style={{ color: '#94a3b8', fontSize: 10 }}>conf: {adv.confidence}</span>
                      </div>
                      <div style={{ color: '#cbd5e1', lineHeight: 1.4, marginBottom: 6 }}>{adv.text}</div>
                      {adv.actionable_recommendations?.slice(0, 2).map((r: string, i: number) => (
                        <div key={i} style={{ color: '#86efac', fontSize: 10, marginBottom: 2 }}>• {r}</div>
                      ))}
                    </>
                  );
                })()}

                {/* ML Crop Suitability Recommendations */}
                {villageAdvisory?.crops && villageAdvisory.crops.length > 0 && (
                  <div style={{ marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#38bdf8', marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>🤖 ML Crop Suitability Recommendations</span>
                      <span style={{ fontSize: 9, color: '#94a3b8' }}>RF + ICAR Rules</span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {villageAdvisory.crops.slice(0, 3).map((item: any, idx: number) => {
                        const scorePct = Math.round(item.suitability_score * 100);
                        const badgeColor = scorePct >= 90 ? '#10b981' : scorePct >= 75 ? '#3b82f6' : '#f59e0b';
                        return (
                          <div key={idx} style={{ background: 'rgba(255,255,255,0.05)', padding: '6px 8px', borderRadius: 6, border: '1px solid rgba(255,255,255,0.08)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                              <span style={{ textTransform: 'capitalize', fontWeight: 600, color: '#f8fafc', fontSize: 11 }}>
                                🌱 {item.crop}
                              </span>
                              <span style={{ background: badgeColor, color: '#fff', fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4 }}>
                                {scorePct}% Suitable
                              </span>
                            </div>
                            <div style={{ fontSize: 10, color: '#94a3b8', lineHeight: 1.3 }}>
                              {item.explanation}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Elevation & static info */}
        {selectedVillage && !advisoryLoading && (
          <div style={{ fontSize: 10, color: '#64748b', marginBottom: 8 }}>
            Elev: <b style={{ color: '#94a3b8' }}>{selectedVillage.elevation_m}m</b> ·
            Land: <b style={{ color: '#94a3b8' }}>{selectedVillage.land_cover}</b> ·
            Block: <b style={{ color: '#94a3b8' }}>{selectedVillage.block_id}</b>
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
