'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Translate,
  Thermometer,
  CloudRain,
  Wind,
  Warning,
  CheckCircle,
  ShieldWarning,
  CircleNotch,
  CaretDown,
  Sun,
  CloudSun,
  Plant,
} from '@phosphor-icons/react';

export type Language = 'en' | 'ml';

export const TRANSLATIONS = {
  en: {
    langBtn: 'മലയാളം',
    today: 'Today',
    tomorrow: 'Tomorrow',
    day3: 'Day 3',
    advisoryTitle: 'Agro-Climate Advisory',
    liveAdvisory: 'Live Field Advisory',
    tempRange: 'Temperature',
    rainChance: 'Rain Probability',
    windSpeed: 'Max Wind',
    humidity: 'Avg Humidity',
    riskLevel: 'Risk Severity',
    recommendations: 'Actionable Field Guidance',
    confidence: 'ML Confidence',
    elevation: 'Elevation',
    district: 'District',
    lowRisk: 'Low Risk',
    mediumRisk: 'Moderate Risk',
    highRisk: 'High Risk',
    criticalRisk: 'Critical Alert',
    forecastTitle: '3-Day Micro-Forecast',
    selectVillage: 'Select Panchayat',
    loading: 'Fetching live agro-climatic data...',
    noAdvice: 'Normal crop conditions. Follow standard seasonal management schedule.',
    switchPanchayat: 'Change village / panchayat',
    timeSlots: ['00:00 (Night)', '06:00 (Morning)', '12:00 (Noon)', '18:00 (Evening)'],
    weatherConditions: {
      'Heavy Rain': 'Heavy Rain',
      'Moderate Rain': 'Moderate Rain',
      'Light Rain': 'Light Rain',
      'Hot & Sunny': 'Hot & Sunny',
      'Humid & Overcast': 'Humid & Overcast',
      'Partly Cloudy': 'Partly Cloudy',
    },
  },
  ml: {
    langBtn: 'English',
    today: 'ഇന്ന്',
    tomorrow: 'നാളെ',
    day3: 'മൂന്നാം ദിവസം',
    advisoryTitle: 'കാർഷിക നിർദ്ദേശം',
    liveAdvisory: 'തത്സമയ കാർഷിക മുന്നറിയിപ്പ്',
    tempRange: 'താപനില',
    rainChance: 'മഴ സാധ്യത',
    windSpeed: 'കാറ്റിന്റെ വേഗത',
    humidity: 'ഈർപ്പം',
    riskLevel: 'അപകടസാധ്യത',
    recommendations: 'ചെയ്യേണ്ട മുൻകരുതലുകൾ',
    confidence: 'കൃത്യത',
    elevation: 'ഉയരം',
    district: 'ജില്ല',
    lowRisk: 'കുറഞ്ഞ അപകടസാധ്യത',
    mediumRisk: 'ഇടത്തരം അപകടസാധ്യത',
    highRisk: 'കൂടിയ അപകടസാധ്യത',
    criticalRisk: 'ഗുരുതര മുന്നറിയിപ്പ്',
    forecastTitle: '3 ദിവസത്തെ കാലാവസ്ഥാ പ്രവചനം',
    selectVillage: 'പഞ്ചായത്ത് മാറ്റുക',
    loading: 'വിവരങ്ങൾ ലഭ്യമാക്കുന്നു...',
    noAdvice: 'സാധാരണ കൃഷി കാലാവസ്ഥ. പതിവ് പരിചരണങ്ങൾ തുടരുക.',
    switchPanchayat: 'മറ്റൊരു ഗ്രാമം തിരഞ്ഞെടുക്കുക',
    timeSlots: ['00:00 (രാത്രി)', '06:00 (രാവിലെ)', '12:00 (ഉച്ചയ്ക്ക്)', '18:00 (വൈകുന്നേരം)'],
    weatherConditions: {
      'Heavy Rain': 'കനത്ത മഴ',
      'Moderate Rain': 'മിതമായ മഴ',
      'Light Rain': 'നേരിയ മഴ',
      'Hot & Sunny': 'ചൂടും വെയിലും',
      'Humid & Overcast': 'മേഘാവൃതമായ അന്തരീക്ഷം',
      'Partly Cloudy': 'ഭാഗികമായി മേഘാവൃതം',
    },
  },
};

interface ForecastDayData {
  dayLabelKey: 'today' | 'tomorrow' | 'day3';
  dateStr: string;
  minTemp: number;
  maxTemp: number;
  avgTemp: number;
  totalRain: number;
  rainChancePct: number;
  maxWind: number;
  avgHumidity: number;
  condition: string;
  steps: Array<{
    time: string;
    temp: number;
    rain: number;
    wind: number;
    humidity: number;
    condition: string;
  }>;
}

interface SidebarProps {
  panchayatId: string;
  backendUrl?: string;
  onSelectPanchayat?: (id: string) => void;
  availableVillages?: Array<{
    panchayat_id: string;
    village_id?: string;
    name: string;
    name_ml?: string;
    district?: string;
  }>;
}

export default function Sidebar({
  panchayatId = 'KL_PANCH_0001',
  backendUrl = 'http://localhost:8000',
  onSelectPanchayat,
  availableVillages = [],
}: SidebarProps) {
  const [lang, setLang] = useState<Language>('en');
  const [activeDay, setActiveDay] = useState<number>(0);
  const [forecastData, setForecastData] = useState<any>(null);
  const [advisoryData, setAdvisoryData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [villageSelectorOpen, setVillageSelectorOpen] = useState(false);

  const t = TRANSLATIONS[lang];

  // Fetch forecast and advisory data whenever panchayatId changes
  useEffect(() => {
    let isCurrent = true;
    setIsLoading(true);

    const fetchData = async () => {
      try {
        const targetId = panchayatId || 'KL_PANCH_0001';
        const [fcRes, advRes] = await Promise.all([
          fetch(`${backendUrl}/forecast/${targetId}`),
          fetch(`${backendUrl}/advisory/${targetId}?crop_stage=spraying_window`),
        ]);

        if (!isCurrent) return;

        if (fcRes.ok) {
          const fc = await fcRes.json();
          setForecastData(fc);
        } else {
          setForecastData(null);
        }

        if (advRes.ok) {
          const adv = await advRes.json();
          setAdvisoryData(adv);
        } else {
          setAdvisoryData(null);
        }
      } catch (err) {
        console.warn('Sidebar data fetch notice:', err);
      } finally {
        if (isCurrent) {
          setIsLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isCurrent = false;
    };
  }, [panchayatId, backendUrl]);

  // Aggregate 12 steps into 3 discrete days
  const dailyForecasts: ForecastDayData[] = useMemo(() => {
    const defaultDays: ForecastDayData[] = [
      {
        dayLabelKey: 'today',
        dateStr: 'Day 1',
        minTemp: 21,
        maxTemp: 29,
        avgTemp: 25,
        totalRain: 2.4,
        rainChancePct: 35,
        maxWind: 12,
        avgHumidity: 76,
        condition: 'Partly Cloudy',
        steps: [],
      },
      {
        dayLabelKey: 'tomorrow',
        dateStr: 'Day 2',
        minTemp: 20,
        maxTemp: 28,
        avgTemp: 24,
        totalRain: 0.0,
        rainChancePct: 10,
        maxWind: 10,
        avgHumidity: 70,
        condition: 'Partly Cloudy',
        steps: [],
      },
      {
        dayLabelKey: 'day3',
        dateStr: 'Day 3',
        minTemp: 22,
        maxTemp: 31,
        avgTemp: 26,
        totalRain: 6.8,
        rainChancePct: 65,
        maxWind: 15,
        avgHumidity: 82,
        condition: 'Moderate Rain',
        steps: [],
      },
    ];

    if (!forecastData || !forecastData.forecast_steps || forecastData.forecast_steps.length === 0) {
      return defaultDays;
    }

    const steps = forecastData.forecast_steps;
    const stepsPerDay = 4;
    const dayLabels: Array<'today' | 'tomorrow' | 'day3'> = ['today', 'tomorrow', 'day3'];

    return dayLabels.map((dayLabelKey, idx) => {
      const slice = steps.slice(idx * stepsPerDay, (idx + 1) * stepsPerDay);
      if (slice.length === 0) return defaultDays[idx];

      const temps = slice.map((s: any) => s.temp_c);
      const rains = slice.map((s: any) => s.rainfall_mm);
      const humids = slice.map((s: any) => s.humidity_pct);
      const winds = slice.map((s: any) => s.wind_kmh);

      const minTemp = Math.min(...temps);
      const maxTemp = Math.max(...temps);
      const avgTemp = temps.reduce((a: number, b: number) => a + b, 0) / temps.length;
      const totalRain = rains.reduce((a: number, b: number) => a + b, 0);
      const maxWind = Math.max(...winds);
      const avgHumidity = humids.reduce((a: number, b: number) => a + b, 0) / humids.length;

      // Calculate rain chance % from rain volume and steps with rain
      const rainSteps = slice.filter((s: any) => s.rainfall_mm > 0.1).length;
      let rainChancePct = Math.round((rainSteps / slice.length) * 100);
      if (totalRain > 10) rainChancePct = Math.max(rainChancePct, 85);
      else if (totalRain > 2) rainChancePct = Math.max(rainChancePct, 60);
      else if (totalRain > 0.2) rainChancePct = Math.max(rainChancePct, 30);
      else rainChancePct = Math.max(rainChancePct, 5);

      // Dominant condition
      const topCondition =
        slice.find((s: any) => s.rainfall_mm > 5)?.weather_condition ||
        slice.find((s: any) => s.rainfall_mm > 0.5)?.weather_condition ||
        slice[1]?.weather_condition ||
        slice[0]?.weather_condition ||
        'Partly Cloudy';

      const firstTs = slice[0]?.timestamp || '';
      let dateStr = `Day ${idx + 1}`;
      if (firstTs) {
        try {
          const d = new Date(firstTs);
          dateStr = d.toLocaleDateString(lang === 'ml' ? 'ml-IN' : 'en-US', {
            month: 'short',
            day: 'numeric',
          });
        } catch {
          dateStr = `Day ${idx + 1}`;
        }
      }

      return {
        dayLabelKey,
        dateStr,
        minTemp: Math.round(minTemp * 10) / 10,
        maxTemp: Math.round(maxTemp * 10) / 10,
        avgTemp: Math.round(avgTemp * 10) / 10,
        totalRain: Math.round(totalRain * 10) / 10,
        rainChancePct,
        maxWind: Math.round(maxWind * 10) / 10,
        avgHumidity: Math.round(avgHumidity),
        condition: topCondition,
        steps: slice.map((s: any, sIdx: number) => ({
          time: t.timeSlots[sIdx] || s.timestamp,
          temp: Math.round(s.temp_c * 10) / 10,
          rain: Math.round(s.rainfall_mm * 10) / 10,
          wind: Math.round(s.wind_kmh * 10) / 10,
          humidity: Math.round(s.humidity_pct),
          condition: s.weather_condition,
        })),
      };
    });
  }, [forecastData, lang, t.timeSlots]);

  const activeForecast = dailyForecasts[activeDay] || dailyForecasts[0];

  // Advisory details
  const advisory = advisoryData?.advisory;
  const riskLevel = advisory?.risk_level || 'low';
  const riskText =
    riskLevel === 'critical'
      ? t.criticalRisk
      : riskLevel === 'high'
      ? t.highRisk
      : riskLevel === 'medium'
      ? t.mediumRisk
      : t.lowRisk;

  const riskBadgeBg =
    riskLevel === 'critical'
      ? 'bg-red-100 text-red-700'
      : riskLevel === 'high'
      ? 'bg-orange-100 text-orange-700'
      : riskLevel === 'medium'
      ? 'bg-amber-100 text-amber-800'
      : 'bg-emerald-100 text-emerald-700';

  const riskIcon =
    riskLevel === 'critical' ? (
      <Warning size={16} className="text-red-600 shrink-0" weight="fill" />
    ) : riskLevel === 'high' ? (
      <ShieldWarning size={16} className="text-orange-600 shrink-0" weight="fill" />
    ) : riskLevel === 'medium' ? (
      <Warning size={16} className="text-amber-600 shrink-0" weight="bold" />
    ) : (
      <CheckCircle size={16} className="text-emerald-600 shrink-0" weight="fill" />
    );

  const villageName =
    lang === 'ml' && (forecastData?.village_name_ml || advisoryData?.village_name_ml)
      ? forecastData?.village_name_ml || advisoryData?.village_name_ml
      : forecastData?.village_name || advisoryData?.village_name || panchayatId;

  const district =
    forecastData?.nearest_block?.district ||
    advisoryData?.district ||
    'Kerala';

  const elevation = forecastData?.static_features?.elevation_m ?? 100;

  return (
    <aside
      className="w-full md:w-[380px] lg:w-[410px] shrink-0 h-full rounded-[4rem] [corner-shape:squircle] overflow-hidden bg-white flex flex-col transition-all duration-300 relative z-20"
      style={{
        fontFamily:
          'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {/* Top Header: Location, Elevation & Language Switcher */}
      <div className="p-4 sm:p-5 flex items-center justify-between shrink-0 bg-slate-50">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-full bg-sky-100 flex items-center justify-center shrink-0">
            <Plant size={18} className="text-sky-600" weight="bold" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h2 className="text-lg md:text-xl font-extrabold text-slate-900 truncate">
                {villageName}
              </h2>
              {availableVillages.length > 0 && onSelectPanchayat && (
                <button
                  type="button"
                  onClick={() => setVillageSelectorOpen(!villageSelectorOpen)}
                  className="text-slate-400 hover:text-slate-700 p-0.5 rounded-full hover:bg-slate-200/60 transition-colors"
                  title={t.switchPanchayat}
                >
                  <CaretDown size={14} />
                </button>
              )}
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-500 font-medium">
              <span>{district}</span>
              <span>•</span>
              <span>{t.elevation}: {Math.round(elevation)}m</span>
            </div>
          </div>
        </div>

        {/* Language Toggle Button */}
        <button
          type="button"
          onClick={() => setLang((prev) => (prev === 'en' ? 'ml' : 'en'))}
          className="rounded-full px-3 py-1.5 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-xs font-semibold text-slate-800 transition-all flex items-center gap-1.5 cursor-pointer shrink-0"
          aria-label="Toggle language"
        >
          <Translate size={15} className="text-sky-600" />
          <span>{t.langBtn}</span>
        </button>
      </div>

      {/* Dropdown for Panchayat Switcher if toggled */}
      {villageSelectorOpen && availableVillages.length > 0 && (
        <div className="px-4 py-2 bg-slate-50 max-h-48 overflow-y-auto z-30">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
            {t.selectVillage}
          </div>
          <div className="flex flex-col gap-1">
            {availableVillages.map((v) => (
              <button
                key={v.panchayat_id || v.village_id}
                type="button"
                onClick={() => {
                  if (onSelectPanchayat) {
                    onSelectPanchayat(v.panchayat_id || v.village_id || '');
                  }
                  setVillageSelectorOpen(false);
                }}
                className={`text-left px-2.5 py-1.5 rounded-xl text-xs flex items-center justify-between transition-colors ${
                  (v.panchayat_id === panchayatId || v.village_id === panchayatId)
                    ? 'bg-sky-100 text-sky-800 font-bold'
                    : 'text-slate-700 hover:bg-slate-200/60'
                }`}
              >
                <span>{lang === 'ml' && v.name_ml ? v.name_ml : v.name}</span>
                <span className="text-[10px] text-slate-400">{v.district}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Scrollable Content Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-5 flex flex-col gap-4">
        {isLoading && (
          <div className="flex items-center justify-center py-4 text-xs font-medium text-sky-600 gap-2 bg-sky-50 rounded-2xl">
            <CircleNotch size={16} className="animate-spin" />
            <span>{t.loading}</span>
          </div>
        )}

        {/* ==================================================================== */}
        {/* 3-DAY FORECAST TABS: MOVING PILL ON A PILL */}
        {/* ==================================================================== */}
        <section className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-extrabold uppercase tracking-widest text-slate-800">
              {t.forecastTitle}
            </h3>
          </div>

          {/* Moving Pill Header Container */}
          <div className="relative bg-slate-100 p-1 rounded-full flex items-center">
            {/* The sliding pill indicator */}
            <div
              className="absolute top-1 bottom-1 rounded-full bg-white transition-all duration-300 ease-out z-0"
              style={{
                width: 'calc((100% - 8px) / 3)',
                left: `calc(4px + ${activeDay} * ((100% - 8px) / 3))`,
              }}
            />

            {/* Tab Buttons */}
            {dailyForecasts.map((day, index) => {
              const label = t[day.dayLabelKey];
              const isSelected = activeDay === index;
              return (
                <button
                  key={day.dayLabelKey}
                  type="button"
                  onClick={() => setActiveDay(index)}
                  className={`relative z-10 flex-1 py-1.5 text-center text-xs font-bold transition-colors duration-200 cursor-pointer rounded-full ${
                    isSelected ? 'text-slate-900' : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Active Tab Weather Summary Card */}
          <div className="bg-slate-100/70 rounded-2xl p-3.5 flex flex-col gap-3">
            {/* Top Row: Weather Condition & Date */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                {activeForecast.condition.includes('Rain') ? (
                  <CloudRain size={18} className="text-sky-600" weight="fill" />
                ) : activeForecast.condition.includes('Sunny') ? (
                  <Sun size={18} className="text-amber-500" weight="fill" />
                ) : (
                  <CloudSun size={18} className="text-slate-600" weight="fill" />
                )}
                <span className="text-xs font-bold text-slate-800">
                  {t.weatherConditions[activeForecast.condition as keyof typeof t.weatherConditions] ||
                    activeForecast.condition}
                </span>
              </div>
              <span className="text-[11px] font-medium text-slate-500 bg-white px-2 py-0.5 rounded-full">
                {activeForecast.dateStr}
              </span>
            </div>

            {/* Metric Grid: Temp Range, Rain Chance, Wind Speed */}
            <div className="grid grid-cols-3 gap-2 text-center">
              {/* Temp Range */}
              <div className="bg-white rounded-xl p-2 flex flex-col items-center justify-center">
                <div className="flex items-center gap-1 text-[10px] font-semibold text-slate-400 mb-0.5">
                  <Thermometer size={12} className="text-rose-500" />
                  <span>{t.tempRange}</span>
                </div>
                <div className="text-xs font-bold text-slate-800">
                  {activeForecast.minTemp}°C – {activeForecast.maxTemp}°C
                </div>
              </div>

              {/* Rain Chance */}
              <div className="bg-white rounded-xl p-2 flex flex-col items-center justify-center">
                <div className="flex items-center gap-1 text-[10px] font-semibold text-slate-400 mb-0.5">
                  <CloudRain size={12} className="text-sky-500" />
                  <span>{t.rainChance}</span>
                </div>
                <div className="text-xs font-bold text-sky-700">
                  {activeForecast.rainChancePct}%
                </div>
              </div>

              {/* Wind Speed */}
              <div className="bg-white rounded-xl p-2 flex flex-col items-center justify-center">
                <div className="flex items-center gap-1 text-[10px] font-semibold text-slate-400 mb-0.5">
                  <Wind size={12} className="text-teal-500" />
                  <span>{t.windSpeed}</span>
                </div>
                <div className="text-xs font-bold text-slate-800">
                  {activeForecast.maxWind} km/h
                </div>
              </div>
            </div>

            {/* Daily Timestep Progression Chips (6-hour intervals) */}
            {activeForecast.steps.length > 0 && (
              <div className="flex flex-col gap-1 pt-1">
                <div className="grid grid-cols-4 gap-1">
                  {activeForecast.steps.map((step, sIdx) => (
                    <div
                      key={sIdx}
                      className="bg-white rounded-lg p-1.5 text-center flex flex-col items-center gap-0.5"
                    >
                      <span className="text-[9px] font-semibold text-slate-400">
                        {sIdx === 0 ? '00h' : sIdx === 1 ? '06h' : sIdx === 2 ? '12h' : '18h'}
                      </span>
                      <span className="text-[11px] font-bold text-slate-800">{step.temp}°</span>
                      <span className="text-[9px] text-sky-600 font-medium">
                        {step.rain > 0 ? `${step.rain}mm` : '—'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ==================================================================== */}
        {/* PROMINENT ADVISORY CARD / BANNER (NOT BURIED BELOW THE FOLD) */}
        {/* ==================================================================== */}
        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-extrabold uppercase tracking-widest text-slate-800">
              {t.advisoryTitle}
            </h3>
            <span className="text-[10px] font-bold text-sky-600 uppercase">
              {advisory?.confidence || 'High'} {t.confidence}
            </span>
          </div>

          <div
            className={`rounded-2xl p-4 flex flex-col gap-3 transition-colors ${
              riskLevel === 'critical'
                ? 'bg-red-50'
                : riskLevel === 'high'
                ? 'bg-orange-50'
                : riskLevel === 'medium'
                ? 'bg-amber-50'
                : 'bg-emerald-50'
            }`}
          >
            {/* Header: Status badge & icon */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                {riskIcon}
                <span className="text-sm font-extrabold text-slate-900">{t.liveAdvisory}</span>
              </div>
              <span
                className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full ${riskBadgeBg}`}
              >
                {riskText}
              </span>
            </div>

            {/* Main Human-Readable Advice Banner */}
            <div className="bg-white rounded-xl p-3">
              <p className="text-xs font-semibold text-slate-800 leading-relaxed">
                &ldquo;{advisory?.text || t.noAdvice}&rdquo;
              </p>
            </div>

            {/* Actionable Recommendations List */}
            {advisory?.actionable_recommendations &&
              advisory.actionable_recommendations.length > 0 && (
                <div className="flex flex-col gap-1.5 pt-1">
                  <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
                    {t.recommendations}:
                  </span>
                  <div className="flex flex-col gap-1">
                    {advisory.actionable_recommendations.map((rec: string, idx: number) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2 text-xs text-slate-700 bg-white/70 rounded-lg p-1.5"
                      >
                        <CheckCircle
                          size={13}
                          className="text-emerald-600 shrink-0 mt-0.5"
                          weight="bold"
                        />
                        <span className="leading-snug">{rec}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
          </div>
        </section>
      </div>
    </aside>
  );
}
