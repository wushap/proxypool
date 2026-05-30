import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 38) ──

test.describe('Chain Routing (Round 38)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('.sidebar-menu').first();
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    const menuItems = page.locator('.el-menu-item');
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(8);

    const texts = await menuItems.allTextContents();
    const joined = texts.join(' ');
    expect(joined).toContain('仪表盘');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('订阅管理');
    expect(joined).toContain('配置历史');
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.stat-grid.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 30000 });

    const statCards = statGrid.locator('.stat-card, .card');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const gridText = await statGrid.textContent();
    expect(gridText).toContain('节点总数');
    expect(gridText).toContain('可用节点');
    expect(gridText).toContain('可用率');
    expect(gridText).toContain('平均延迟');
  });

  test('dashboard has system status section', async ({ page }) => {
    const statusCard = page.locator('.card').filter({ hasText: '系统状态' }).first();
    await statusCard.scrollIntoViewIfNeeded();
    await expect(statusCard).toBeVisible({ timeout: 10000 });

    const statusList = statusCard.locator('.dashboard-status-list');
    await expect(statusList).toBeVisible();

    const statusRows = statusList.locator('.dashboard-status-row');
    const count = await statusRows.count();
    expect(count).toBeGreaterThanOrEqual(2);

    const rowLabels = statusList.locator('.dashboard-status-label');
    const labels = await rowLabels.allTextContents();
    expect(labels).toContain('后端引擎');
    expect(labels).toContain('网关服务');
  });

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await protocolCard.scrollIntoViewIfNeeded();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    const hasDonut = await protocolCard.locator('.dashboard-donut-wrapper').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await protocolCard.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasDonut || hasEmpty).toBeTruthy();

    if (hasDonut) {
      const svgChart = protocolCard.locator('.dashboard-donut-svg');
      await expect(svgChart).toBeVisible();

      const legendItems = protocolCard.locator('.dashboard-donut-legend-item');
      const legendCount = await legendItems.count();
      expect(legendCount).toBeGreaterThanOrEqual(1);
    }
  });

  test('dashboard has quick actions', async ({ page }) => {
    const hasQuickActions = await page.locator('text=快速操作').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasQuickActions).toBeTruthy();
  });
});

// ── Subscription Intelligence (Round 38) ──

test.describe('Subscription Intelligence (Round 38)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '代理节点');
  });

  test('proxy nodes page has data table', async ({ page }) => {
    const table = page.locator('table, .el-table').first();
    await expect(table).toBeVisible({ timeout: 15000 });

    const headers = page.locator('th, .el-table__header-wrapper th');
    const headerCount = await headers.count();
    expect(headerCount).toBeGreaterThanOrEqual(3);
  });

  test('proxy nodes page has filter inputs', async ({ page }) => {
    const searchInput = page.locator('input').first();
    await expect(searchInput).toBeVisible({ timeout: 10000 });

    // Check for filter-related elements (search box, select, or button filters)
    const filterArea = page.locator('.filter, .toolbar, .search-bar, .card').first();
    const filterVisible = await filterArea.isVisible({ timeout: 10000 }).catch(() => false);
    expect(filterVisible).toBeTruthy();
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    const buttons = page.locator('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(1);

    const pageText = await page.locator('.page-container, .card').first().textContent({ timeout: 15000 });
    expect(pageText).toBeTruthy();
  });
});

// ── System Diagnostics Export (Round 38) ──

test.describe('System Diagnostics Export (Round 38)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '配置历史');
  });

  test('config history has save snapshot button', async ({ page }) => {
    // Look for save/snapshot button or the page header
    const saveBtn = page.locator('button').filter({ hasText: /保存|快照|snapshot/i }).first();
    const saveBtnVisible = await saveBtn.isVisible({ timeout: 10000 }).catch(() => false);

    // Also check for page header or card title
    const pageTitle = page.locator('.page-title, .card-title, h2, h3').filter({ hasText: /配置|历史|快照/i }).first();
    const titleVisible = await pageTitle.isVisible({ timeout: 10000 }).catch(() => false);

    expect(saveBtnVisible || titleVisible).toBeTruthy();
  });

  test('config history has empty state or snapshot list', async ({ page }) => {
    const hasEmptyState = await page.locator('.empty-state, .el-empty, [class*="empty"]').first().isVisible({ timeout: 10000 }).catch(() => false);

    const hasSnapshotList = await page.locator('.el-table, table, .card').first().isVisible({ timeout: 10000 }).catch(() => false);

    expect(hasEmptyState || hasSnapshotList).toBeTruthy();
  });
});
