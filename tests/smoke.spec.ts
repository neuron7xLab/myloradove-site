import { test, expect } from '@playwright/test';

/**
 * Smoke tests — end-to-end flows that must never regress.
 * Fail-closed, no soft assertions.
 */

test.describe('homepage', () => {
  test('loads with no console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    page.on('pageerror', (err) => errors.push(String(err)));

    await page.goto('/');
    await expect(page).toHaveTitle(/Милорадове/);
    await expect(page.locator('h1.hero__title')).toContainText('Милорадове');
    await expect(page.locator('.brand__name')).toBeVisible();
    await expect(page.locator('#nav .flag')).toBeVisible();

    expect(errors, `console errors: ${errors.join(' | ')}`).toEqual([]);
  });

  test('all in-page anchors resolve to sections', async ({ page }) => {
    await page.goto('/');
    const anchors = await page.locator('nav.nav__menu a[href^="#"]').all();
    for (const a of anchors) {
      const href = (await a.getAttribute('href'))!;
      const id = href.slice(1);
      await expect(page.locator(`#${id}`), `missing section #${id}`).toHaveCount(1);
    }
  });
});

test.describe('gallery lightbox', () => {
  test('opens on tile click and closes on Escape', async ({ page }) => {
    await page.goto('/');
    // Scroll gallery into view so content-visibility renders tiles.
    await page.locator('#gallery').scrollIntoViewIfNeeded();
    const firstTile = page.locator('.tile a').first();
    await firstTile.click();
    const dialog = page.locator('dialog.lightbox');
    await expect(dialog).toHaveAttribute('open', '');
    await expect(dialog.locator('img')).toBeVisible();
    // ESC closes
    await page.keyboard.press('Escape');
    await expect(dialog).not.toHaveAttribute('open', '');
  });

  test('close button restores focus to trigger', async ({ page }) => {
    await page.goto('/');
    await page.locator('#gallery').scrollIntoViewIfNeeded();
    const firstTile = page.locator('.tile a').first();
    await firstTile.click();
    await page.locator('.lightbox__close').click();
    await expect(firstTile).toBeFocused();
  });
});

test.describe('404 page', () => {
  test('renders with link back to home', async ({ page }) => {
    const resp = await page.goto('/404.html');
    expect(resp?.status()).toBe(200);   // served as file; real 404 = CF routing
    await expect(page.locator('h1')).toContainText('404');
    await expect(page.locator('a[href="/"]')).toBeVisible();
  });
});

test.describe('mobile menu', () => {
  test.skip(({ browserName }) => browserName !== 'chromium' || process.env.PROJECT !== 'mobile',
            'mobile-only');

  test('toggle opens drawer and Escape closes it', async ({ page }) => {
    await page.goto('/');
    const toggle = page.locator('.nav__toggle');
    await toggle.click();
    await expect(page.locator('#nav-menu')).toHaveClass(/is-open/);
    await page.keyboard.press('Escape');
    await expect(page.locator('#nav-menu')).not.toHaveClass(/is-open/);
  });
});

test.describe('metadata', () => {
  test('critical meta tags present', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', /^https:\/\//);
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', /^https:\/\//);
    await expect(page.locator('script[type="application/ld+json"]')).toHaveCount(1);
  });
});
