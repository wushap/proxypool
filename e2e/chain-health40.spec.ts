import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 40) ──

test.describe('Chain Health Check (Round 40)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('aside.sidebar');
    await expect(sidebar).toBeVisible();

    const menuItems = sidebar.locator('.el-menu-item');
    const menuCount = await menuItems.count();
    expect(menuCount).toBeGreaterThanOrEqual(5);

    const dashboardItem = page.locator('.el-menu-item').filter({ hasText: '仪表盘' });
    await expect(dashboardItem).toBeVisible();

    const proxyItem = page.locator('.el-menu-item').filter({ hasText: '代理节点' });
    await expect(proxyItem).toBeVisible();
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.dashboard-stat-grid');
    await expect(statGrid).toBeVisible();

    const statCards = statGrid.locator('.stat-card, [class*="stat"]');
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has system status', async ({ page }) => {
    const statusTitle = page.locator('.card-title').filter({ hasText: '系统状态' });
    await expect(statusTitle).toBeVisible();

    const statusCard = statusTitle.locator('..');
    const statusRows = statusCard.locator('.dashboard-status-row');
    const rowCount = await statusRows.count();
    expect(rowCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has real-time monitoring', async ({ page }) => {
    const monitoringTitle = page.locator('.card-title').filter({ hasText: '实时监控' });
    await expect(monitoringTitle).toBeVisible();

    const monitoringCard = monitoringTitle.locator('..');
    const statGrid = monitoringCard.locator('.stat-grid');
    await expect(statGrid.first()).toBeVisible();

    const statCards = monitoringCard.locator('.stat-card, [class*="stat"]');
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has quick actions', async ({ page }) => {
    const quickActionsTitle = page.locator('.card-title').filter({ hasText: '快速操作' });
    await expect(quickActionsTitle).toBeVisible();

    const actionBar = page.locator('.action-bar');
    await expect(actionBar).toBeVisible();

    const buttons = actionBar.locator('button, a');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(3);
  });
});

// ── Batch Operations (Round 40) ──

test.describe('Batch Operations (Round 40)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscription page has add form', async ({ page }) => {
    const nameInput = page.locator('input[placeholder="订阅名称"]');
    await expect(nameInput).toBeVisible();

    const urlInput = page.locator('input[placeholder="订阅链接 URL"]');
    await expect(urlInput).toBeVisible();

    const addBtn = page.locator('button').filter({ hasText: '添加订阅' });
    await expect(addBtn.first()).toBeVisible();
  });

  test('subscription page has group tabs', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    const tabs = groupTabs.locator('button[role="tab"], .btn');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(1);

    const allTab = groupTabs.locator('button').filter({ hasText: '全部' });
    await expect(allTab.first()).toBeVisible();
  });

  test('subscription page has batch buttons', async ({ page }) => {
    const sectionHeader = page.locator('.section-header');
    await expect(sectionHeader).toBeVisible();

    const refreshAllBtn = sectionHeader.locator('button').filter({ hasText: '刷新全部' });
    await expect(refreshAllBtn.first()).toBeVisible();

    const refreshListBtn = sectionHeader.locator('button').filter({ hasText: '刷新列表' });
    await expect(refreshListBtn.first()).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 40) ──

test.describe('System Diagnostics Export (Round 40)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('settings page has theme options', async ({ page }) => {
    const appearanceTitle = page.locator('.settings-title').filter({ hasText: '外观设置' });
    await expect(appearanceTitle).toBeVisible();

    const themeRadio = page.locator('.el-radio-button').filter({ hasText: '浅色' });
    await expect(themeRadio.first()).toBeVisible();

    const darkRadio = page.locator('.el-radio-button').filter({ hasText: '深色' });
    await expect(darkRadio.first()).toBeVisible();
  });

  test('settings page has about section', async ({ page }) => {
    const aboutTitle = page.locator('.settings-title').filter({ hasText: '关于' });
    await expect(aboutTitle).toBeVisible();

    const aboutInfo = page.locator('.about-info');
    await expect(aboutInfo).toBeVisible();

    const appName = aboutInfo.locator('.about-value').filter({ hasText: 'Proxy Pool' });
    await expect(appName.first()).toBeVisible();

    const resetBtn = page.locator('button').filter({ hasText: '重置为默认设置' });
    await expect(resetBtn.first()).toBeVisible();
  });
});
