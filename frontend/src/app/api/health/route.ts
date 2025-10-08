import { NextResponse } from 'next/server';

export async function GET() {
  try {
    // Basic health check - could be extended to check API connectivity
    return NextResponse.json(
      {
        status: 'healthy',
        timestamp: new Date().toISOString(),
        service: 'aegis-admin-ui',
        version: process.env.npm_package_version || '1.0.0'
      },
      { status: 200 }
    );
  } catch (error) {
    console.error('Health check error:', error);
    return NextResponse.json(
      {
        status: 'unhealthy',
        timestamp: new Date().toISOString(),
        service: 'aegis-admin-ui',
        error: 'Health check failed'
      },
      { status: 500 }
    );
  }
}
