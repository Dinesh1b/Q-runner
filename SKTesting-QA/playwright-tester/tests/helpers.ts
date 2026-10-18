import { expect, type Page } from '@playwright/test';

export const credentials = {
  email: 'cucommugeuta-1374@yopmail.com',
  password: 'DWN83oxG',
};

export async function gotoLogin(page: Page) {
  await page.goto('/authorization/login');
  await expect(page).toHaveURL(/authorization\/login/);
}

export async function login(page: Page) {
  await gotoLogin(page);
  await page.getByRole('textbox', { name: /email/i }).fill(credentials.email);
  await page.locator('input[type="password"]').fill(credentials.password);
  await page.getByRole('button', { name: /login/i }).click();
  await page.waitForLoadState('networkidle');
  await expect(page).not.toHaveURL(/authorization\/login/);
}

export function attachClientSideMonitors(page: Page) {
  const consoleErrors: string[] = [];
  const requestFailures: string[] = [];
  const serverErrors: string[] = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('requestfailed', (request) => {
    requestFailures.push(`${request.method()} ${request.url()} :: ${request.failure()?.errorText ?? 'unknown failure'}`);
  });

  page.on('response', (response) => {
    if (response.status() >= 400) {
      serverErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  return { consoleErrors, requestFailures, serverErrors };
}
