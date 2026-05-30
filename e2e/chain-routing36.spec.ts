import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 36) ──

test.describe('Chain Routing (Round 36)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar with navigation menu', async ({ page }) => {
    const sidebar = page.locator('.sidebar-menu').first();
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    // Verify key navigation items exist
    const menuItems = page.locator('.el-menu-item');
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(8);

    const menuItemTexts = await menuItems.allTextContents();
    const joinedTexts = menuItemTexts.join(' ');
    expect(joinedTexts).toContain('仪表盘');
    expect(joinedTexts).toContain('代理节点');
    expect(joinedTexts).toContain('多跳代理池');
    expect(joinedTexts).toContain('入站端口');
    expect(joinedTexts).toContain('订阅管理');
    expect(joinedTexts).toContain('使用指南');
    expect(joinedTexts).toContain('配置历史');
    expect(joinedTexts).toContain('系统诊断');
  });

  test('dashboard has stat cards grid', async ({ page }) => {
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });

    const statGrid = page.locator('.stat-grid.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 10000 });

    // Stat cards are rendered as card components within the grid
    const statCards = statGrid.locator('.stat-card, .card');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);

    // Verify the stat grid contains key labels
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

    // Verify backend engine and gateway service rows exist
    const rowLabels = statusList.locator('.dashboard-status-label');
    const labels = await rowLabels.allTextContents();
    expect(labels).toContain('后端引擎');
    expect(labels).toContain('网关服务');
  });

  test('dashboard has real-time monitoring', async ({ page }) => {
    const monitoringCard = page.locator('.card').filter({ hasText: '实时监控' }).first();
    await monitoringCard.scrollIntoViewIfNeeded();
    await expect(monitoringCard).toBeVisible({ timeout: 15000 });

    // The monitoring section contains a stat-grid with monitoring stat cards
    const monitoringGrid = monitoringCard.locator('.stat-grid').first();
    await expect(monitoringGrid).toBeVisible();

    const gridText = await monitoringGrid.textContent();
    expect(gridText).toContain('活跃连接');
    expect(gridText).toContain('总连接数');
  });

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    // The card should contain either a donut chart or an empty state
    const donutWrapper = protocolCard.locator('.dashboard-donut-wrapper').first();
    const emptyState = protocolCard.locator('.empty-state').first();

    const hasDonut = await donutWrapper.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasDonut || hasEmpty).toBeTruthy();

    if (hasDonut) {
      // Verify the SVG donut chart is present
      const svgChart = donutWrapper.locator('.dashboard-donut-svg');
      await expect(svgChart).toBeVisible();

      // Verify legend items exist
      const legendItems = donutWrapper.locator('.dashboard-donut-legend-item');
      const legendCount = await legendItems.count();
      expect(legendCount).toBeGreaterThanOrEqual(1);
    }
  });
});

// ── Subscription Intelligence (Round 36) ──

test.describe('Subscription Intelligence (Round 36)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '代理节点');
  });

  test('proxy nodes page has data table', async ({ page }) => {
    // The proxy page has a card wrapping the data table
    const proxyCard = page.locator('.card').filter({ hasText: '代理节点' }).first();
    await expect(proxyCard).toBeVisible({ timeout: 10000 });

    // Either a data table or an empty state should be present
    const dataTable = proxyCard.locator('.data-table').first();
    const tableVisible = await dataTable.isVisible({ timeout: 10000 }).catch(() => false);

    const emptyState = proxyCard.locator('.empty-state').first();
    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);

    expect(tableVisible || hasEmpty).toBeTruthy();

    // The status bar showing count info should be present
    const statusBar = proxyCard.locator('.status-bar').first();
    await expect(statusBar).toBeVisible({ timeout: 5000 });
  });

  test('proxy nodes page has filter inputs', async ({ page }) => {
    const filterPanel = page.locator('.filter-panel').first();
    await expect(filterPanel).toBeVisible({ timeout: 10000 });

    // Click to expand the filter panel
    const filterToggle = filterPanel.locator('.filter-panel-toggle');
    await expect(filterToggle).toBeVisible();
    await filterToggle.click();

    // After expanding, filter fields should be visible
    const filterBody = filterPanel.locator('.filter-panel-body');
    await expect(filterBody).toBeVisible({ timeout: 5000 });

    const filterFields = filterBody.locator('.filter-panel-field');
    const fieldCount = await filterFields.count();
    expect(fieldCount).toBeGreaterThanOrEqual(3);
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    const importBtn = page.locator('button').filter({ hasText: '导入代理' }).first();
    await expect(importBtn).toBeVisible({ timeout: 10000 });

    const exportBtn = page.locator('button').filter({ hasText: '导出代理' }).first();
    await expect(exportBtn).toBeVisible();

    // Verify additional action buttons exist
    const clearBtn = page.locator('button').filter({ hasText: '清空筛选' }).first();
    await expect(clearBtn).toBeVisible();

    const resetBtn = page.locator('button').filter({ hasText: '重置列' }).first();
    await expect(resetBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 36) ──

test.describe('System Diagnostics Export (Round 36)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '配置历史');
  });

  test('config history has save snapshot button', async ({ page }) => {
    const saveBtn = page.locator('button').filter({ hasText: '保存快照' }).first();
    await expect(saveBtn).toBeVisible({ timeout: 10000 });

    // Verify the page header exists with the correct title
    const sectionTitle = page.locator('.section-title').filter({ hasText: '配置历史' }).first();
    await expect(sectionTitle).toBeVisible();

    // Verify the description text is present
    const descriptionText = page.locator('p.text-muted').filter({ hasText: '管理配置快照' }).first();
    await expect(descriptionText).toBeVisible();
  });

  test('config history has empty state or snapshot list', async ({ page }) => {
    // Either an empty state or a snapshot list should be present
    const emptyState = page.locator('.empty-state').first();
    const hasEmpty = await emptyState.isVisible({ timeout: 10000 }).catch(() => false);

    const snapshotList = page.locator('.config-snapshot-list').first();
    const hasList = await snapshotList.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasEmpty || hasList).toBeTruthy();

    if (hasList) {
      // If snapshots exist, verify snapshot items are rendered
      const snapshotItems = snapshotList.locator('.config-snapshot-item');
      const itemCount = await snapshotItems.count();
      expect(itemCount).toBeGreaterThanOrEqual(1);
    }
  });
});
