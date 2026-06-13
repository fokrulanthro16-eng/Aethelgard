/**
 * Aethelgard screenshot capture script.
 * Run from the project root: node screenshots/capture.mjs
 *
 * Requires: npx playwright (already installed)
 * Both servers must be running:
 *   - Frontend: http://localhost:3000
 *   - Backend:  http://localhost:8000
 */

import { chromium } from "playwright";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = __dirname; // screenshots/ directory
const BASE = "http://localhost:3000";
const API  = "http://localhost:8000";

async function seedDemo() {
  const res = await fetch(`${API}/demo/setup`, { method: "POST" });
  if (!res.ok) throw new Error(`demo/setup failed: ${res.status}`);
  return res.json();
}

async function main() {
  // Seed demo data before opening the browser
  console.log("Seeding demo user…");
  let demo;
  try {
    demo = await seedDemo();
    console.log(`  demo email: ${demo.demo_email}`);
  } catch (e) {
    console.error("  demo/setup failed:", e.message);
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();

  // ── 1. Landing page ──────────────────────────────────────────────────────────
  console.log("1/6 landing-page.png");
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.screenshot({
    path: path.join(OUT, "landing-page.png"),
    fullPage: true,
  });

  // ── 2. Create vault (register/login view) ────────────────────────────────────
  console.log("2/6 create-vault.png");
  await page.click('button:has-text("Create My Vault")');
  await page.waitForSelector('text=Create New Vault');
  await page.screenshot({
    path: path.join(OUT, "create-vault.png"),
    fullPage: true,
  });

  // ── 3. Dashboard ─────────────────────────────────────────────────────────────
  console.log("3/6 dashboard.png");
  // Fill the "Access Existing Vault" email field and submit
  await page.fill('input[id="login-email"]', demo.demo_email);
  await page.click('button:has-text("Access My Vault")');
  await page.waitForSelector('text=I AM OK');
  // Give vault entries a moment to load
  await page.waitForTimeout(800);
  await page.screenshot({
    path: path.join(OUT, "dashboard.png"),
    fullPage: true,
  });

  // ── 4. Legacy vault entry form ───────────────────────────────────────────────
  console.log("4/6 legacy-vault-entry.png");
  await page.click('button:has-text("Add Entry")');
  await page.waitForSelector('text=Sensitive Information');
  await page.screenshot({
    path: path.join(OUT, "legacy-vault-entry.png"),
    fullPage: true,
  });

  // ── 5. Family Guide card ─────────────────────────────────────────────────────
  console.log("5/6 family-guide.png");
  // Close the vault form first so the card is clearly visible
  await page.click('button:has-text("Cancel")');
  await page.waitForSelector('text=Family Guide');
  // Scroll the Family Guide card into view
  const guideCard = await page.locator('text=Family Guide').first();
  await guideCard.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({
    path: path.join(OUT, "family-guide.png"),
    fullPage: true,
  });

  // ── 6. Architecture page ─────────────────────────────────────────────────────
  console.log("6/6 architecture.png");
  await page.goto(`${BASE}/architecture`, { waitUntil: "networkidle" });
  await page.screenshot({
    path: path.join(OUT, "architecture.png"),
    fullPage: true,
  });

  await browser.close();
  console.log("Done. Screenshots written to screenshots/");
}

main().catch((e) => { console.error(e); process.exit(1); });
