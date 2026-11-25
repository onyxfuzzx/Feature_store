import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  // Workflows include several API writes, reloads and browser interactions.
  timeout: 120000,
  use: {
    baseURL: process.env.P0_BASE_URL || "http://localhost:5188",
    trace: "retain-on-failure",
    ignoreHTTPSErrors: process.env.P0_INSECURE_TLS === "1",
  },
});
