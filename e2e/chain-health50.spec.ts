import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 50) ──

test.describe('Chain Health Check (Round 50)', () => {
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

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolTitle = page.locator('.card-title').filter({ hasText: '协议分布' });
    await expect(protocolTitle).toBeVisible();

    const protocolCard = protocolTitle.locator('..');
    const hasDonut = await protocolCard.locator('.dashboard-donut-wrapper').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await protocolCard.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasDonut || hasEmpty).toBeTruthy();
  });

  test('dashboard has quick actions', async ({ page }) => {
    const headerActions = page.locator('.header-actions');
    await expect(headerActions).toBeVisible();

    const refreshBtn = headerActions.locator('button').filter({ hasText: '刷新' });
    await expect(refreshBtn.first()).toBeVisible();

    const refreshSelect = headerActions.locator('select');
    await expect(refreshSelect.first()).toBeVisible();
  });
});

// ── Batch Operations (Round 50) ──

test.describe('Batch Operations (Round 50)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('proxy nodes page has data table', async ({ page }) => {
    const tableWrap = page.locator('.table-wrap');
    await expect(tableWrap.first()).toBeVisible({ timeout: 10000 });

    const dataTable = tableWrap.locator('table.data-table');
    await expect(dataTable.first()).toBeVisible();

    const headerCells = dataTable.locator('thead th');
    const colCount = await headerCells.count();
    expect(colCount).toBeGreaterThanOrEqual(4);
  });

  test('proxy nodes page has filter inputs', async ({ page }) => {
    const filterToggle = page.locator('.filter-panel-toggle');
    await expect(filterToggle).toBeVisible();
    await expect(filterToggle).toHaveText(/高级筛选/);

    const filterPanel = page.locator('.filter-panel-body');
    const isVisible = await filterPanel.isVisible().catch(() => false);
    if (!isVisible) {
      await filterToggle.click();
    }
    await expect(filterPanel).toBeVisible();

    const filterFields = filterPanel.locator('.filter-panel-field');
    const fieldCount = await filterFields.count();
    expect(fieldCount).toBeGreaterThanOrEqual(3);
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    const sectionHeader = page.locator('.section-header');
    await expect(sectionHeader).toBeVisible();

    const importBtn = sectionHeader.locator('button').filter({ hasText: '导入代理' });
    await expect(importBtn).toBeVisible();

    const exportBtn = sectionHeader.locator('button').filter({ hasText: '导出代理' });
    await expect(exportBtn).toBeVisible();

    const paginationNav = page.locator('.pagination-nav');
    await expect(paginationNav).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 50) ──

test.describe('System Diagnostics Export (Round 50)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('config history has save snapshot button', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '配置历史' });
    await expect(sectionTitle).toBeVisible();

    const saveButton = page.locator('button').filter({ hasText: '保存快照' });
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeEnabled();
  });

  test('config history has empty state or snapshot list', async ({ page }) => {
    const emptyState = page.locator('.empty-state').first();
    const snapshotList = page.locator('.config-snapshot-list');

    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);
    const hasList = await snapshotList.isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasEmpty || hasList).toBeTruthy();
  });
});
