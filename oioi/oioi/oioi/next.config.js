/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['localhost', 'image.pollinations.ai', 'cdn.pollinations.ai'],
  },
};

module.exports = nextConfig;
