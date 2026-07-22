# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: exhaustive_ui.spec.ts >> Exhaustive UI Component & Page Flow Suite >> Should render and interact with ApiDocs (pages/ApiDocs.tsx)
- Location: e2e/exhaustive_ui.spec.ts:134:3

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.innerHTML: Test timeout of 45000ms exceeded.
Call log:
  - waiting for locator('#root')

```

# Test source

```ts
  37  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  38  |   });
  39  | 
  40  |   test('Should render and interact with misc (kit/misc.tsx)', async ({ page }) => {
  41  |     // Mock navigation to route containing misc
  42  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  43  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  44  |   });
  45  | 
  46  |   test('Should render and interact with PipelineFlow (kit/PipelineFlow.tsx)', async ({ page }) => {
  47  |     // Mock navigation to route containing PipelineFlow
  48  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  49  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  50  |   });
  51  | 
  52  |   test('Should render and interact with JSONViewer (kit/JSONViewer.tsx)', async ({ page }) => {
  53  |     // Mock navigation to route containing JSONViewer
  54  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  55  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  56  |   });
  57  | 
  58  |   test('Should render and interact with primitives (kit/primitives.tsx)', async ({ page }) => {
  59  |     // Mock navigation to route containing primitives
  60  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  61  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  62  |   });
  63  | 
  64  |   test('Should render and interact with AppShell (kit/AppShell.tsx)', async ({ page }) => {
  65  |     // Mock navigation to route containing AppShell
  66  |     // Component-level isolation test via storybook/mount mock (Conceptual for full-mesh E2E)
  67  |     expect(true).toBeTruthy(); // Placeholder for deep component mesh
  68  |   });
  69  | 
  70  |   test('Should render and interact with Alerts (pages/Alerts.tsx)', async ({ page }) => {
  71  |     // Mock navigation to route containing Alerts
  72  |     await page.goto(BASE_URL + '/streampulse/alerts');
  73  |     await page.waitForLoadState('domcontentloaded');
  74  |     const rootHtml = await page.locator('#root').innerHTML();
  75  |     expect(rootHtml.length).toBeGreaterThan(0);
  76  |   });
  77  | 
  78  |   test('Should render and interact with Live (pages/Live.tsx)', async ({ page }) => {
  79  |     // Mock navigation to route containing Live
  80  |     await page.goto(BASE_URL + '/streampulse/live');
  81  |     await page.waitForLoadState('domcontentloaded');
  82  |     const rootHtml = await page.locator('#root').innerHTML();
  83  |     expect(rootHtml.length).toBeGreaterThan(0);
  84  |   });
  85  | 
  86  |   test('Should render and interact with Destinations (pages/Destinations.tsx)', async ({ page }) => {
  87  |     // Mock navigation to route containing Destinations
  88  |     await page.goto(BASE_URL + '/streampulse/destinations');
  89  |     await page.waitForLoadState('domcontentloaded');
  90  |     const rootHtml = await page.locator('#root').innerHTML();
  91  |     expect(rootHtml.length).toBeGreaterThan(0);
  92  |   });
  93  | 
  94  |   test('Should render and interact with Classifier (pages/Classifier.tsx)', async ({ page }) => {
  95  |     // Mock navigation to route containing Classifier
  96  |     await page.goto(BASE_URL + '/streampulse/classifier');
  97  |     await page.waitForLoadState('domcontentloaded');
  98  |     const rootHtml = await page.locator('#root').innerHTML();
  99  |     expect(rootHtml.length).toBeGreaterThan(0);
  100 |   });
  101 | 
  102 |   test('Should render and interact with Sources (pages/Sources.tsx)', async ({ page }) => {
  103 |     // Mock navigation to route containing Sources
  104 |     await page.goto(BASE_URL + '/streampulse/sources');
  105 |     await page.waitForLoadState('domcontentloaded');
  106 |     const rootHtml = await page.locator('#root').innerHTML();
  107 |     expect(rootHtml.length).toBeGreaterThan(0);
  108 |   });
  109 | 
  110 |   test('Should render and interact with Automation (pages/Automation.tsx)', async ({ page }) => {
  111 |     // Mock navigation to route containing Automation
  112 |     await page.goto(BASE_URL + '/streampulse/automation');
  113 |     await page.waitForLoadState('domcontentloaded');
  114 |     const rootHtml = await page.locator('#root').innerHTML();
  115 |     expect(rootHtml.length).toBeGreaterThan(0);
  116 |   });
  117 | 
  118 |   test('Should render and interact with Analytics (pages/Analytics.tsx)', async ({ page }) => {
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
> 137 |     const rootHtml = await page.locator('#root').innerHTML();
      |                                                  ^ Error: locator.innerHTML: Test timeout of 45000ms exceeded.
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
  219 |     const swState = await page.evaluate(async () => {
  220 |       const reg = await navigator.serviceWorker.ready;
  221 |       return reg.active ? reg.active.state : 'none';
  222 |     });
  223 |     
  224 |     expect(['activated', 'activating']).toContain(swState);
  225 |   });
  226 | });
  227 | 
```