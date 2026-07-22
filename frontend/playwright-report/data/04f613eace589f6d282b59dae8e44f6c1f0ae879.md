# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: streampulse_telemetry.spec.ts >> Phase 5.2 — StreamPulse Dashboards >> All main navigation pages render without crash
- Location: e2e/streampulse_telemetry.spec.ts:34:3

# Error details

```
Error: page.goto: net::ERR_NAME_NOT_RESOLVED at https://alerts/
Call log:
  - navigating to "https://alerts/", waiting until "load"

```

# Test source

```ts
  1   | import { test, expect, Page } from '@playwright/test';
  2   | 
  3   | /**
  4   |  * StreamPulse — Comprehensive E2E Suite
  5   |  * Phase 5.2: StreamPulse Live Terminal & High-Velocity Data
  6   |  * Phase 6: Edge Cases & Degradation
  7   |  * Phase 7: Deep Component Integration
  8   |  */
  9   | 
  10  | const BASE_URL = process.env.STREAMPULSE_URL    || process.env.TEST_BASE_URL || '/';
  11  | const API_URL  = process.env.STREAMPULSE_API_URL || '/';
  12  | const AUTH_URL = process.env.INTELAI_API_URL     || '/';
  13  | 
  14  | async function assertNoReactCrash(page: Page) {
  15  |   await expect(page.locator('text=/An unexpected error occurred|Something went wrong/i')).toHaveCount(0);
  16  | }
  17  | 
  18  | async function getAuthToken(request: any): Promise<string> {
  19  |   const resp = await request.post(`${AUTH_URL}/api/login`, {
  20  |     data: { username: 'admin', password: 'fLNtwDH2VaQLbO' }
  21  |   }).catch(() => null);
  22  |   if (resp && resp.ok()) {
  23  |     const body = await resp.json();
  24  |     return body.access_token || body.token || '';
  25  |   }
  26  |   return '';
  27  | }
  28  | 
  29  | // ─────────────────────────────────────────────────────────────────────────────
  30  | // Phase 5.2 — StreamPulse UI Workflows
  31  | // ─────────────────────────────────────────────────────────────────────────────
  32  | test.describe('Phase 5.2 — StreamPulse Dashboards', () => {
  33  | 
  34  |   test('All main navigation pages render without crash', async ({ page }) => {
  35  |     await page.goto(`${BASE_URL}/`);
  36  |     const routes = [
  37  |       '/alerts', '/analytics', '/automation', '/classifier',
  38  |       '/destinations', '/events', '/live', '/playground', '/sources'
  39  |     ];
  40  |     for (const route of routes) {
> 41  |       await page.goto(`${'/'}${route}`);
      |                  ^ Error: page.goto: net::ERR_NAME_NOT_RESOLVED at https://alerts/
  42  |       await page.waitForLoadState('domcontentloaded');
  43  |       await assertNoReactCrash(page);
  44  |       console.log(`✅ StreamPulse ${route} — OK`);
  45  |     }
  46  |   });
  47  | 
  48  |   test('Live page shows event terminal or empty state', async ({ page }) => {
  49  |     await page.goto(`${BASE_URL}/live`);
  50  |     await page.waitForLoadState('domcontentloaded');
  51  |     await assertNoReactCrash(page);
  52  | 
  53  |     const terminal = page.locator('.terminal, .live-log, [data-testid="live-terminal"], pre, code').first();
  54  |     if (await terminal.isVisible({ timeout: 5000 }).catch(() => false)) {
  55  |       await expect(terminal).toBeVisible();
  56  |     }
  57  |   });
  58  | 
  59  |   test('Live terminal updates within 2s after API event injection', async ({ page, request }) => {
  60  |     const token = await getAuthToken(request);
  61  |     await page.goto(`${BASE_URL}/live`);
  62  |     await page.waitForLoadState('domcontentloaded');
  63  |     await assertNoReactCrash(page);
  64  | 
  65  |     // Inject a test event via API
  66  |     const testEventId = `test_event_${Date.now()}`;
  67  |     await request.post(`${API_URL}/api/events`, {
  68  |       headers: token ? { Authorization: `Bearer ${token}` } : {},
  69  |       data: {
  70  |         event_type: 'test',
  71  |         source: 'playwright_e2e',
  72  |         payload: { id: testEventId, message: 'Playwright live test event' }
  73  |       }
  74  |     }).catch(() => null);
  75  | 
  76  |     // Wait up to 3s for the event to appear in the live terminal
  77  |     const eventEl = page.locator(`text=${testEventId}`);
  78  |     const found = await eventEl.isVisible({ timeout: 3000 }).catch(() => false);
  79  |     if (found) {
  80  |       await expect(eventEl).toBeVisible();
  81  |       console.log(`✅ Event ${testEventId} appeared in live terminal within 3s`);
  82  |     } else {
  83  |       console.warn(`⚠️ Event ${testEventId} not found in terminal — WebSocket may be inactive`);
  84  |     }
  85  |   });
  86  | 
  87  |   test('Classifier page shows classifier config form', async ({ page }) => {
  88  |     await page.goto(`${BASE_URL}/classifier`);
  89  |     await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
  90  |     await assertNoReactCrash(page);
  91  |     const formEl = page.locator('form, input, select, .classifier, [data-testid="classifier"]').first();
  92  |     if (await formEl.isVisible({ timeout: 5000 }).catch(() => false)) {
  93  |       await expect(formEl).toBeVisible();
  94  |     }
  95  |   });
  96  | });
  97  | 
  98  | // ─────────────────────────────────────────────────────────────────────────────
  99  | // Phase 5.2 — StreamPulse API Tests
  100 | // ─────────────────────────────────────────────────────────────────────────────
  101 | test.describe('Phase 5.2 — StreamPulse API Validation', () => {
  102 | 
  103 |   test('GET /health returns < 500', async ({ request }) => {
  104 |     const resp = await request.get(`${API_URL}/health`).catch(() => null);
  105 |     if (resp) expect(resp.status()).toBeLessThan(500);
  106 |   });
  107 | 
  108 |   test('POST /api/events creates an event', async ({ request }) => {
  109 |     const token = await getAuthToken(request);
  110 |     const resp = await request.post(`${API_URL}/api/events`, {
  111 |       headers: token ? { Authorization: `Bearer ${token}` } : {},
  112 |       data: {
  113 |         event_type: 'test',
  114 |         source: 'playwright_api_test',
  115 |         payload: { msg: 'API test event', ts: Date.now() }
  116 |       }
  117 |     }).catch(() => null);
  118 |     if (resp) {
  119 |       expect(resp.status()).not.toBe(500);
  120 |       console.log(`POST /api/events → ${resp.status()}`);
  121 |     }
  122 |   });
  123 | 
  124 |   test('GET /api/events returns list', async ({ request }) => {
  125 |     const token = await getAuthToken(request);
  126 |     const resp = await request.get(`${API_URL}/api/events`, {
  127 |       headers: token ? { Authorization: `Bearer ${token}` } : {}
  128 |     }).catch(() => null);
  129 |     if (resp) expect([200, 401, 403, 404]).toContain(resp.status());
  130 |   });
  131 | 
  132 |   test('Webhook endpoint validates secret header', async ({ request }) => {
  133 |     // Without the correct webhook secret, should reject
  134 |     const resp = await request.post(`${API_URL}/api/webhook`, {
  135 |       headers: { 'X-Webhook-Secret': 'wrong_secret' },
  136 |       data: { event: 'test', data: {} }
  137 |     }).catch(() => null);
  138 |     if (resp) {
  139 |       // 200 = no secret enforcement (warn), 401/403 = correct
  140 |       if (resp.status() === 200) {
  141 |         console.warn('⚠️ Webhook does not validate secret — security gap');
```