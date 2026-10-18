/**
 * PHASE 1 & 2: Application Exploration
 * This spec logs in, navigates to New Purchase, and maps out all DOM elements.
 * Results are written to test-results/exploration-report.json for use in writing targeted tests.
 */
import { test, expect } from '@playwright/test';
import { login, attachClientSideMonitors } from './helpers';
import * as fs from 'fs';
import * as path from 'path';

test.describe('App Exploration', () => {
  test('map login page and post-login dashboard', async ({ page }, testInfo) => {
    const monitor = attachClientSideMonitors(page);

    // --- Login page ---
    await page.goto('/authorization/login');
    await page.waitForLoadState('networkidle');

    const loginPageTitle = await page.title();
    const loginUrl = page.url();

    // Collect all text/input/button elements on login page
    const loginPageInputs = await page.$$eval('input', els =>
      els.map(el => ({
        type: (el as HTMLInputElement).type,
        placeholder: (el as HTMLInputElement).placeholder,
        name: (el as HTMLInputElement).name,
        id: el.id,
        disabled: (el as HTMLInputElement).disabled,
        value: (el as HTMLInputElement).value,
      }))
    );
    const loginPageButtons = await page.$$eval('button', els =>
      els.map(el => ({
        text: el.textContent?.trim(),
        disabled: (el as HTMLButtonElement).disabled,
        type: (el as HTMLButtonElement).type,
      }))
    );

    await testInfo.attach('login-page-inputs', {
      body: JSON.stringify(loginPageInputs, null, 2),
      contentType: 'application/json',
    });

    // --- Login ---
    await login(page);
    await page.waitForLoadState('networkidle');

    const postLoginUrl = page.url();
    const postLoginTitle = await page.title();

    // Collect nav items
    const navItems = await page.$$eval('nav a, aside a, [role="navigation"] a, .sidebar a, .menu a, li a', els =>
      els.map(el => ({
        text: el.textContent?.trim(),
        href: el.getAttribute('href'),
      })).filter(e => e.text || e.href)
    );

    await testInfo.attach('nav-items', {
      body: JSON.stringify(navItems, null, 2),
      contentType: 'application/json',
    });

    // Collect all visible text on the page
    const bodyText = await page.locator('body').innerText();

    await testInfo.attach('post-login-body-text', {
      body: bodyText.substring(0, 5000),
      contentType: 'text/plain',
    });

    // Screenshot
    await page.screenshot({ path: 'test-results/post-login-dashboard.png', fullPage: true });

    // Navigate to new purchase
    await page.goto('/home/purchase/newpurchase');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000); // let Angular render

    const purchasePageUrl = page.url();
    const purchasePageTitle = await page.title();

    // Collect all inputs on purchase page
    const purchaseInputs = await page.$$eval('input, textarea, select', els =>
      els.map(el => ({
        tag: el.tagName,
        type: (el as HTMLInputElement).type,
        placeholder: (el as HTMLInputElement).placeholder,
        name: (el as HTMLInputElement).name,
        id: el.id,
        disabled: (el as HTMLInputElement).disabled,
        'aria-label': el.getAttribute('aria-label'),
        'ng-reflect-placeholder': el.getAttribute('ng-reflect-placeholder'),
        class: el.className.substring(0, 80),
      }))
    );

    const purchaseButtons = await page.$$eval('button', els =>
      els.map(el => ({
        text: el.textContent?.trim(),
        disabled: (el as HTMLButtonElement).disabled,
        id: el.id,
        class: el.className.substring(0, 80),
      }))
    );

    const purchaseBodyText = await page.locator('body').innerText();

    // Collect labels
    const labels = await page.$$eval('label', els =>
      els.map(el => ({
        text: el.textContent?.trim(),
        for: el.getAttribute('for'),
      }))
    );

    // Collect table headers
    const tableHeaders = await page.$$eval('th, .p-datatable-column-title, [role="columnheader"]', els =>
      els.map(el => el.textContent?.trim())
    );

    // Collect PrimeNG dropdowns
    const dropdowns = await page.$$eval('p-dropdown, p-select, p-autocomplete, p-multiselect', els =>
      els.map(el => ({
        tag: el.tagName,
        placeholder: el.getAttribute('ng-reflect-placeholder') || el.getAttribute('placeholder'),
        label: el.getAttribute('ng-reflect-option-label'),
        formControlName: el.getAttribute('formcontrolname'),
        ngReflectFilter: el.getAttribute('ng-reflect-filter'),
      }))
    );

    const report = {
      loginPage: {
        url: loginUrl,
        title: loginPageTitle,
        inputs: loginPageInputs,
        buttons: loginPageButtons,
      },
      postLogin: {
        url: postLoginUrl,
        title: postLoginTitle,
        navItems,
      },
      newPurchasePage: {
        url: purchasePageUrl,
        title: purchasePageTitle,
        inputs: purchaseInputs,
        buttons: purchaseButtons,
        labels,
        tableHeaders,
        dropdowns,
        bodyTextPreview: purchaseBodyText.substring(0, 3000),
      },
      clientSideMonitor: {
        consoleErrors: monitor.consoleErrors,
        requestFailures: monitor.requestFailures.slice(0, 10),
        serverErrors: monitor.serverErrors.slice(0, 10),
      },
    };

    await testInfo.attach('full-exploration-report', {
      body: JSON.stringify(report, null, 2),
      contentType: 'application/json',
    });

    // Save to file
    const outDir = path.join(process.cwd(), 'test-results');
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'exploration-report.json'), JSON.stringify(report, null, 2));

    await page.screenshot({ path: 'test-results/new-purchase-page.png', fullPage: true });

    console.log('=== EXPLORATION REPORT ===');
    console.log('Post-Login URL:', postLoginUrl);
    console.log('New Purchase URL:', purchasePageUrl);
    console.log('Nav items count:', navItems.length);
    console.log('Purchase page inputs count:', purchaseInputs.length);
    console.log('Purchase page buttons count:', purchaseButtons.length);
    console.log('Purchase page dropdowns count:', dropdowns.length);
    console.log('Labels:', JSON.stringify(labels, null, 2));
    console.log('Table headers:', JSON.stringify(tableHeaders, null, 2));
    console.log('Dropdowns:', JSON.stringify(dropdowns, null, 2));
    console.log('Buttons:', JSON.stringify(purchaseButtons, null, 2));
    console.log('Inputs:', JSON.stringify(purchaseInputs, null, 2));
    console.log('Console errors:', monitor.consoleErrors);
    console.log('Request failures:', monitor.requestFailures.slice(0, 5));
    console.log('Body text preview:', purchaseBodyText.substring(0, 1000));

    // Basic sanity assertions
    expect(purchasePageUrl).not.toContain('authorization/login');
  });
});
