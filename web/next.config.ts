import type { NextConfig } from "next";

const config: NextConfig = {
  // Phone footage is big; uploads go through a route handler for now (direct-to-bucket later).
  experimental: { serverActions: { bodySizeLimit: "500mb" } },
};

export default config;
