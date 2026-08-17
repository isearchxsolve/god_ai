/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['localhost', 'image.pollinations.ai', 'cdn.pollinations.ai'],
  },
  // Proxy API + generated media to the FastAPI backend so the frontend can use
  // relative URLs and avoid CORS entirely.
  async rewrites() {
    return [
      { source: '/api/v1/:path*', destination: `${BACKEND_URL}/api/v1/:path*` },
      { source: '/media/:path*', destination: `${BACKEND_URL}/media/:path*` },
      { source: '/health', destination: `${BACKEND_URL}/health` },
    ];
  },
};

module.exports = nextConfig;
