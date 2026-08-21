/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['localhost', 'api.nvidia.com', 'integrate.api.nvidia.com', 'image.pollinations.ai', 'cdn.pollinations.ai'],
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*', // Proxy to Backend
      },
    ]
  },
};

module.exports = nextConfig;