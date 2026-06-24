import type { NextConfig } from "next";

// Next.js bakes rewrite destinations at build time, so BACKEND_URL must be set
// during `next build`. The default targets the compose service name, which is
// correct for the production image. Override at build time for local dev.
const backend = process.env.BACKEND_URL ?? "http://backend:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
