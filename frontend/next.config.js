/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    serverComponentsExternalPackages: ['keycloak-js'],
  },
};

module.exports = nextConfig;
