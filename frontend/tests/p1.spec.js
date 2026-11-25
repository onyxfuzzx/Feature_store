import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

const base = process.env.P0_BASE_URL || "http://localhost:5188";
if (!["localhost", "127.0.0.1"].includes(new URL(base).hostname))
  throw new Error("Use a disposable local stack");
const env = Object.fromEntries(
  readFileSync(process.env.P0_ENV_FILE || "../.cache/p0-stack.env", "utf8")
    .trim()
    .split(/\r?\n/)
    .map((line) => {
      const i = line.indexOf("=");
      return [line.slice(0, i), line.slice(i + 1)];
    }),
);
let headers;
test.beforeAll(async ({ request }) => {
  const response = await request.post("/api/auth/login", {
    data: { email: env.ADMIN_EMAIL, password: env.ADMIN_PASSWORD },
  });
  expect(response.ok()).toBeTruthy();
  headers = { Authorization: `Bearer ${(await response.json()).access_token}` };
});
async function signIn(
  page,
  email = env.ADMIN_EMAIL,
  password = env.ADMIN_PASSWORD,
) {
  await page.goto("/login");
  await page.getByLabel("Email Address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Mission Control" }),
  ).toBeVisible();
}
async function post(request, path, data) {
  const response = await request.post("/api" + path, { headers, data });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

test("feature creation, materialization, accessible modal and visible query errors", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/features");
  const create = page
    .getByRole("button", { name: "Feature Group", exact: true })
    .first();
  await create.click();
  let dialog = page.getByRole("dialog", { name: "Create Feature Group" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(create).toBeFocused();
  await create.click();
  dialog = page.getByRole("dialog", { name: "Create Feature Group" });
  const group = "UI_" + Date.now();
  await dialog.getByLabel("Group Name").fill(group);
  await dialog.getByRole("button", { name: "Close modal" }).focus();
  await page.keyboard.press("Shift+Tab");
  await expect(
    dialog.getByRole("button", { name: "Create Group", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    dialog.getByRole("button", { name: "Close modal" }),
  ).toBeFocused();
  await dialog
    .getByRole("button", { name: "Create Group", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("button", { name: /Define Feature|New Feature/ })
    .click();
  dialog = page.getByRole("dialog", { name: "Define New Feature" });
  await dialog
    .getByLabel("Feature Group")
    .selectOption({ label: `${group} (dev)` });
  const name = "ui_feature_" + Date.now();
  await dialog.getByLabel("Feature Name").fill(name);
  await dialog
    .getByLabel("SQL Transformation")
    .fill("SELECT password_hash FROM core.users");
  await dialog.getByRole("button", { name: "Test Query (Dry Run)" }).click();
  await expect(dialog.getByRole("alert")).toContainText("permission denied");
  await dialog
    .getByLabel("SQL Transformation")
    .fill("SELECT 'ui_entity' AS entity_key, 7 AS value");
  await dialog
    .getByRole("button", {
      name: /Create Feature|Save Feature|Define Feature/,
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("link", { name, exact: true }).click();
  await page.getByRole("button", { name: "Materialize Now" }).click();
  await expect(
    page.getByText("Materialization finished with status:"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Online Serving Test Bench" }).click();
  await page.locator('input[type="text"]').last().fill("ui_entity");
  const lookup = page.waitForResponse((response) =>
    response.url().endsWith("/features/online/batch"),
  );
  await page
    .getByRole("button", { name: /Fetch|Lookup|Test/ })
    .last()
    .click();
  expect((await (await lookup).json()).values.ui_entity[name]).toBe("7");
});

test("registry artifact upload/download, linking, baseline and recorded drift", async ({
  page,
  request,
}) => {
  const group = await post(request, "/features/groups", {
    name: "Assets_" + Date.now(),
  });
  const source = await post(request, "/features", {
    group_id: group.id,
    name: "asset_value_" + Date.now(),
    dtype: "float",
    refresh_interval: "hourly",
    source_sql: "SELECT 'asset_entity' AS entity_key, 2 AS value",
  });
  await post(request, `/features/${source.id}/materialize`, {});
  const model = await post(request, "/models", {
    name: "UI Assets " + Date.now(),
  });
  await signIn(page);
  await page.goto(`/models/${model.id}`);
  await page.getByRole("button", { name: "New Version" }).click();
  let dialog = page.getByRole("dialog", { name: "Register New Version" });
  await dialog.getByLabel("Version String").fill("ui-v1");
  await dialog
    .getByRole("button", { name: /Register Version|Create Version/ })
    .click();
  await expect(dialog).not.toBeVisible();
  const row = page.getByRole("row").filter({ hasText: "vui-v1" });
  const artifact = Buffer.from(
    JSON.stringify({
      format: "featureops.linear.v1",
      task: "binary_classification",
      inputs: [{ name: "value", feature_id: source.id, dtype: "float" }],
      coefficients: [1],
      intercept: 0,
      classes: [0, 1],
    }),
  );
  const uploaded = page.waitForResponse(
    (response) =>
      response.url().endsWith("/artifact") &&
      response.request().method() === "POST",
  );
  await row.getByLabel("Upload artifact vui-v1").setInputFiles({
    name: "model.json",
    mimeType: "application/json",
    buffer: artifact,
  });
  expect((await uploaded).ok()).toBeTruthy();
  await expect(
    row.getByRole("button", { name: "Download Artifact" }),
  ).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await row.getByRole("button", { name: "Download Artifact" }).click();
  expect(readFileSync(await (await downloaded).path())).toEqual(artifact);
  await row.getByRole("button", { name: "Link Features" }).click();
  dialog = page.getByRole("dialog", { name: "Training Features - vui-v1" });
  await expect(
    dialog.getByRole("checkbox", { name: source.name }),
  ).toBeChecked();
  await dialog
    .getByLabel("Training dataset URI")
    .fill("generated://ui-training");
  await dialog.getByRole("button", { name: "Save Training Features" }).click();
  await expect(dialog).not.toBeVisible();
  await row.getByRole("button", { name: "Promote Stage", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Confirm Promotion" })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close modal" })
    .click();
  for (let i = 0; i < 2; i++)
    await post(request, `/models/${model.id}/predict`, {
      entity_key: "asset_entity",
    });
  await page
    .getByRole("button", { name: "Population Stability & Drift (PSI)" })
    .click();
  await page
    .getByLabel("Training samples by linked feature ID (JSON)")
    .fill(JSON.stringify({ [source.id]: [2, 2] }));
  await page.getByLabel("Minimum samples").fill("2");
  await page.getByRole("button", { name: "Capture Training Baseline" }).click();
  await expect(
    page.getByText("Training window:", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Measure Drift" }).click();
  await expect(
    page.getByText("PSI: 0 · measured", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Lineage DAG", exact: true }).click();
  await expect(page.locator("path[data-source]")).not.toHaveCount(0);
});

test("job validation errors, edit, pause and resume", async ({
  page,
  request,
}) => {
  const group = await post(request, "/features/groups", {
    name: "Jobs_" + Date.now(),
  });
  const source = await post(request, "/features", {
    group_id: group.id,
    name: "job_value_" + Date.now(),
    dtype: "float",
    refresh_interval: "hourly",
    source_sql: "SELECT 'job_entity' AS entity_key, 3 AS value",
  });
  await signIn(page);
  await page.goto("/jobs");
  await page.getByRole("button", { name: "Create Schedule" }).click();
  const dialog = page.getByRole("dialog", { name: "Create Scheduled Job" });
  const name = "UI Job " + Date.now();
  await dialog.getByLabel("Job Name").fill(name);
  await dialog.getByLabel("Cron Expression (UTC)").fill("invalid");
  await dialog
    .getByLabel("Payload (JSON)")
    .fill(JSON.stringify({ feature_id: source.id }));
  await dialog.getByRole("button", { name: "Create Job" }).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  await dialog.getByLabel("Cron Expression (UTC)").fill("0 * * * *");
  await dialog.getByRole("button", { name: "Create Job" }).click();
  await expect(dialog).not.toBeVisible();
  const card = page
    .locator("div.rounded-xl")
    .filter({ has: page.getByText(name, { exact: true }) })
    .last();
  await card.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(card.getByText("Paused", { exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(card.getByText("Active", { exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Edit Schedule" }).click();
  const edit = page.getByRole("dialog", { name: "Edit Scheduled Job" });
  await edit.getByLabel("Cron Expression (UTC)").fill("30 * * * *");
  await edit.getByRole("button", { name: "Save Schedule" }).click();
  await expect(card).toContainText("30 * * * *");
});

test("analyst navigation and unavailable service status are honest", async ({
  page,
  request,
}) => {
  const email = `analyst_${Date.now()}@example.test`,
    password = "Analyst-Test-Password!";
  await post(request, "/users", {
    name: "Analyst browser",
    email,
    password,
    roles: ["analyst"],
  });
  await page.route("**/api/ready", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"offline"}',
    }),
  );
  await signIn(page, email, password);
  await expect(page.getByText("Service Unavailable")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Scheduler & Jobs" }),
  ).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Administration" })).toHaveCount(
    0,
  );
  await page.goto("/admin");
  await expect(page.getByRole("alert")).toContainText("do not have permission");
});

test("API key is shown once and revocation removes access", async ({
  page,
  request,
}) => {
  await signIn(page);
  await page.goto("/admin");
  await page.getByRole("button", { name: "Programmatic API Keys" }).click();
  await page
    .getByRole("button", { name: "Generate API Key", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Generate API Key" });
  const name = "UI Key " + Date.now();
  await dialog.locator("input").fill(name);
  await dialog.getByRole("button", { name: /Generate|Create/ }).click();
  await expect(
    dialog.getByText("API Key Generated Successfully"),
  ).toBeVisible();
  const key = await dialog.locator("code").textContent();
  expect(key).toMatch(/^fo_/);
  expect(
    (
      await request.get("/api/features", { headers: { "X-API-Key": key } })
    ).status(),
  ).toBe(200);
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText(key, { exact: true })).toHaveCount(0);
  const row = page.getByRole("row").filter({ hasText: name });
  await row.getByRole("button", { name: "Revoke" }).click();
  await expect(row).toHaveCount(0);
  expect(
    (
      await request.get("/api/features", { headers: { "X-API-Key": key } })
    ).status(),
  ).toBe(401);
});

test("data scientist can register versions while promotion stays restricted", async ({
  page,
  request,
}) => {
  const email = `scientist_${Date.now()}@example.test`,
    password = "Scientist-Test-Password!";
  await post(request, "/users", {
    name: "Scientist browser",
    email,
    password,
    roles: ["data_scientist"],
  });
  const model = await post(request, "/models", {
    name: "Scientist model " + Date.now(),
  });
  await signIn(page, email, password);
  await page.goto(`/models/${model.id}`);
  await page.getByRole("button", { name: "New Version" }).click();
  const dialog = page.getByRole("dialog", { name: "Register New Version" });
  await dialog.getByLabel("Version String").fill("scientist-v1");
  await dialog.getByRole("button", { name: "Register Version" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByRole("row").filter({ hasText: "vscientist-v1" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Promote Stage", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Upload Artifact" }),
  ).toHaveCount(0);
});
