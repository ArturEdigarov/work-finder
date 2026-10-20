import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Lets a preview build live next to `pnpm dev` without clobbering its .next folder.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  // Same-origin proxy to FastAPI: the httpOnly session cookie works without CORS.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
};

export default createNextIntlPlugin()(nextConfig);
