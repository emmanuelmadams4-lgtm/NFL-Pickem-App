import type { NextConfig } from "next";

// Static export: production files are served by the FastAPI app, so web and API share one origin.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  transpilePackages: ["@nflpi/shared"],
  devIndicators: false,
};

export default config;
