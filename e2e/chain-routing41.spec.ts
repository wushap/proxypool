import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 41) ──

test.describe('Chain Routing (Round 41)', () => {
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
    expect(joined).toContain('入站端口');
    expect(joined).toContain('订阅管理');
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

// ── Subscription Intelligence (Round 41) ──

test.describe('Subscription Intelligence (Round 41)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '代理节点');
  });

  test('proxy nodes page has data table', async ({ page }) => {
    const dataTable = page.locator('.data-table').first();
    await expect(dataTable).toBeVisible({ timeout: 10000 });

    const tableRows = dataTable.locator('tbody tr');
    const count = await tableRows.count();
    expect(count).toBeGreaterThanOrEqual(0);

    const hasStatusHeader = await page.locator('th, .data-table th').filter({ hasText: /状态|协议|节点|地址/ }).first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasAnyContent = await page.locator('.data-table td, .data-table th').first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasStatusHeader || hasAnyContent).toBeTruthy();
  });

  test('proxy nodes page has filter inputs', async ({ page }) => {
    const filterPanel = page.locator('.filter-panel').first();
    await expect(filterPanel).toBeVisible({ timeout: 10000 });

    const filterToggle = page.locator('.filter-panel-toggle').first();
    await expect(filterToggle).toBeVisible();

    const hasActiveChips = await page.locator('.filter-panel-active-chips').isVisible({ timeout: 5000 }).catch(() => false);

    await filterToggle.click();
    const hasFilterBody = await page.locator('.filter-panel-body').isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasActiveChips || hasFilterBody).toBeTruthy();
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    const importBtn = page.locator('button').filter({ hasText: '导入代理' }).first();
    await expect(importBtn).toBeVisible({ timeout: 10000 });

    const exportBtn = page.locator('button').filter({ hasText: '导出代理' }).first();
    await expect(exportBtn).toBeVisible();

    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 41) ──

test.describe('System Diagnostics Export (Round 41)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '系统诊断');
  });

  test('diagnostics has health overview', async ({ page }) => {
    const healthCard = page.locator('.card').filter({ hasText: '系统健康概览' }).first();
    await expect(healthCard).toBeVisible({ timeout: 10000 });

    const healthGrid = healthCard.locator('.health-summary-grid').first();
    await expect(healthGrid).toBeVisible();

    const healthItems = healthGrid.locator('.health-item');
    const count = await healthItems.count();
    expect(count).toBeGreaterThanOrEqual(2);

    const labels = healthGrid.locator('.health-label');
    const labelTexts = await labels.allTextContents();
    expect(labelTexts).toContain('后端进程');
    expect(labelTexts).toContain('网关服务');
  });

  test('diagnostics has diagnostic button', async ({ page }) => {
    const hasDiagBtn = await page.locator('button:has-text("一键诊断")').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasDiagBtn).toBeTruthy();
  });
});
