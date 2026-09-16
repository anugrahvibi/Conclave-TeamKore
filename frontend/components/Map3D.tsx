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
  User,
  NavigationArrow,
  Plus,
  Minus,
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

// One dashboard, two profiles: k=0 officer (statewide Kerala view),
// k=1 farmer (flies to their village). Search & village interaction identical.
const DASH_OFFICER = 0;
const DASH_FARMER = 1;
const FARMER_HOME = {
  center: [76.08, 11.6] as [number, number],
  zoom: 12.6,
};

// Resolve a village's centroid for popups/flyTo: prefer the backend-provided
// centroid {lat, lon} (it may arrive JSON-stringified through GeoJSON
// properties), falling back to the click location. Polygon geometry
// coordinates are a nested ring and cannot be used directly as a center.
function villageCenter(props: any, fallback: [number, number]): [number, number] {
  let c = props?.centroid;
  if (typeof c === 'string') {
    try {
      c = JSON.parse(c);
    } catch {
      c = null;
    }
  }
  if (c && typeof c.lat === 'number' && typeof c.lon === 'number') return [c.lon, c.lat];
  return fallback;
}

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
  const villageLayersBoundRef = useRef<Set<string>>(new Set());

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

  const [dash, setDash] = useState<typeof DASH_OFFICER | typeof DASH_FARMER>(DASH_OFFICER);
  const isFarmerDash = dash === DASH_FARMER;
  const prevDashRef = useRef<number | null>(null);

  // Map Controls State
  const [is3D, setIs3D] = useState<boolean>(initialPitch > 0);
  const [isLocating, setIsLocating] = useState(false);

  // Client-side village fetch fallback if villageData prop is not passed
  useEffect(() => {
    if (villageData) {
      setLoadedVillageData(villageData);
      return;
    }
    let isMounted = true;
    fetch(`${backendUrl}/villages?format=geojson&limit=300`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data || !data.features) return;
        // Color each village polygon by risk_level: critical/high=red(frost), medium=orange(heat), low=green(none)
        const colorMap: Record<string, string> = {
          critical: '#dc2626',
          high: '#f97316',
          medium: '#eab308',
          low: '#22c55e',
        };
        const features = data.features.map((f: any) => {
          const props = f.properties || {};
          const risk = props.risk_level || 'low';
          return {
            ...f,
            properties: {
              ...props,
              village_id: props.village_id,
              panchayat_id: props.panchayat_id,
              panchayat_name: props.name || props.panchayat_name || 'Village',
              name_ml: props.name_ml || '',
              district: props.district,
              block_id: props.nearest_block_id || props.block_id,
              block_name: props.nearest_block_name || props.block_name,
              elevation_m: props.elevation_m ?? 100,
              land_cover: props.land_cover ?? 'agriculture',
              current_risk_level: risk,
              fillColor: colorMap[risk] || '#22c55e',
            },
          };
        });
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
        // Glyph server for symbol text layers (village name labels)
        glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
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
        el.style.borderRadius = '9999px';
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

    let setupDone = false;
    const safeSetup = () => {
      if (setupDone) return;
      setupDone = true;
      setupControls();
    };

    if (map.isStyleLoaded()) {
      safeSetup();
    } else {
      map.once('style.load', safeSetup);
      map.once('load', safeSetup);
      setTimeout(safeSetup, 1200);
    }

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      villageLayersBoundRef.current.clear();
      map.remove();
      mapRef.current = null;
    };
  }, [currentBasemap, initialCenter, initialZoom, initialPitch, initialBearing]);

  // Village layer visibility/paint per dashboard:
  // - Officer: full risk-shaded fills + heatmap, labels on from zoom 8
  // - Farmer: subtle risk shading + always-on clickable village name labels
  const applyVillageLayerMode = (map: maplibregl.Map, farmer: boolean) => {
    const setVis = (id: string, visible: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
    };
    setVis('villages-heat', !farmer);
    setVis('villages-fill', true);
    setVis('villages-outline', true);
    setVis('villages-labels', true);
    if (map.getLayer('villages-fill')) {
      map.setPaintProperty('villages-fill', 'fill-opacity', farmer ? 0.18 : 0.55);
    }
    if (map.getLayer('villages-outline')) {
      map.setPaintProperty('villages-outline', 'line-opacity', farmer ? 0.55 : 0.9);
    }
  };

  // Reactive effect to render/update villages GeoJSON source & layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded || !loadedVillageData) return;

    if (map.getSource('villages-source')) {
      (map.getSource('villages-source') as maplibregl.GeoJSONSource).setData(loadedVillageData);
    } else {
      map.addSource('villages-source', {
        type: 'geojson',
        data: loadedVillageData as any,
      });
    }

    // Remove old point/heatmap layers if they exist
    ['villages-heat', 'villages-points-bg', 'villages-points'].forEach((id) => {
      if (map.getLayer(id)) map.removeLayer(id);
    });

    // Village polygon fills — each village shaded by risk_level
    // red=frost (critical), orange=heat (high), yellow=rain (medium), green=none (low)
    if (!map.getLayer('villages-fill')) {
      map.addLayer({
        id: 'villages-fill',
        type: 'fill',
        source: 'villages-source',
        minzoom: 6,
        paint: {
          'fill-color': ['get', 'fillColor'],
          'fill-opacity': 0.55,
          'fill-outline-color': '#ffffff',
        },
      });

      map.addLayer({
        id: 'villages-outline',
        type: 'line',
        source: 'villages-source',
        minzoom: 6,
        paint: {
          'line-color': '#ffffff',
          'line-width': 1.5,
          'line-opacity': 0.9,
        },
      });
    }

    // Village name labels — each village labelled with its name
    if (!map.getLayer('villages-labels')) {
      map.addLayer({
        id: 'villages-labels',
        type: 'symbol',
        source: 'villages-source',
        minzoom: 8,
        layout: {
          'text-field': ['get', 'panchayat_name'],
          'text-size': 10,
          'text-offset': [0, 0],
          'text-anchor': 'center',
          'text-font': ['Open Sans Regular'],
          'text-max-width': 10,
        },
        paint: {
          'text-color': '#0f172a',
          'text-halo-color': '#ffffff',
          'text-halo-width': 2,
        },
      });
    }

    // Click + pointer-cursor handlers for village fills, outlines, and name labels.
    // Guarded so re-running this effect doesn't stack duplicate listeners.
    ['villages-fill', 'villages-outline', 'villages-labels'].forEach((layerId) => {
      if (!map.getLayer(layerId) || villageLayersBoundRef.current.has(layerId)) return;
      map.on('click', layerId, (e) => {
        if (!e.features || !e.features[0]) return;
        handleVillageClick(e as any);
      });
      map.on('mouseenter', layerId, () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', layerId, () => {
        map.getCanvas().style.cursor = '';
      });
      villageLayersBoundRef.current.add(layerId);
    });

    const mapNotNull = mapRef.current!;
    async function handleVillageClick(e: any) {
      if (!e.features || !e.features[0]) return;
      const props = e.features[0].properties as any;
      const coords = villageCenter(props, [e.lngLat.lng, e.lngLat.lat]);
      mapNotNull.flyTo({ center: coords, zoom: Math.max(mapNotNull.getZoom(), 11), pitch: 50, duration: 800 });

      const pinIconHtml = renderToStaticMarkup(<MapPin size={14} color="#0284c7" style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 4 }} />);
      const loadingIconHtml = renderToStaticMarkup(<CircleNotch size={14} color="#0284c7" style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: 4 }} />);

      const popup = new maplibregl.Popup({ offset: 15, maxWidth: '300px', closeButton: true })
        .setLngLat(coords)
        .setHTML(`
          <div style="font-family: system-ui, sans-serif; padding: 4px; color: #0f172a;">
            <div style="font-weight: 700; font-size: 13px; display: flex; align-items: center;">${pinIconHtml} <span>${props.panchayat_name || 'Village'}</span></div>
            <div style="font-size: 11px; color: #64748b; margin-bottom: 6px;">${props.district || ''} • Elev: ${props.elevation_m ?? 100}m</div>
            ${props.name_ml ? `<div style="font-size: 11px; color: #334155; margin-bottom: 6px;">${props.name_ml}</div>` : ''}
            <div id="popup-loading-${props.village_id || '0'}" style="font-size: 11px; color: #0284c7; display: flex; align-items: center;">${loadingIconHtml} <span>Loading live advisory & forecast...</span></div>
          </div>
        `)
        .addTo(mapNotNull);

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
        // Map risk_level to officer dashboard category colors: frost=red, heat=orange, rain=yellow, none=green
        const riskColor =
          riskLevel === 'critical'
            ? '#dc2626'
            : riskLevel === 'high'
            ? '#f97316'
            : riskLevel === 'medium'
            ? '#eab308'
            : '#22c55e';

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
            ${cropHtml}          </div>
        `);
      } catch {
        // Keep initial popup content if fetch fails
      }
    }

    applyVillageLayerMode(map, isFarmerDash);
  }, [isLoaded, loadedVillageData, backendUrl, isFarmerDash]);

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

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    const officer = dash === DASH_OFFICER;
    applyVillageLayerMode(map, !officer);

    markersRef.current.forEach((marker) => {
      marker.getElement().style.display = officer ? '' : 'none';
    });

    if (prevDashRef.current === null) {
      prevDashRef.current = dash;
      return;
    }
    if (prevDashRef.current === dash) return;
    prevDashRef.current = dash;

    map.flyTo({
      center: officer ? initialCenter : FARMER_HOME.center,
      zoom: officer ? initialZoom : FARMER_HOME.zoom,
      pitch: officer ? initialPitch : 52,
      bearing: officer ? initialBearing : 18,
      duration: 1400,
      essential: true,
    });
  }, [dash, isLoaded, initialCenter, initialZoom, initialPitch, initialBearing]);

  return (
    <div
      data-k={dash}
      style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}
    >
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

      {/* Top-right profile — unlabeled toggle between the two dashboards */}
      <button
        type="button"
        onClick={() => {
          setIsSearchOpen(false);
          setSearchQuery('');
          setIsMapViewMenuOpen(false);
          setDash((prev) => (prev === DASH_OFFICER ? DASH_FARMER : DASH_OFFICER));
        }}
        aria-label="Switch profile"
        style={{
          position: 'absolute',
          top: 20,
          right: 20,
          zIndex: 40,
          width: 44,
          height: 44,
          borderRadius: 9999,
          border: isFarmerDash ? '2px solid #0284c7' : '1px solid #e2e8f0',
          background: '#ffffff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 0,
          fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          transition: 'background 0.15s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#f8fafc';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#ffffff';
        }}
      >
        <User size={22} color="#0f172a" weight={isFarmerDash ? 'fill' : 'regular'} />
      </button>

      {/* Top-Left Search: shared by both profiles; profile toggle only changes map focus */}
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
                      borderRadius: 14,
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
                        borderRadius: 9999,
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
                    borderRadius: 4,
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
            borderRadius: 16,
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
