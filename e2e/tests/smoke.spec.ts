import { test, expect } from "@playwright/test";
import path from "path";

test("login, create agent, configure, ingest, build ontology, open chat", async ({
  page,
}) => {
  // Unauthenticated -> redirected to /login
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);

  // Sign in with the hardcoded MVP credentials
  await page.locator('input[autocomplete="username"]').fill("user");
  await page.locator('input[type="password"]').fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();

  // Lands on the Show Projects dashboard (agents live inside a show project).
  await expect(
    page.getByRole("heading", { name: "Show Projects" }),
  ).toBeVisible();

  // Create a show project -> its detail page, which lists Agents
  await page.getByPlaceholder("New show project name").fill("E2E Show");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/projects\/\d+$/);
  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();

  // Create an agent -> lands on its setup page
  await page.getByPlaceholder("New agent name").fill("E2E Concierge");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/agents\/\d+$/);

  // Configure and save
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved")).toBeVisible();

  // Ingest the fixture dataset
  await page
    .locator('input[type="file"]')
    .setInputFiles(path.join(__dirname, "..", "fixtures", "exhibitors.csv"));
  await page.getByRole("button", { name: "Ingest" }).click();
  await expect(page.getByText(/Ingested \d+ records/)).toBeVisible();

  // Build the ontology in Neo4j -> summary counts appear
  await page.getByRole("button", { name: "Build ontology" }).click();
  await expect(page.getByText("Classes")).toBeVisible();
  await expect(page.getByText("Nodes")).toBeVisible();

  // Open the chat workspace -> chat input and live ontology panel present
  await page.getByRole("link", { name: "Open chat" }).click();
  await expect(page.getByPlaceholder("Message the agent...")).toBeVisible();
  await expect(page.getByText("Ontology layer")).toBeVisible();
});
