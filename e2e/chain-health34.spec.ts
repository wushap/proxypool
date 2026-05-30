import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 34) ──

test.describe('Chain Health Check (Round 34)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    // Wait for loading to finish and dashboard content to appear
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.dashboard-stat-grid, .stat-grid').first().waitFor({ state: 'visible', timeout: 20000 });
  });

  test('dashboard has sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).toBeVisible();

    // Verify key menu items exist
    const menuItems = page.locator('.el-menu-item');
    const itemCount = await menuItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(6);

    // Verify specific menu items
    await expect(page.locator('.el-menu-item').filter({ hasText: '仪表盘' })).toBeVisible();
    await expect(page.locator('.el-menu-item').filter({ hasText: '代理节点' })).toBeVisible();
    await expect(page.locator('.el-menu-item').filter({ hasText: '多跳代理池' })).toBeVisible();
  });

  test('dashboard has stat cards grid', async ({ page }) => {
    const statGrid = page.locator('.dashboard-stat-grid');
    await expect(statGrid).toBeVisible();

    // Should contain multiple stat cards
    const statCards = statGrid.locator('.stat-card, [class*="stat"]');
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has system status section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '系统状态' });
    await expect(sectionTitle).toBeVisible();

    // System status section should contain status rows
    const card = sectionTitle.locator('..').locator('..');
    const statusRows = card.locator('.dashboard-status-row');
    const rowCount = await statusRows.count();
    expect(rowCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has real-time monitoring', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '实时监控' });
    await expect(sectionTitle).toBeVisible();

    // Real-time monitoring section should contain stat cards
    const card = sectionTitle.locator('..').locator('..');
    const statItems = card.locator('.stat-card, [class*="stat"]');
    const itemCount = await statItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has quick action buttons', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '快速操作' });
    await expect(sectionTitle).toBeVisible();

    // Quick actions section should have multiple buttons
    const card = sectionTitle.locator('..').locator('..');
    const buttons = card.locator('.action-bar button, .action-bar a');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(4);
  });
});

// ── Batch Operations (Round 34) ──

test.describe('Batch Operations (Round 34)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    // Wait for pool page content to appear
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 20000 });
  });

  test('pool page has creation form', async ({ page }) => {
    const createTitle = page.locator('.settings-title').filter({ hasText: '创建代理池' });
    await expect(createTitle).toBeVisible();

    // The creation form should have a name input and a create button
    const nameInput = page.locator('input[placeholder*="exit"]');
    await expect(nameInput.first()).toBeVisible();

    const createBtn = page.locator('button').filter({ hasText: '创建代理池' });
    await expect(createBtn.first()).toBeVisible();
  });

  test('pool page has chain view', async ({ page }) => {
    // Switch to chain view tab
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await chainTab.click();
    await page.waitForLoadState('domcontentloaded');

    // Chain view should have chain visualization elements
    const chainViz = page.locator('.chain-visualization, .chain-flow');
    await expect(chainViz.first()).toBeVisible({ timeout: 10000 });
  });

  test('pool page has filter section', async ({ page }) => {
    const filterTitle = page.locator('.form-section-title').filter({ hasText: '过滤条件' });
    await expect(filterTitle).toBeVisible();

    // The filter section should be expandable/collapsible
    const filterToggle = page.locator('.collapse-icon, .form-section-header').filter({ hasText: '过滤条件' });
    await expect(filterToggle.first()).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 34) ──

test.describe('System Diagnostics Export (Round 34)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    // Wait for subscription page content to appear
    await page.locator('.section-title').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 20000 });
  });

  test('subscription page has table or empty state', async ({ page }) => {
    // Page should show either a data table or an empty state
    const table = page.locator('.data-table');
    const emptyState = page.locator('.empty-state, .empty-state-small');

    const hasTable = await table.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();

    // Page title should be visible
    const sectionTitle = page.locator('.section-title').filter({ hasText: '订阅管理' });
    await expect(sectionTitle).toBeVisible();
  });

  test('subscription page has batch operation buttons', async ({ page }) => {
    // The page should have batch operation buttons
    const refreshAllBtn = page.locator('button').filter({ hasText: '刷新全部' }).first();
    await expect(refreshAllBtn).toBeVisible();

    const deleteUnavailableBtn = page.locator('button').filter({ hasText: '删除不可用' }).first();
    await expect(deleteUnavailableBtn).toBeVisible();

    const refreshListBtn = page.locator('button').filter({ hasText: '刷新列表' }).first();
    await expect(refreshListBtn).toBeVisible();
  });
});
