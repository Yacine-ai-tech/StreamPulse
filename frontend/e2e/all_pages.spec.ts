import { test, expect } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || '';

const ROUTES = ['/', '/events', '/live', '/analytics', '/sources', '/destinations', '/automation', '/classifier', '/alerts', '/playground'];

test.describe('StreamPulse All Pages E2E Suite', () => {

  test.beforeEach(async ({ page }) => {
    await page.route('**/*', async route => {
      const req = route.request();
      const url = req.url();
      if ((req.resourceType() === 'fetch' || req.resourceType() === 'xhr') && url.includes('vercel.app')) {
        let backendUrl = process.env.TEST_BACKEND_URL || 'http://localhost:8004';
        if (url.includes('docintel-ui')) backendUrl = process.env.TEST_DOCINTEL_URL || 'http://localhost:8001';
        else if (url.includes('agentkit-ui')) backendUrl = process.env.TEST_AGENTKIT_URL || 'http://localhost:8002';
        else if (url.includes('rageval-ui')) backendUrl = process.env.TEST_RAGEVAL_URL || 'http://localhost:8003';
        else if (url.includes('voiceflow-ui')) backendUrl = process.env.TEST_VOICEFLOW_URL || 'http://localhost:8005';
        else if (url.includes('streampulse-ui')) backendUrl = process.env.TEST_STREAMPULSE_URL || 'http://localhost:8004';
        
        const pathPart = new URL(url).pathname;
        const newUrl = backendUrl.replace(/\/$/, '') + pathPart;
        await route.continue({ url: newUrl });
      } else {
        await route.continue();
      }
    });
  });

  for (const route of ROUTES) {
    test(`Should successfully load ${route} page without crashing`, async ({ page }) => {
      await page.goto(route);
      // Wait for DOM to load
      await page.waitForLoadState('domcontentloaded');

      // Ensure the blank screen of death did not occur
      const rootHtml = await page.locator('#root').innerHTML();
      expect(rootHtml.length).toBeGreaterThan(0);

      // Ensure no generic "An unexpected error occurred" overlay
      const errorOverlay = page.locator('text=unexpected error');
      await expect(errorOverlay).not.toBeVisible();
    });
  }
});
