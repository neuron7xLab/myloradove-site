import { test, expect } from '@playwright/test';

/**
 * Visual regression — intentionally sparse.
 * Four snapshots total: hero (desktop+mobile), gallery open, contact.
 * Keep this minimal — every snapshot is a future maintenance debt.
 */

test('hero fold', async ({ page }) => {
  await page.goto('/');
  // Wait for fonts and hero image.
  await page.evaluate(() => (document as any).fonts.ready);
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveScreenshot('hero.png', {
    fullPage: false,
    maxDiffPixelRatio: 0.02,
  });
});

test('contact section', async ({ page }) => {
  await page.goto('/#contact');
  await page.locator('#contact').scrollIntoViewIfNeeded();
  await page.evaluate(() => (document as any).fonts.ready);
  await page.waitForTimeout(200);
  await expect(page.locator('#contact')).toHaveScreenshot('contact.png', {
    maxDiffPixelRatio: 0.02,
  });
});
