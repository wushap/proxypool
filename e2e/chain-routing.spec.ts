import { test, expect } from '@playwright/test';

test.describe('Chain Routing via Proxy Pools', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor();
  });

  test('should display chain view tab', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
  });

  test('should click chain view tab and load content', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainTab.click();

    // The chain view panel should become visible
    const chainPanel = page.locator('.tab-panel').filter({ has: page.locator('.chain-visualization, .chain-flow, h3:has-text("链路可视化")') });
    await expect(chainPanel).toBeVisible({ timeout: 5000 });
  });

  test('should show chain flow visualization', async ({ page }) => {
    // Switch to chain view tab
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainTab.click();

    // The chain flow container should be visible
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible({ timeout: 5000 });
  });

  test('should display chain node elements', async ({ page }) => {
    // Switch to chain view tab
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainTab.click();

    // Entry node should exist
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode).toBeVisible({ timeout: 5000 });

    // Exit (target) node should exist
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode).toBeVisible();

    // Chain arrows connecting nodes should exist
    const arrows = page.locator('.chain-arrow');
    await expect(arrows.first()).toBeVisible();
  });
});

test.describe('Batch Refresh via Subscriptions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor();
  });

  test('should display refresh all button', async ({ page }) => {
    const refreshAllBtn = page.locator('button:has-text("刷新全部")');
    await expect(refreshAllBtn).toBeVisible();
    await expect(refreshAllBtn).toBeEnabled();
  });

  test('should display delete unavailable button', async ({ page }) => {
    const deleteUnavailableBtn = page.locator('button:has-text("删除不可用")');
    await expect(deleteUnavailableBtn).toBeVisible();
  });

  test('should display refresh list button', async ({ page }) => {
    const refreshListBtn = page.locator('button:has-text("刷新列表")');
    await expect(refreshListBtn).toBeVisible();
    await expect(refreshListBtn).toBeEnabled();
  });
});

test.describe('System Version via Settings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor();
  });

  test('should show version info on settings page', async ({ page }) => {
    const aboutCard = page.locator('.settings-card').filter({ hasText: '关于' });
    await expect(aboutCard).toBeVisible();
  });

  test('should display version number 0.2.0', async ({ page }) => {
    const versionValue = page.locator('.about-value').filter({ hasText: '0.2.0' });
    await expect(versionValue).toBeVisible();
  });

  test('should display app name Proxy Pool', async ({ page }) => {
    const appNameValue = page.locator('.about-value').filter({ hasText: 'Proxy Pool' });
    await expect(appNameValue).toBeVisible();
  });
});
