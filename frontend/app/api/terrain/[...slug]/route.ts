import { NextRequest, NextResponse } from 'next/server';

// In-memory tile cache to accelerate repeated terrain tile requests
const tileCache = new Map<string, ArrayBuffer>();
const MAX_CACHE_SIZE = 1000;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const { slug } = await params;
  if (!slug || slug.length < 3) {
    return new NextResponse('Invalid tile path', { status: 400 });
  }

  const [z, x, rawY] = slug;
  const fileName = rawY.endsWith('.png') ? rawY : `${rawY}.png`;
  const cacheKey = `${z}/${x}/${fileName}`;

  // Check in-memory cache first
  if (tileCache.has(cacheKey)) {
    const cachedBuffer = tileCache.get(cacheKey)!;
    return new NextResponse(cachedBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/png',
        'Cache-Control': 'public, max-age=31536000, immutable',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
      },
    });
  }

  const url = `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${fileName}`;

  try {
    const res = await fetch(url, {
      cache: 'force-cache',
    });

    if (!res.ok) {
      console.warn(`[TERRAIN API] Not found (${res.status}): ${url}`);
      return new NextResponse('Tile not found', { status: res.status });
    }

    const buffer = await res.arrayBuffer();

    // Cache in memory (evict oldest if full)
    if (tileCache.size >= MAX_CACHE_SIZE) {
      const firstKey = tileCache.keys().next().value;
      if (firstKey) tileCache.delete(firstKey);
    }
    tileCache.set(cacheKey, buffer);

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        'Content-Type': 'image/png',
        'Cache-Control': 'public, max-age=31536000, immutable',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
      },
    });
  } catch (error) {
    return new NextResponse('Error fetching elevation tile', { status: 500 });
  }
}

