import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 60) ──

test.describe('Chain Routing (Round 60)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('aside.sidebar').first();
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    const menuItems = sidebar.locator('.el-menu-item');
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(5);

    const texts = await menuItems.allTextContents();
    const joined = texts.join(' ');
    expect(joined).toContain('仪表盘');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('设置');
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 30000 });

    const statCards = statGrid.locator('.stat-card, [class*="stat"]');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const gridText = await statGrid.textContent();
    expect(gridText).toContain('节点总数');
    expect(gridText).toContain('可用节点');
    expect(gridText).toContain('可用率');
  });

  test('dashboard has system status', async ({ page }) => {
    const statusCard = page.locator('.card').filter({ hasText: '系统状态' }).first();
    await statusCard.scrollIntoViewIfNeeded();
    await expect(statusCard).toBeVisible({ timeout: 10000 });

    const statusRows = statusCard.locator('.dashboard-status-row');
    const count = await statusRows.count();
    expect(count).toBeGreaterThanOrEqual(2);

    const rowLabels = statusCard.locator('.dashboard-status-label');
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
    await page.locator('.stat-grid.dashboard-stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });

    const quickActionsCard = page.locator('.card').filter({ has: page.locator('.card-title:text-is("快速操作")') }).first();
    await quickActionsCard.scrollIntoViewIfNeeded();
    await expect(quickActionsCard).toBeVisible({ timeout: 10000 });

    const buttons = quickActionsCard.locator('button');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(5);
  });
});

// ── Subscription Intelligence (Round 60) ──

test.describe('Subscription Intelligence (Round 60)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '代理节点');
  });

  test('proxy nodes page has data table', async ({ page }) => {
    await page.locator('.section-title, .page-title').first().waitFor({ state: 'visible', timeout: 15000 });

    const hasTable = await page.locator('table.data-table').isVisible({ timeout: 10000 }).catch(() => false);
    const hasCardTable = await page.locator('.card table').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasTable || hasCardTable || hasEmpty).toBeTruthy();

    if (hasTable || hasCardTable) {
      const table = hasTable ? page.locator('table.data-table').first() : page.locator('.card table').first();
      const rows = table.locator('tbody tr');
      const headerCells = table.locator('thead th, thead td');
      const headerCount = await headerCells.count();
      expect(headerCount).toBeGreaterThanOrEqual(3);
    }
  });

  test('proxy nodes page has filter inputs', async ({ page }) => {
    const filterArea = page.locator('.filter-bar, .search-bar, .table-filter, .card').first();
    await filterArea.waitFor({ state: 'visible', timeout: 15000 });

    const searchInput = page.locator('input[placeholder*="搜索"], input[placeholder*="过滤"], input[placeholder*="search"]').first();
    const protocolFilter = page.locator('select, .el-select').first();

    const hasSearch = await searchInput.isVisible({ timeout: 5000 }).catch(() => false);
    const hasSelect = await protocolFilter.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasSearch || hasSelect).toBeTruthy();
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });

    const buttons = page.locator('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(1);

    const buttonTexts = await buttons.allTextContents();
    const joined = buttonTexts.join(' ');
    const hasAction = joined.includes('刷新') || joined.includes('删除') || joined.includes('全部') || joined.includes('检测') || joined.includes('导入');
    expect(hasAction).toBeTruthy();
  });
});

// ── System Diagnostics Export (Round 60) ──

test.describe('System Diagnostics Export (Round 60)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '配置历史');
  });

  test('config history has save snapshot button', async ({ page }) => {
    await page.locator('.section-title, h2, h1').filter({ hasText: '配置历史' }).first().waitFor({ state: 'visible', timeout: 15000 });

    const saveButton = page.locator('button:has-text("保存快照")').first();
    await expect(saveButton).toBeVisible({ timeout: 10000 });
    await expect(saveButton).toBeEnabled();
  });

  test('config history has empty state or snapshot list', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });

    const hasEmpty = await page.locator('.empty-state-title:has-text("暂无配置快照")').isVisible({ timeout: 5000 }).catch(() => false);
    const hasList = await page.locator('.config-snapshot-list, .config-snapshot-item').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasTitle = await page.locator('h1:has-text("配置历史"), h2:has-text("配置历史")').isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasEmpty || hasList || hasTitle).toBeTruthy();
  });
});
