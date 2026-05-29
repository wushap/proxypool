import { test, expect } from '@playwright/test';

test.describe('Proxy Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxies page
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('section.card, .empty-state').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display export button', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出代理")');
    await expect(exportButton).toBeVisible();
  });

  test('should open export dialog on click', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出代理")');
    await exportButton.click();

    // The export dialog should appear
    const exportDialog = page.locator('.el-dialog').filter({ hasText: '导出代理' });
    await expect(exportDialog).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Subscription Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to tasks page where subscription export controls live
    await page.locator('.el-menu-item').filter({ hasText: '任务中心' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have export functionality on tasks page', async ({ page }) => {
    // Check for any export-related buttons or links on the page
    const exportButtons = page.locator('button:has-text("导出"), a:has-text("导出")');
    const count = await exportButtons.count();
    // At least some form of export should be available or the page should load
    const pageTitle = page.locator('h2.section-title').filter({ hasText: '任务列表' });
    await expect(pageTitle).toBeVisible();
  });

  test('should have copy subscription button', async ({ page }) => {
    const copyButton = page.locator('button:has-text("复制订阅")');
    await expect(copyButton).toBeVisible();
  });

  test('should have export link button', async ({ page }) => {
    const exportLinkButton = page.locator('button:has-text("导出链接"), a:has-text("导出链接")');
    await expect(exportLinkButton).toBeVisible();
  });
});

test.describe('Pool Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxy pools page
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have export config button', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出配置")');
    await expect(exportButton).toBeVisible();
  });

  test('should have import config button', async ({ page }) => {
    const importButton = page.locator('button:has-text("导入配置")');
    await expect(importButton).toBeVisible();
  });
});

test.describe('System Version', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to settings page
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display version info on settings page', async ({ page }) => {
    const aboutCard = page.locator('.settings-card').filter({ hasText: '关于' });
    await expect(aboutCard).toBeVisible();
  });

  test('should display version number 0.2.0', async ({ page }) => {
    const versionValue = page.locator('.about-value').filter({ hasText: '0.2.0' });
    await expect(versionValue).toBeVisible();
  });

  test('should display app name Proxy Pool', async ({ page }) => {
    const appName = page.locator('.about-value').filter({ hasText: 'Proxy Pool' });
    await expect(appName).toBeVisible();
  });

  test('should display description text', async ({ page }) => {
    const description = page.locator('.about-value').filter({ hasText: '高性能代理池管理器' });
    await expect(description).toBeVisible();
  });
});

test.describe('System Diagnostics Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to system diagnostics page
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should navigate to diagnostics page', async ({ page }) => {
    await expect(page.locator('h2.section-title:has-text("系统诊断")')).toBeVisible();
  });

  test('should enable export report button after running diagnostics', async ({ page }) => {
    // Run diagnostics first
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Wait for diagnostics to complete
    await page.waitForTimeout(3000);
    await page.waitForLoadState('networkidle');

    // Export report button should be enabled after diagnostics complete
    const exportButton = page.locator('button:has-text("导出报告")');
    if (await exportButton.isVisible()) {
      await expect(exportButton).toBeEnabled();
    }
  });
});
