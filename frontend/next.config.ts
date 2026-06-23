import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  devIndicators: {
    appIsrStatus: false // Disables the Static Route indicator
  }
};

export default nextConfig;
