import { NextRequest, NextResponse } from 'next/server';

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
