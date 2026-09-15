'use client';

import React, { useEffect, useRef, useState, useMemo } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  Globe,
  MapTrifold,
  Compass,
  MagnifyingGlass,
  MapPin,
  Plant,
  Thermometer,
  CloudRain,
  Drop,
  Wind,
  CircleNotch,
  X,
  CaretUp,
  CaretDown,
  Mouse,
  Scroll,
  Buildings,
  Mountains,
  Waves,
  Tree,
  IconProps,
} from '@phosphor-icons/react';
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

const cartoApiKey = process.env.NEXT_PUBLIC_CARTO_API_KEY;
const BASEMAP_TILES = {
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  osm: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  carto:
    cartoApiKey && cartoApiKey !== 'your_carto_api_key_here' && cartoApiKey.trim() !== ''
      ? `https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${cartoApiKey}`
      : 'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
};

const BASEMAP_OPTIONS = [
  {
    id: 'satellite' as const,
    label: 'Satellite',
    icon: Globe,
    preview: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/4/8/11',
  },
  {
    id: 'osm' as const,
    label: 'Streets',
    icon: MapTrifold,
    preview: 'https://tile.openstreetmap.org/4/11/7.png',
  },
  {
    id: 'carto' as const,
    label: 'Voyager',
    icon: Compass,
    preview: cartoApiKey && cartoApiKey !== 'your_carto_api_key_here' && cartoApiKey.trim() !== ''
      ? `https://a.basemaps.cartocdn.com/rastertiles/voyager/4/11/7.png?key=${cartoApiKey}`
      : 'https://a.basemaps.cartocdn.com/rastertiles/voyager/4/11/7.png',
  },
];

// Preset quick search locations
const POPULAR_LOCATIONS = [
  { name: 'Kerala Overview', district: 'Statewide', center: [76.27, 10.85] as [number, number], zoom: 7.0, type: 'region', icon: Plant },
  { name: 'Idukki Highlands', district: 'Idukki', center: [77.0, 9.9] as [number, number], zoom: 11.0, type: 'region', icon: Mountains },
  { name: 'Alappuzha Backwaters', district: 'Alappuzha', center: [76.34, 9.49] as [number, number], zoom: 11.5, type: 'region', icon: Waves },
  { name: 'Wayanad Plantations', district: 'Wayanad', center: [76.08, 11.6] as [number, number], zoom: 11.0, type: 'region', icon: Tree },
  { name: 'Thiruvananthapuram', district: 'Thiruvananthapuram', center: [76.95, 8.52] as [number, number], zoom: 11.5, type: 'region', icon: Buildings },
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

  // Basemap & View Selector State
  const [currentBasemap, setCurrentBasemap] = useState<'osm' | 'satellite' | 'carto'>('satellite');
  const [isMapViewMenuOpen, setIsMapViewMenuOpen] = useState(false);
  const [isLoaded, setIsLoaded] = useState<boolean>(false);
  const [loadedVillageData, setLoadedVillageData] = useState<any>(villageData);

  // Search Bar / Pill State
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchContainerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

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

  // Handle click outside search to collapse pill
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        if (!searchQuery) {
          setIsSearchOpen(false);
        }
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [searchQuery]);

  // Focus input when search shifts to pill
  useEffect(() => {
    if (isSearchOpen) {
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    }
  }, [isSearchOpen]);

  // Suggestions computation
  const suggestions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      return POPULAR_LOCATIONS.map((loc) => ({
        id: `pop-${loc.name}`,
        title: loc.name,
        subtitle: loc.district,
        badge: 'Region',
        coords: loc.center,
        zoom: loc.zoom,
        icon: loc.icon,
      }));
    }

    const list: Array<{
      id: string;
      title: string;
      subtitle: string;
      badge: string;
      coords: [number, number];
      zoom: number;
      icon: React.ComponentType<IconProps>;
    }> = [];

    // Filter villages
    if (loadedVillageData?.features) {
      for (const f of loadedVillageData.features) {
        const p = f.properties;
        const name = (p.panchayat_name || '').toLowerCase();
        const dist = (p.district || '').toLowerCase();
        const nameMl = (p.name_ml || '').toLowerCase();

        if (name.includes(q) || dist.includes(q) || nameMl.includes(q)) {
          list.push({
            id: `v-${p.village_id || p.panchayat_id}`,
            title: p.panchayat_name,
            subtitle: `${p.district || ''} • Elev: ${p.elevation_m || 100}m`,
            badge: 'Village',
            coords: f.geometry.coordinates as [number, number],
            zoom: 12.5,
            icon: MapPin,
          });
          if (list.length >= 6) break;
        }
      }
    }

    // Filter crops
    if (cropData?.features) {
      for (const f of cropData.features) {
        const p = f.properties;
        const cropType = (p.cropType || '').toLowerCase();
        const variety = (p.variety || '').toLowerCase();
        const farmer = (p.farmer || '').toLowerCase();

        if (cropType.includes(q) || variety.includes(q) || farmer.includes(q)) {
          list.push({
            id: `c-${p.id || Math.random()}`,
            title: `${p.cropType} (${p.variety})`,
            subtitle: `Farmer: ${p.farmer} • ${p.fieldAreaAcres} ac`,
            badge: 'Crop',
            coords: f.geometry.coordinates[0][0] as [number, number],
            zoom: 14.5,
            icon: Plant,
          });
          if (list.length >= 10) break;
        }
      }
    }

    return list;
  }, [searchQuery, loadedVillageData]);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    if (typeof window !== 'undefined') {
      maplibregl.setWorkerUrl(`${origin}/maplibre-gl-worker.mjs`);
    }

    // Initialize Map with AWS Terrarium 3D Terrain & Hillshade Relief only
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'basemap-source': {
            type: 'raster',
            tiles: [BASEMAP_TILES[currentBasemap]],
            tileSize: 256,
            attribution: '© OpenStreetMap / Esri / CARTO / OpenFreeMap contributors',
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
              'hillshade-exaggeration': 0.8,
              'hillshade-shadow-color': '#94a3b8',
              'hillshade-highlight-color': 'rgba(255, 255, 255, 0.1)',
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
          'horizon-color': '#bae6fd',
          'horizon-fog-blend': 0.5,
          'fog-color': 'rgba(255, 255, 255, 0.1)',
          'fog-ground-blend': 0.5,
          'atmosphere-blend': 0.8,
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
    console.log('[Map3D] Map initialized with AWS Terrarium 3D Terrain');

    map.on('error', (e) => {
      if (e && e.error) {
        console.warn('MapLibre engine notice:', e.error.message || e.error);
      }
    });

    const setupControls = () => {
      map.resize();
      setIsLoaded(true);

      // --- ADD 3D CROP PARCELS DATA SOURCE ---
      if (!map.getSource('crops-source')) {
        map.addSource('crops-source', {
          type: 'geojson',
          data: cropData as any,
        });

        map.addLayer({
          id: 'crops-2d-fill',
          type: 'fill',
          source: 'crops-source',
          paint: {
            'fill-color': ['get', 'color'],
            'fill-opacity': 0.75,
          },
        });

        map.addLayer({
          id: 'crops-outline',
          type: 'line',
          source: 'crops-source',
          paint: {
            'line-color': '#ffffff',
            'line-width': 2.5,
            'line-opacity': 1.0,
          },
        });

        // Interactive Click on Crop Parcels
        map.on('click', 'crops-2d-fill', (e) => {
          if (e.features && e.features[0]) {
            const props = e.features[0].properties as any;
            const plantIconHtml = renderToStaticMarkup(<Plant size={16} color={props.color} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />);
            new maplibregl.Popup({ offset: 20, closeButton: true })
              .setLngLat(e.lngLat)
              .setHTML(`
                <div style="font-family: system-ui, sans-serif; padding: 6px 10px; color: #111;">
                  <strong style="font-size: 14px; color: ${props.color}; display: flex; align-items: center;">${plantIconHtml} <span>${props.cropType} (${props.variety})</span></strong>
                  <div style="font-size: 11px; margin-top: 4px; color: #444;">Farmer: <b>${props.farmer}</b></div>
                  <div style="font-size: 11px; color: #444;">Area: <b>${props.fieldAreaAcres} Acres</b></div>
                  <div style="font-size: 11px; color: #444;">NDVI: <b>${props.ndvi}</b> | Health: <b>${props.healthStatus}</b></div>
                  <div style="font-size: 11px; color: #444;">Soil: <b>${props.soilType}</b> | Moisture: <b>${props.moistureLevel}</b></div>
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
      }

      // Floating HTML Badge Pins for Crops
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      cropData.features?.forEach((feature) => {
        const props = feature.properties;
        const coords = feature.geometry.coordinates[0][0] as [number, number];

        const el = document.createElement('div');
        el.className = 'crop-badge';
        el.style.backgroundColor = props.color;
        el.style.color = '#ffffff';
        el.style.padding = '4px 8px';
        el.style.borderRadius = '12px';
        el.style.fontSize = '11px';
        el.style.fontWeight = '700';
        el.style.fontFamily = 'system-ui, sans-serif';
        el.style.border = '1px solid #e2e8f0';
        el.style.cursor = 'pointer';
        el.style.whiteSpace = 'nowrap';
        el.innerText = `${props.cropType} (${props.fieldAreaAcres}ac)`;

        el.addEventListener('click', () => {
          map.flyTo({ center: coords, zoom: 14.5, pitch: 50, duration: 1000 });
        });

        const marker = new maplibregl.Marker({ element: el }).setLngLat(coords).addTo(map);
        markersRef.current.push(marker);
      });

    };

    if (map.isStyleLoaded()) {
      setupControls();
    } else {
      map.once('style.load', setupControls);
      map.once('load', setupControls);
    }

    return () => {
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
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0,
            'rgba(16,185,129,0)',
            0.3,
            '#10b981',
            0.6,
            '#f59e0b',
            1.0,
            '#ef4444',
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
            'critical',
            '#dc2626',
            'high',
            '#ef4444',
            'medium',
            '#f59e0b',
            'low',
            '#10b981',
            '#6b7280',
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

    // Click handler → fetch live advisory & ML recommendations and show on map popup
    map.on('click', 'villages-points', async (e) => {
      if (!e.features || !e.features[0]) return;
      const props = e.features[0].properties as any;
      const coords = (e.features[0].geometry as any).coordinates as [number, number];
      map.flyTo({ center: coords, zoom: Math.max(map.getZoom(), 11), pitch: 50, duration: 800 });

      const pinIconHtml = renderToStaticMarkup(<MapPin size={14} color="#0284c7" style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 4 }} />);
      const loadingIconHtml = renderToStaticMarkup(<CircleNotch size={14} color="#0284c7" style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 4 }} />);

      const popup = new maplibregl.Popup({ offset: 15, maxWidth: '300px', closeButton: true })
        .setLngLat(coords)
        .setHTML(`
          <div style="font-family: system-ui, sans-serif; padding: 4px; color: #0f172a;">
            <div style="font-weight: 700; font-size: 13px; display: flex; align-items: center;">${pinIconHtml} <span>${props.panchayat_name || 'Village'}</span></div>
            <div style="font-size: 11px; color: #64748b; margin-bottom: 6px;">${props.district || ''} • Elev: ${props.elevation_m ?? 100}m</div>
            <div id="popup-loading-${props.village_id || '0'}" style="font-size: 11px; color: #0284c7; display: flex; align-items: center;">${loadingIconHtml} <span>Loading live advisory & forecast...</span></div>
          </div>
        `)
        .addTo(map);

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

        const advData = adv?.advisory;
        const riskLevel = advData?.risk_level || 'low';
        const riskColor =
          riskLevel === 'critical'
            ? '#dc2626'
            : riskLevel === 'high'
            ? '#ef4444'
            : riskLevel === 'medium'
            ? '#f59e0b'
            : '#10b981';

        const plantIconHtml = renderToStaticMarkup(<Plant size={12} color="#0284c7" style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 4 }} />);
        const topCrops = crops?.recommendations?.slice(0, 2) || [];
        const cropHtml = topCrops.length > 0
          ? `<div style="margin-top: 6px; border-top: 1px solid #e2e8f0; padding-top: 4px;">
              <span style="font-size: 10px; font-weight: 700; color: #0284c7; display: flex; align-items: center;">${plantIconHtml} <span>Top ML Crops:</span></span>
              ${topCrops.map((c: any) => `<div style="font-size: 10px; color: #334155;">• <b>${c.crop}</b> (${Math.round(c.suitability_score * 100)}% match)</div>`).join('')}
             </div>`
          : '';

        const tempIconHtml = renderToStaticMarkup(<Thermometer size={12} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 2 }} />);
        const rainIconHtml = renderToStaticMarkup(<CloudRain size={12} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 2 }} />);
        const humIconHtml = renderToStaticMarkup(<Drop size={12} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 2 }} />);
        const windIconHtml = renderToStaticMarkup(<Wind size={12} style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 2 }} />);

        const forecastHtml = fc?.summary
          ? `<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2px 6px; font-size: 10px; margin-bottom: 4px; color: #475569;">
              <div style="display: flex; align-items: center;">${tempIconHtml} <span>${fc.summary.avg_temp_c?.toFixed(1)}°C</span></div>
              <div style="display: flex; align-items: center;">${rainIconHtml} <span>${fc.summary.total_rainfall_mm?.toFixed(1)}mm rain</span></div>
              <div style="display: flex; align-items: center;">${humIconHtml} <span>${fc.summary.avg_humidity_pct?.toFixed(0)}% hum</span></div>
              <div style="display: flex; align-items: center;">${windIconHtml} <span>${fc.summary.max_wind_kmh?.toFixed(0)} km/h</span></div>
             </div>`
          : '';

        popup.setHTML(`
          <div style="font-family: system-ui, sans-serif; padding: 4px; color: #0f172a; max-width: 280px;">
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px;">
              <strong style="font-size: 13px; display: flex; align-items: center;">${pinIconHtml} <span>${props.panchayat_name}</span></strong>
              <span style="background: ${riskColor}; color: #fff; font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 4px; text-transform: uppercase;">
                ${riskLevel}
              </span>
            </div>
            <div style="font-size: 10px; color: #64748b; margin-bottom: 6px;">${props.district || ''}</div>
            ${forecastHtml}
            ${advData?.text ? `<div style="font-size: 10px; color: #334155; line-height: 1.3; margin-bottom: 4px;">${advData.text}</div>` : ''}
            ${cropHtml}
          </div>
        `);
      } catch {
        // Keep initial popup content if fetch fails
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

  // Fly to suggestion
  const handleSelectSuggestion = (item: { coords: [number, number]; zoom: number }) => {
    if (!mapRef.current) return;
    mapRef.current.flyTo({
      center: item.coords,
      zoom: item.zoom,
      pitch: 50,
      duration: 1500,
      essential: true,
    });
    setIsSearchOpen(false);
    setSearchQuery('');
  };

  const activeBasemapObj = BASEMAP_OPTIONS.find((b) => b.id === currentBasemap) || BASEMAP_OPTIONS[0];

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

      {/* Top-Left Search: Button that smoothly shifts to Pill with Dropdown (Completely White, DESIGN.md) */}
      <div
        ref={searchContainerRef}
        style={{
          position: 'absolute',
          top: 20,
          left: 20,
          zIndex: 30,
          fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        }}
      >
        {!isSearchOpen ? (
          // Search Button (Completely White, flat with single 1px border)
          <button
            onClick={() => setIsSearchOpen(true)}
            style={{
              background: '#ffffff',
              color: '#0f172a',
              border: '1px solid #e2e8f0',
              borderRadius: 9999,
              height: 44,
              padding: '0 18px',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'scale(1.03)';
              e.currentTarget.style.background = '#f8fafc';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.background = '#ffffff';
            }}
          >
            <MagnifyingGlass size={16} />
            <span>Search</span>
          </button>
        ) : (
          // Expanded Search Pill & Dropdown
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              width: 320,
              animation: 'expandPill 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            {/* White Pill Search Input */}
            <div
              style={{
                background: '#ffffff',
                borderRadius: 9999,
                height: 44,
                padding: '0 14px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                border: '1px solid #e2e8f0',
              }}
            >
              <MagnifyingGlass size={16} color="#64748b" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search village, crop, district..."
                style={{
                  border: 'none',
                  outline: 'none',
                  background: 'transparent',
                  width: '100%',
                  fontSize: 13,
                  color: '#0f172a',
                  fontWeight: 500,
                }}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{
                    background: '#f1f5f9',
                    border: 'none',
                    borderRadius: '50%',
                    width: 20,
                    height: 20,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 10,
                    color: '#64748b',
                    cursor: 'pointer',
                  }}
                >
                  <X size={12} color="#64748b" />
                </button>
              )}
              <button
                onClick={() => {
                  setIsSearchOpen(false);
                  setSearchQuery('');
                }}
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: 12,
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '2px 4px',
                  fontWeight: 600,
                }}
              >
                Close
              </button>
            </div>

            {/* Completely White Suggestion Dropdown (DESIGN.md squircle/rounded curve) */}
            <div
              style={{
                background: '#ffffff',
                marginTop: 8,
                borderRadius: 20,
                border: '1px solid #e2e8f0',
                maxHeight: 280,
                overflowY: 'auto',
                padding: 6,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
              }}
            >
              <div
                style={{
                  padding: '6px 12px 4px',
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: '#94a3b8',
                }}
              >
                {searchQuery ? 'Matching Results' : 'Featured & Suggested'}
              </div>

              {suggestions.length === 0 ? (
                <div style={{ padding: '12px 14px', fontSize: 12, color: '#64748b', textAlign: 'center' }}>
                  No matches found for &quot;{searchQuery}&quot;
                </div>
              ) : (
                suggestions.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSelectSuggestion(item)}
                    style={{
                      background: '#ffffff',
                      border: 'none',
                      borderRadius: 12,
                      padding: '8px 12px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                      width: '100%',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#f8fafc';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = '#ffffff';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <item.icon size={16} color="#0284c7" />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: '#0f172a' }}>{item.title}</span>
                        <span style={{ fontSize: 10, color: '#64748b' }}>{item.subtitle}</span>
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        background: item.badge === 'Crop' ? '#ecfdf5' : item.badge === 'Village' ? '#f0f9ff' : '#f8fafc',
                        color: item.badge === 'Crop' ? '#059669' : item.badge === 'Village' ? '#0284c7' : '#64748b',
                        padding: '2px 6px',
                        borderRadius: 6,
                        border: '1px solid rgba(0,0,0,0.06)',
                      }}
                    >
                      {item.badge}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Change Map View - Flat Square Button & Options (Bottom-Left) */}
      <div
        style={{
          position: 'absolute',
          bottom: 24,
          left: 24,
          zIndex: 20,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: 10,
        }}
      >
        {/* Expanded Square Basemap Selection Menu */}
        {isMapViewMenuOpen && (
          <div
            style={{
              display: 'flex',
              gap: 8,
              background: '#ffffff',
              padding: 8,
              borderRadius: 12,
              border: '1px solid #e2e8f0',
              animation: 'fadeIn 0.15s ease-in-out',
            }}
          >
            {BASEMAP_OPTIONS.map((option) => {
              const isSelected = currentBasemap === option.id;
              const IconComp = option.icon;
              return (
                <button
                  key={option.id}
                  onClick={() => {
                    switchBasemap(option.id);
                    setIsMapViewMenuOpen(false);
                  }}
                  style={{
                    width: 68,
                    height: 68,
                    borderRadius: 8,
                    border: isSelected ? '2px solid #0284c7' : '1px solid #e2e8f0',
                    backgroundImage: `url(${option.preview})`,
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    padding: 4,
                    color: '#ffffff',
                    fontFamily: 'system-ui, sans-serif',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span style={{ alignSelf: 'flex-end' }}>
                    <IconComp size={16} color="#ffffff" />
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      lineHeight: 1.1,
                    }}
                  >
                    {option.label}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* Main Flat Square Trigger Button */}
        <button
          onClick={() => setIsMapViewMenuOpen(!isMapViewMenuOpen)}
          title="Change Map View"
          style={{
            width: 64,
            height: 64,
            borderRadius: 10,
            border: '1px solid #e2e8f0',
            backgroundImage: `url(${activeBasemapObj.preview})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            cursor: 'pointer',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            padding: 5,
            color: '#ffffff',
            fontFamily: 'system-ui, sans-serif',
            transition: 'transform 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'scale(1.04)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            {(() => {
              const ActiveIcon = activeBasemapObj.icon;
              return <ActiveIcon size={16} color="#ffffff" />;
            })()}
            <span style={{ opacity: 0.9 }}>
              {isMapViewMenuOpen ? <CaretUp size={10} color="#ffffff" /> : <CaretDown size={10} color="#ffffff" />}
            </span>
          </div>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              lineHeight: 1.1,
              textAlign: 'left',
            }}
          >
            Map View
          </span>
        </button>
      </div>
    </div>
  );
}
