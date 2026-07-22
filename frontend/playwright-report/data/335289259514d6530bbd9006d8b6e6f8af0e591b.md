# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: streampulse_telemetry.spec.ts >> Phase 6 — StreamPulse Edge Cases >> API offline: UI does not white-screen
- Location: e2e/streampulse_telemetry.spec.ts:172:3

# Error details

```
Error: page.goto: net::ERR_FAILED at https://streampulse.ysiddo-ai-projects.app/
Call log:
  - navigating to "https://streampulse.ysiddo-ai-projects.app/", waiting until "load"

```

# Test source

```ts
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
  142 |       }
  143 |     }
  144 |   });
  145 | 
  146 |   test('POST /api/events with malformed payload returns 400 not 500', async ({ request }) => {
  147 |     const token = await getAuthToken(request);
  148 |     const resp = await request.post(`${API_URL}/api/events`, {
  149 |       headers: {
  150 |         ...(token ? { Authorization: `Bearer ${token}` } : {}),
  151 |         'Content-Type': 'application/json',
  152 |       },
  153 |       data: '{"invalid_json": }', // malformed
  154 |     }).catch(() => null);
  155 |     if (resp) expect(resp.status()).not.toBe(500);
  156 |   });
  157 | });
  158 | 
  159 | // ─────────────────────────────────────────────────────────────────────────────
  160 | // Phase 6 — StreamPulse Edge Cases
  161 | // ─────────────────────────────────────────────────────────────────────────────
  162 | test.describe('Phase 6 — StreamPulse Edge Cases', () => {
  163 | 
  164 |   test('Events page handles empty event list gracefully', async ({ page }) => {
  165 |     await page.goto(`${BASE_URL}/events`);
  166 |     await page.waitForLoadState('domcontentloaded');
  167 |     await assertNoReactCrash(page);
  168 |     const body = await page.locator('body').textContent();
  169 |     expect(body!.length).toBeGreaterThan(10); // Not a blank page
  170 |   });
  171 | 
  172 |   test('API offline: UI does not white-screen', async ({ page }) => {
  173 |     // Block all API requests
  174 |     await page.route(`${API_URL}/**`, route => route.abort());
> 175 |     await page.goto(`${BASE_URL}/`);
      |                ^ Error: page.goto: net::ERR_FAILED at https://streampulse.ysiddo-ai-projects.app/
  176 |     await page.waitForLoadState('domcontentloaded');
  177 |     await assertNoReactCrash(page);
  178 |     const body = await page.locator('body').textContent();
  179 |     expect(body!.length).toBeGreaterThan(10);
  180 |   });
  181 | });
  182 | 
  183 | // ─────────────────────────────────────────────────────────────────────────────
  184 | // Phase 5.2 — StreamPulse Mocked Feature Test
  185 | // ─────────────────────────────────────────────────────────────────────────────
  186 | test.describe('Phase 5.2 — StreamPulse Mocked Features', () => {
  187 | 
  188 |   test('Mock n8n Webhook / telemetry event insertion', async ({ page }) => {
  189 |     // Intercept to return a mock webhook URL
  190 |     await page.route('**/api/sources', async route => {
  191 |       const json = [{ id: 'src-1', name: 'n8n Integration', type: 'webhook', url: 'https://streampulse.app/hook/mock' }];
  192 |       await route.fulfill({ json, status: 200, contentType: 'application/json' });
  193 |     });
  194 | 
  195 |     await page.goto();
  196 |     await page.waitForLoadState('domcontentloaded');
  197 | 
  198 |     // Simulate clicking the source
  199 |     const sourceEl = page.locator('text=/n8n/i').first();
  200 |     if (await sourceEl.isVisible({ timeout: 5000 }).catch(() => false)) {
  201 |       await sourceEl.click();
  202 |       await page.waitForTimeout(1000);
  203 |       await assertNoReactCrash(page);
  204 |     }
  205 |   });
  206 | });
  207 | 
  208 | // ─────────────────────────────────────────────────────────────────────────────
  209 | // Phase 5.2 — StreamPulse Mocked Feature Test
  210 | 
  211 | // ─────────────────────────────────────────────────────────────────────────────
  212 | // Phase 5.3 — StreamPulse Deep Interactivity & Mocked Features
  213 | // ─────────────────────────────────────────────────────────────────────────────
  214 | test.describe('Phase 5.3 — Deep Interactivity', () => {
  215 | 
  216 |   test('Automation rule creation and destination mapping mock', async ({ page }) => {
  217 |     
  218 | 
  219 |     await page.goto(`${BASE_URL}/automation`);
  220 |     await page.waitForLoadState('domcontentloaded');
  221 | 
  222 |     // Look for create rule button
  223 |     const createBtn = page.locator('button:has-text("Create"), button:has-text("New Rule")').first();
  224 |     if (await createBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
  225 |       await createBtn.click();
  226 |       await page.waitForTimeout(1000);
  227 |       
  228 |       const saveBtn = page.locator('button:has-text("Save")').first();
  229 |       if (await saveBtn.isVisible().catch(() => false)) {
  230 |         await saveBtn.click();
  231 |       }
  232 |       await assertNoReactCrash(page);
  233 |     }
  234 |   });
  235 | 
  236 |   test('Real-time alert UI popups mock', async ({ page }) => {
  237 |     // Navigate to alerts
  238 |     await page.goto(`${BASE_URL}/alerts`);
  239 |     await page.waitForLoadState('domcontentloaded');
  240 | 
  241 |     // Inject a high-severity alert via window variable or by manipulating DOM for testing
  242 |     // Or intercept the alerts polling API
  243 |     
  244 |     
  245 |     // Reload to trigger the intercepted API
  246 |     await page.reload();
  247 |     await page.waitForLoadState('domcontentloaded');
  248 |     
  249 |     // Assert alert toast/row appears
  250 |     const alertEl = page.locator('.alert, .critical, text=/critical|CPU/i').first();
  251 |     if (await alertEl.isVisible({ timeout: 5000 }).catch(() => false)) {
  252 |       await expect(alertEl).toBeVisible();
  253 |     }
  254 |   });
  255 | });
  256 | 
```