import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The page reads the seed run from disk when it refreshes, so ship it with the server function.
  outputFileTracingIncludes: { "/": ["./data/seed-run.json"] },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
