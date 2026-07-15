import { test, expect } from '@playwright/test';

const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:5173';

test.describe('Phase 4: StreamPulse Telemetry & High-Velocity Dashboards', () => {

  test('Slice 4.2: Live Event Terminal & Automation rendering', async ({ page }) => {
    // 1. Check Live Terminal Page
    await page.goto(`${BASE_URL}/live`);
    await expect(page.locator('text=/Live/i').first()).toBeVisible();
    
    // The Live terminal should have a fast-scrolling list or a JSON block
    const terminalOrList = page.locator('.terminal, pre, [role="log"], .event-list');
    await expect(terminalOrList.first()).toBeVisible({ timeout: 10000 });

    // 2. Check Automation config forms
    await page.goto(`${BASE_URL}/automation`);
    await expect(page.locator('text=/Automation/i').first()).toBeVisible();
    
    // Webhook or rule forms should be visible
    await expect(page.locator('form, input, button').first()).toBeVisible();
  });

  test('Slice 4.2: Playground & Synthetic Events', async ({ page }) => {
    await page.goto(`${BASE_URL}/playground`);
    await expect(page.locator('text=/Playground/i').first()).toBeVisible();

    // Check if there is a way to fire events
    const fireEventBtn = page.locator('button', { hasText: /Fire|Send|Emit/i });
    if (await fireEventBtn.count() > 0) {
      await fireEventBtn.first().click();
      
      // Look for a success toast or log entry
      await expect(page.locator('.toast, .success, [role="alert"]')).toBeVisible({ timeout: 5000 });
    }
  });

  test('Slice 4.2: Data Topology & Classifier Rendering', async ({ page }) => {
    const topoPages = [
      { path: '/analytics', title: 'Analytics' },
      { path: '/alerts', title: 'Alerts' },
      { path: '/classifier', title: 'Classifier' },
      { path: '/destinations', title: 'Destinations' },
      { path: '/events', title: 'Events' },
      { path: '/sources', title: 'Sources' }
    ];

    for (const tp of topoPages) {
      await test.step(`Verify ${tp.title} Dashboard Rendering`, async () => {
        await page.goto(`${BASE_URL}${tp.path}`);
        await expect(page.locator('body')).toBeVisible();
        await expect(page.locator(`text=/${tp.title}/i`).first()).toBeVisible({ timeout: 5000 });
        
        // Ensure no fatal React crashes
        await expect(page.locator('text=/An unexpected error occurred/i')).toHaveCount(0);
      });
    }
  });

});
