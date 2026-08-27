import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pins the workspace root to web/ itself -- without this Turbopack walks up looking
  // for a lockfile and finds one outside the git repo (a stray ~/package-lock.json),
  // which it warns about on every dev start.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
