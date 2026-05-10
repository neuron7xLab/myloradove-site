import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

/**
 * axe-core accessibility scan.
 * Fails on any serious or critical violation.
 * Known exclusions must be listed + justified here — not silently ignored.
 */

test.describe('axe a11y', () => {
  test('homepage has no serious/critical violations', async ({ page }) => {
    await page.goto('/');
    const result = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .disableRules([
        // color-contrast is audited visually; mix-blend-mode on nav
        // produces dynamic contrast that axe cannot evaluate statically.
        'color-contrast',
      ])
      .analyze();

    const serious = result.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical',
    );
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });

  test('404 page has no serious/critical violations', async ({ page }) => {
    await page.goto('/404.html');
    const result = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    const serious = result.violations.filter(
      (v) => v.impact === 'serious' || v.impact === 'critical',
    );
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });
});
