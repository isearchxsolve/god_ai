/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['localhost', 'api.nvidia.com', 'integrate.api.nvidia.com', 'image.pollinations.ai', 'cdn.pollinations.ai'],
  },
};

module.exports = nextConfig;