/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'api.dicebear.com' },
      { protocol: 'https', hostname: 'lh3.googleusercontent.com' },
      { protocol: 'https', hostname: 'images.unsplash.com' },
    ],
  },
  // Bundle the seeded SQLite file with every serverless function so cold-start
  // bootstrap in lib/prisma.ts can copy it to /tmp.
  experimental: {
    outputFileTracingIncludes: {
      '/**': ['./data/seed.db'],
    },
  },
}

module.exports = nextConfig
