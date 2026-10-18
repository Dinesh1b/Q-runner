import { test, expect } from '@playwright/test';
import { attachClientSideMonitors, credentials, gotoLogin } from './helpers';

test.describe('Stockount login flow', () => {
  test('login page renders the required authentication controls', async ({ page }) => {
    await gotoLogin(page);

    await expect(page).toHaveTitle(/Stockount/i);
    await expect(page.getByRole('textbox', { name: /email/i })).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole('button', { name: /login/i })).toBeDisabled();
  });

  test('required field validation is shown when the form is submitted empty', async ({ page }) => {
    await gotoLogin(page);

    await page.getByRole('button', { name: /login/i }).focus();
    await page.getByRole('button', { name: /login/i }).blur();

    await expect(page.getByRole('button', { name: /login/i })).toBeDisabled();
  });

  test('invalid email is rejected before authentication', async ({ page }) => {
    await gotoLogin(page);

    await page.getByRole('textbox', { name: /email/i }).fill('invalid-email');
    await page.locator('input[type="password"]').fill('example-password');
    await expect(page.getByRole('button', { name: /login/i })).toBeDisabled();
  });

  test('incorrect credentials show an error and keep the user on login', async ({ page }) => {
    await gotoLogin(page);

    await page.getByRole('textbox', { name: /email/i }).fill(credentials.email);
    await page.locator('input[type="password"]').fill(`${credentials.password}x`);
    await page.getByRole('button', { name: /login/i }).click();

    await expect(page).toHaveURL(/authorization\/login/);
    await expect(page.getByText(/invalid|incorrect|try again|failed/i)).toBeVisible();
  });

  test('valid credentials should redirect to the authenticated app without major client-side errors', async ({ page }) => {
    const monitor = attachClientSideMonitors(page);
    await gotoLogin(page);

    await page.getByRole('textbox', { name: /email/i }).fill(credentials.email);
    await page.locator('input[type="password"]').fill(credentials.password);

    const loginButton = page.getByRole('button', { name: /login/i });
    await expect(loginButton).toBeEnabled();
    await loginButton.click();

    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/authorization\/login/);

    expect.soft(monitor.consoleErrors, `Console errors: ${monitor.consoleErrors.join(' | ')}`).toEqual([]);
    expect.soft(monitor.requestFailures, `Request failures: ${monitor.requestFailures.join(' | ')}`).toEqual([]);
  });
});
