import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost", "100.124.44.113"],
  devIndicators: false,
  turbopack: {
    root: repoRoot,
  },
};

export default nextConfig;
