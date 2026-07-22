# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: exhaustive_ui.spec.ts >> Mobile & Low-Bandwidth Resilience (Sahel Optimized) >> Should verify Service Worker uses Network-First strategy for documents to prevent stale cache
- Location: e2e/exhaustive_ui.spec.ts:206:3

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: page.evaluate: Test timeout of 45000ms exceeded.
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e5]:
    - generic [ref=e7]:
      - generic [ref=e8]: StreamPulse
      - generic [ref=e9]: Real-Time Data Intelligence
    - navigation [ref=e10]:
      - link "Live Operations" [ref=e11] [cursor=pointer]:
        - /url: /
        - img [ref=e13]
        - text: Live Operations
      - link "Events" [ref=e19] [cursor=pointer]:
        - /url: /events
        - img [ref=e20]
        - text: Events
      - link "Ingest Playground" [ref=e23] [cursor=pointer]:
        - /url: /playground
        - img [ref=e24]
        - text: Ingest Playground
      - link "Sources" [ref=e27] [cursor=pointer]:
        - /url: /sources
        - img [ref=e28]
        - text: Sources
      - link "Destinations" [ref=e34] [cursor=pointer]:
        - /url: /destinations
        - img [ref=e35]
        - text: Destinations
      - link "Analytics" [ref=e39] [cursor=pointer]:
        - /url: /analytics
        - img [ref=e40]
        - text: Analytics
      - link "Alerts" [ref=e42] [cursor=pointer]:
        - /url: /alerts
        - img [ref=e43]
        - text: Alerts
      - link "Automation" [ref=e48] [cursor=pointer]:
        - /url: /automation
        - img [ref=e49]
        - text: Automation
      - link "Classifier" [ref=e53] [cursor=pointer]:
        - /url: /classifier
        - img [ref=e54]
        - text: Classifier
      - link "API Docs" [ref=e59] [cursor=pointer]:
        - /url: /api-docs
        - img [ref=e60]
        - text: API Docs
      - link "User Guide" [ref=e64] [cursor=pointer]:
        - /url: /user-guide
        - img [ref=e65]
        - text: User Guide
    - generic [ref=e67]: Backend online
  - main [ref=e70]:
    - generic [ref=e72]:
      - generic [ref=e73]:
        - generic [ref=e74]:
          - heading "Live operations" [level=1] [ref=e75]
          - paragraph [ref=e76]: Every record ingested anywhere in the platform streams here in real time, already classified.
        - generic [ref=e78]:
          - generic [ref=e79]:
            - img [ref=e80]
            - text: live · WebSocket
          - button "Pause" [ref=e86] [cursor=pointer]:
            - img [ref=e87]
            - text: Pause
      - generic [ref=e90]:
        - generic [ref=e91]:
          - generic [ref=e92]:
            - generic [ref=e93]: Records / min
            - img [ref=e94]
          - generic [ref=e100]: "0"
          - generic [ref=e102]: this session
        - generic [ref=e103]:
          - generic [ref=e105]: Session records
          - generic [ref=e106]: "0"
          - generic [ref=e108]: last 200 kept
        - generic [ref=e109]:
          - generic [ref=e111]: Connected clients
          - generic [ref=e112]: "1"
          - generic [ref=e114]: from /pipeline/status
      - generic [ref=e115]:
        - generic [ref=e116]:
          - generic [ref=e118]: Record feed
          - generic [ref=e120]:
            - img [ref=e121]
            - generic [ref=e127]: Listening — no records yet
            - generic [ref=e128]: Send something from the Ingest Playground (even from another tab) and watch it arrive here, classified.
            - link "Open Playground" [ref=e130] [cursor=pointer]:
              - /url: /playground
              - generic [ref=e131]:
                - img [ref=e132]
                - text: Open Playground
                - img [ref=e135]
        - generic [ref=e138]:
          - generic [ref=e139]:
            - generic [ref=e140]: Domain distribution
            - generic [ref=e142]: session
          - generic [ref=e144]:
            - img [ref=e145]
            - generic [ref=e148]: No data yet
```

# Test source

```ts
  119 |     // Mock navigation to route containing Analytics
  120 |     await page.goto(BASE_URL + '/streampulse/analytics');
  121 |     await page.waitForLoadState('domcontentloaded');
  122 |     const rootHtml = await page.locator('#root').innerHTML();
  123 |     expect(rootHtml.length).toBeGreaterThan(0);
  124 |   });
  125 | 
  126 |   test('Should render and interact with Playground (pages/Playground.tsx)', async ({ page }) => {
  127 |     // Mock navigation to route containing Playground
  128 |     await page.goto(BASE_URL + '/streampulse/playground');
  129 |     await page.waitForLoadState('domcontentloaded');
  130 |     const rootHtml = await page.locator('#root').innerHTML();
  131 |     expect(rootHtml.length).toBeGreaterThan(0);
  132 |   });
  133 | 
  134 |   test('Should render and interact with ApiDocs (pages/ApiDocs.tsx)', async ({ page }) => {
  135 |     // Mock navigation to route containing ApiDocs
  136 |     await page.waitForLoadState('domcontentloaded');
  137 |     const rootHtml = await page.locator('#root').innerHTML();
  138 |     expect(rootHtml.length).toBeGreaterThan(0);
  139 |   });
  140 | 
  141 |   test('Should render and interact with Events (pages/Events.tsx)', async ({ page }) => {
  142 |     // Mock navigation to route containing Events
  143 |     await page.goto(BASE_URL + '/streampulse/events');
  144 |     await page.waitForLoadState('domcontentloaded');
  145 |     const rootHtml = await page.locator('#root').innerHTML();
  146 |     expect(rootHtml.length).toBeGreaterThan(0);
  147 |   });
  148 | 
  149 | });
  150 | 
  151 | test.describe("2026 UI/UX Standards Validation", () => {
  152 |   test("Should verify haptic feedback scale animation on buttons", async ({ page }) => {
  153 |     await page.goto(BASE_URL);
  154 |     const btn = page.locator('button').first();
  155 |     if (await btn.isVisible()) {
  156 |       // Hover the button and simulate mouse down to trigger :active
  157 |       const box = await btn.boundingBox();
  158 |       if (box) {
  159 |         await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  160 |         await page.mouse.down();
  161 |         // The scale should drop to 0.96 due to the new CSS rules
  162 |         const transform = await btn.evaluate((el) => window.getComputedStyle(el).transform);
  163 |         // Note: transform is usually a matrix. We check that it's not 'none'.
  164 |         expect(transform).not.toBe('none');
  165 |         await page.mouse.up();
  166 |       }
  167 |     }
  168 |   });
  169 | 
  170 |   test("Should verify accessibility focus-visible rings", async ({ page }) => {
  171 |     await page.goto(BASE_URL);
  172 |     const input = page.locator('input').first();
  173 |     if (await input.isVisible()) {
  174 |       await input.focus();
  175 |       const outline = await input.evaluate((el) => window.getComputedStyle(el).outline);
  176 |       // We expect the focus-visible to trigger either a box-shadow or an outline
  177 |       expect(outline).not.toBe('none');
  178 |     }
  179 |   });
  180 | });
  181 | 
  182 | test.describe("Mobile & Low-Bandwidth Resilience (Sahel Optimized)", () => {
  183 |   test("Should verify strict mobile viewport configuration", async ({ page }) => {
  184 |     await page.goto(BASE_URL);
  185 |     const viewport = await page.locator('meta[name="viewport"]').getAttribute('content');
  186 |     expect(viewport).toContain('width=device-width');
  187 |     expect(viewport).toContain('shrink-to-fit=no');
  188 |     expect(viewport).toContain('maximum-scale=5.0');
  189 |   });
  190 | 
  191 |   test("Should verify offline Service Worker registration", async ({ page }) => {
  192 |     await page.goto(BASE_URL);
  193 |     // Wait for window.onload so SW registers
  194 |     await page.waitForLoadState('domcontentloaded');
  195 |     
  196 |     // Evaluate if a service worker is registered in the navigator
  197 |     const isSwRegistered = await page.evaluate(async () => {
  198 |       if (!('serviceWorker' in navigator)) return false;
  199 |       const registrations = await navigator.serviceWorker.getRegistrations();
  200 |       return registrations.length > 0;
  201 |     });
  202 |     
  203 |     expect(isSwRegistered).toBe(true);
  204 |   });
  205 | 
  206 |   test("Should verify Service Worker uses Network-First strategy for documents to prevent stale cache", async ({ page }) => {
  207 |     // Intercept network requests to verify the SW doesn't block the document fetch
  208 |     let documentFetchedFromNetwork = false;
  209 |     page.on('request', request => {
  210 |       if (request.resourceType() === 'document' && request.url() === '/' + '/') {
  211 |         documentFetchedFromNetwork = true;
  212 |       }
  213 |     });
  214 |     
  215 |     await page.goto(BASE_URL);
  216 |     await page.waitForLoadState('domcontentloaded');
  217 |     
  218 |     // Evaluate the active Service Worker state to ensure it skips waiting
> 219 |     const swState = await page.evaluate(async () => {
      |                                ^ Error: page.evaluate: Test timeout of 45000ms exceeded.
  220 |       const reg = await navigator.serviceWorker.ready;
  221 |       return reg.active ? reg.active.state : 'none';
  222 |     });
  223 |     
  224 |     expect(['activated', 'activating']).toContain(swState);
  225 |   });
  226 | });
  227 | 
```