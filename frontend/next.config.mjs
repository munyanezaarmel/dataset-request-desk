// The browser only ever talks to Next.js at /api/...; Next forwards those calls
// to the FastAPI backend. Result: one origin, so no CORS configuration needed.
const API_URL = process.env.API_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
