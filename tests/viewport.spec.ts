import { test, expect } from '@playwright/test';

/**
 * WSE §22 viewport sweep — no body horizontal overflow at any width
 * from 320 px (smallest-supported phone) to 1920 px (HD desktop).
 *
 * Failure here means a fixed-width element broke its inline budget,
 * a long word/URL escaped its container, or an inline image lacked
 * the responsive contract. WCAG §1.4.10 Reflow gate.
 *
 * Single project (desktop chromium); the resize sweep covers mobile
 * widths inside the same browser process — running webkit + chromium
 * × 9 widths would needlessly multiply CI runtime.
 */
const widths = [320, 360, 390, 430, 768, 1024, 1280, 1440, 1920] as const;

for (const width of widths) {
  test(`no body horizontal overflow @ ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/');
    await page.evaluate(() => document.fonts.ready);
    const overflow = await page.evaluate(() => ({
      docScroll: document.documentElement.scrollWidth,
      docClient: document.documentElement.clientWidth,
      bodyScroll: document.body.scrollWidth,
      bodyClient: document.body.clientWidth,
    }));
    expect.soft(
      overflow.docScroll,
      `<html> overflow at ${width}px: ${JSON.stringify(overflow)}`,
    ).toBeLessThanOrEqual(overflow.docClient + 1);
    expect(
      overflow.bodyScroll,
      `<body> overflow at ${width}px: ${JSON.stringify(overflow)}`,
    ).toBeLessThanOrEqual(overflow.bodyClient + 1);
  });
}

test('hero section never produces horizontal scroll on the smallest phone', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto('/');
  await page.evaluate(() => document.fonts.ready);
  const heroOverflow = await page.evaluate(() => {
    const hero = document.querySelector('.hero') as HTMLElement | null;
    if (!hero) return { ok: false, reason: 'no .hero element' };
    return {
      ok: hero.scrollWidth <= hero.clientWidth + 1,
      sw: hero.scrollWidth,
      cw: hero.clientWidth,
    };
  });
  expect(heroOverflow.ok, JSON.stringify(heroOverflow)).toBe(true);
});
