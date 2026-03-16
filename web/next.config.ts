import bundleAnalyzer from '@next/bundle-analyzer';
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'wahl.chat',
        port: '',
        pathname: '/images/**',
      },
      {
        protocol: 'https',
        hostname: 'dev.wahl.chat',
        port: '',
        pathname: '/images/**',
      },
    ],
  },
  webpack: (config: { resolve: { alias: { [key: string]: boolean } } }) => {
    config.resolve.alias.canvas = false;

    return config;
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/exploration-study/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/v1/exploration-study/:path*`,
      },
    ];
  },
};

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === 'true',
});

export default withBundleAnalyzer(nextConfig);
