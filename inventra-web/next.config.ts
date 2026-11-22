import type { NextConfig } from "next";

const devOrigin = process.env.INVENTRA_DEV_ORIGIN?.trim();
const nextConfig: NextConfig = {
  ...(devOrigin ? { allowedDevOrigins: [devOrigin] } : {}),
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:5000/api/:path*" }];
  },
};

export default nextConfig;
