import { test, expect } from '@playwright/test';

async function waitForPageReady(page: import('@playwright/test').Page) {
  await page.waitForLoadState('domcontentloaded');
  await page.locator('[role="navigation"], .sidebar-nav').first().waitFor({ state: 'visible', timeout: 10000 });
}

test.describe('Proxy Import', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('section.card, .empty-state, .page-container').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should show import button on proxies page', async ({ page }) => {
    const importButton = page.locator('button:has-text("导入代理")');
    await expect(importButton).toBeVisible();
  });

  test('should open import form when clicking import button', async ({ page }) => {
    const importButton = page.locator('button:has-text("导入代理")');
    await importButton.click();
    await page.waitForTimeout(500);

    // Either a dialog, drawer, or inline form should appear
    const importArea = page.locator('.el-dialog, .el-drawer, .import-form, textarea').first();
    await expect(importArea).toBeVisible({ timeout: 5000 });
  });

  test('should show export button on proxies page', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出代理")');
    await expect(exportButton).toBeVisible();
  });
});

test.describe('Subscription Controls', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should show refresh all button', async ({ page }) => {
    const refreshButton = page.locator('button:has-text("刷新全部")');
    await expect(refreshButton).toBeVisible();
  });

  test('should show delete unavailable button', async ({ page }) => {
    const deleteButton = page.locator('button:has-text("删除不可用")');
    await expect(deleteButton).toBeVisible();
  });

  test('should show refresh list button', async ({ page }) => {
    const refreshListButton = page.locator('button:has-text("刷新列表")');
    await expect(refreshListButton).toBeVisible();
  });

  test('should show subscription table with data or empty state', async ({ page }) => {
    const table = page.locator('table.data-table');
    const emptyState = page.locator('.empty-state');
    const hasTable = await table.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();
  });
});
