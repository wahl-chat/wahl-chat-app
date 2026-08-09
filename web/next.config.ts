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
};

// next.config.ts is loaded via Next's CJS shim, so require() is correct here; the
// ESLint no-require-imports rule (which fires when this file is linted directly, e.g.
// by lint-staged) does not apply.
// eslint-disable-next-line @typescript-eslint/no-require-imports
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

export default withBundleAnalyzer(nextConfig);
