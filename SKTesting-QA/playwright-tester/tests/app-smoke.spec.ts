import { test, expect } from '@playwright/test';
import { attachClientSideMonitors, login } from './helpers';

test.describe('Stockount authenticated smoke coverage', () => {
  test('authenticated shell loads, exposes navigation, and allows basic page traversal', async ({ page }, testInfo) => {
    const monitor = attachClientSideMonitors(page);
    await login(page);

    await expect(page.getByRole('main')).toBeVisible();

    const nav = page.locator('nav a, [role="navigation"] a, aside a');
    await expect(nav.first()).toBeVisible({ timeout: 20000 });

    const links = await nav.evaluateAll((anchors) =>
      anchors
        .map((anchor) => ({
          text: anchor.textContent?.trim() ?? '',
          href: anchor.getAttribute('href') ?? '',
        }))
        .filter((entry) => entry.text || entry.href),
    );

    await testInfo.attach('navigation-map.json', {
      body: JSON.stringify(links, null, 2),
      contentType: 'application/json',
    });

    const uniqueAppLinks = links
      .filter((entry) => entry.href && !entry.href.startsWith('http'))
      .slice(0, 8);

    for (const entry of uniqueAppLinks) {
      await page.goto(entry.href);
      await page.waitForLoadState('domcontentloaded');
      await expect(page.getByRole('main')).toBeVisible({ timeout: 20000 });
    }

    expect.soft(links.length).toBeGreaterThan(0);
    expect.soft(monitor.requestFailures, `Request failures: ${monitor.requestFailures.join(' | ')}`).toEqual([]);
  });

  test('session remains valid after refresh and protected pages redirect after logout', async ({ page }) => {
    await login(page);
    const authenticatedUrl = page.url();

    await page.reload();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(authenticatedUrl);

    const logoutControl = page.getByRole('button', { name: /logout|sign out/i }).or(
      page.getByRole('menuitem', { name: /logout|sign out/i }),
    );
    await logoutControl.first().click();

    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/login|authorization/i);

    await page.goto(authenticatedUrl);
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/login|authorization/i);
  });
});
