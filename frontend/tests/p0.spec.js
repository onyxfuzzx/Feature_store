import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

const base = process.env.P0_BASE_URL || "http://localhost:5188";
if (!["localhost", "127.0.0.1"].includes(new URL(base).hostname)) {
  throw new Error("P0 browser tests write fixtures and must target a disposable local stack");
}
const env = Object.fromEntries(readFileSync(process.env.P0_ENV_FILE || "../.cache/p0-stack.env", "utf8")
  .trim().split(/\r?\n/).map((line) => { const i = line.indexOf("="); return [line.slice(0, i), line.slice(i + 1)]; }));
let model, version, feature, headers;

test.beforeAll(async ({ request }) => {
  const login = await request.post("/api/auth/login", { data: { email: env.ADMIN_EMAIL, password: env.ADMIN_PASSWORD } });
  expect(login.ok()).toBeTruthy();
  headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
  async function post(path, data) {
    const response = await request.post(`/api${path}`, { headers, data });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  }
  const group = await post("/features/groups", { name: `browser_${Date.now()}` });
  feature = await post("/features", { group_id: group.id, name: `browser_spend_${Date.now()}`, dtype: "float",
    source_sql: "SELECT 'browser_entity' AS entity_key, 8 AS value", refresh_interval: "hourly", status: "active" });
  const run = await post(`/features/${feature.id}/materialize`, {});
  expect(run.status).toBe("success");
  model = await post("/models", { name: `Browser Model ${Date.now()}` });
  version = await post(`/models/${model.id}/versions`, { version: "browser-v1" });
  const artifact = { format: "featureops.linear.v1", task: "binary_classification",
    inputs: [{ name: "spend", feature_id: feature.id, dtype: "float" }], coefficients: [0.5], intercept: -1, classes: [0, 1] };
  const upload = await request.post(`/api/models/${model.id}/versions/${version.id}/artifact`, {
    headers, multipart: { file: { name: "trained.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(artifact)) } },
  });
  expect(upload.ok()).toBeTruthy();
});

async function signIn(page) {
  await page.goto("/login");
  await page.getByLabel("Email Address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page.getByRole("heading", { name: "Mission Control" })).toBeVisible();
}

test("promotion persists and exposes its recorded history", async ({ page, request }) => {
  const badRequests = [];
  page.on("request", (request) => { if (request.url().includes(":8000")) badRequests.push(request.url()); });
  await signIn(page);
  await page.goto(`/models/${model.id}`);
  await page.getByRole("button", { name: "Promote Stage", exact: true }).click();
  await page.getByRole("button", { name: "Confirm Promotion" }).click();
  await expect(page.getByRole("heading", { name: "Stage History - vbrowser-v1" })).toBeVisible();
  await expect(page.getByText("Staging → Production", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Close modal" }).click();
  await page.reload();
  await expect(page.getByRole("row").filter({ hasText: "vbrowser-v1" })).toContainText("Production");
  await page.getByRole("button", { name: "History", exact: true }).click();
  await expect(page.getByText("Staging → Production", { exact: false })).toBeVisible();
  const stored = await request.get(`/api/models/versions/${version.id}/detail`, { headers });
  expect((await stored.json()).stage_history[0].to_stage).toBe("Production");
  expect(badRequests).toEqual([]);
});

test("inference bench serves the registered artifact", async ({ page }) => {
  await signIn(page);
  await page.goto(`/models/${model.id}`);
  await page.getByRole("button", { name: "Real-Time Inference Bench" }).click();
  await page.locator('input[type="text"]').last().fill("browser_entity");
  const response = page.waitForResponse((response) => response.url().endsWith(`/models/${model.id}/predict`));
  await page.getByRole("button", { name: /Predict|Run Inference|Score/ }).click();
  const result = await (await response).json();
  expect(result.prediction.probability).toBeCloseTo(1 / (1 + Math.exp(-3)), 10);
  await expect(page.getByText("0.9525741268224334")).toBeVisible();
});

test("SQL preview denies sensitive data and ingestion reads through same origin", async ({ request }) => {
  const preview = await request.post("/api/features/dry-run", { headers, data: { query: "SELECT password_hash FROM core.users" } });
  expect((await preview.json()).is_valid).toBe(false);
  const pushed = await request.post("/api/features/stream-ingest", { headers, data: { records: [
    { entity_key: "browser_push", feature_name: feature.name, value: "0" },
  ] } });
  expect(pushed.status()).toBe(201);
  const values = await request.post("/api/features/online/batch", { headers,
    data: { entity_keys: ["browser_push"], features: [feature.id] } });
  expect((await values.json()).values.browser_push[feature.name]).toBe("0");
});
