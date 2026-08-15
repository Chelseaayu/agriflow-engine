import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The dashboard route reads committed artifacts from the repository root.
  // Keep the tracing scope narrow so raw Siskaperbapo evidence is not bundled.
  outputFileTracingRoot: path.join(__dirname, ".."),
  outputFileTracingIncludes: {
    "/api/v1/[...route]": [
      "../sample_data/forecasts/forecast_all.json",
      "../sample_data/anomalies/anomalies_all.json",
      "../sample_data/kabupaten_jatim.csv",
    ],
  },
};

export default nextConfig;
