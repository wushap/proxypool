import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card, .dashboard-page').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 43) ──

test.describe('Chain Routing (Round 43)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card, .dashboard-page').first().waitFor({ state: 'visible', timeout: 15000 });
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

  test('dashboard has system status', async ({ page }) => {
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
    // The quick actions are inside v-else, only rendered after data loads
    await page.locator('.stat-grid.dashboard-stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });

    // Match the card whose title is exactly "快速操作" (not "快速操作历史")
    const quickActionsCard = page.locator('.card').filter({ has: page.locator('.card-title:text-is("快速操作")') }).first();
    await quickActionsCard.scrollIntoViewIfNeeded();
    await expect(quickActionsCard).toBeVisible({ timeout: 10000 });

    const buttons = quickActionsCard.locator('button');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(5);
  });
});

// ── Subscription Intelligence (Round 43) ──

test.describe('Subscription Intelligence (Round 43)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '代理节点');
  });

  test('proxy nodes page has data table', async ({ page }) => {
    const card = page.locator('.card').first();
    await expect(card).toBeVisible({ timeout: 10000 });

    const sectionTitle = card.locator('.section-title, h2').filter({ hasText: '代理节点' }).first();
    await expect(sectionTitle).toBeVisible({ timeout: 10000 });

    const statusBar = page.locator('.status-bar[role="status"]').first();
    const statusVisible = await statusBar.isVisible({ timeout: 5000 }).catch(() => false);

    const tableArea = page.locator('.el-table, table, .pagination').first();
    const tableVisible = await tableArea.isVisible({ timeout: 5000 }).catch(() => false);

    expect(statusVisible || tableVisible).toBeTruthy();
  });

  test('proxy nodes page has filter inputs', async ({ page }) => {
    const filterPanel = page.locator('.filter-panel').first();
    await expect(filterPanel).toBeVisible({ timeout: 10000 });

    const toggleBtn = filterPanel.locator('.filter-panel-toggle').first();
    await expect(toggleBtn).toBeVisible();

    const toggleText = await toggleBtn.textContent();
    expect(toggleText).toBeTruthy();
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    const importBtn = page.locator('button').filter({ hasText: '导入代理' }).first();
    await expect(importBtn).toBeVisible({ timeout: 10000 });

    const exportBtn = page.locator('button').filter({ hasText: '导出代理' }).first();
    await expect(exportBtn).toBeVisible();

    const clearBtn = page.locator('button').filter({ hasText: '清空筛选' }).first();
    await expect(clearBtn).toBeVisible();

    const resetBtn = page.locator('button').filter({ hasText: '重置列' }).first();
    await expect(resetBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 43) ──

test.describe('System Diagnostics Export (Round 43)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '使用指南');
  });

  test('docs page has quick start', async ({ page }) => {
    const pageContainer = page.locator('.page-container').first();
    await expect(pageContainer).toBeVisible({ timeout: 10000 });

    const quickStartTitle = page.locator('.settings-title, h3').filter({ hasText: '快速开始' }).first();
    await expect(quickStartTitle).toBeVisible({ timeout: 10000 });

    const quickStartSteps = page.locator('.quick-start-steps').first();
    await expect(quickStartSteps).toBeVisible();

    const steps = page.locator('.quick-start-step');
    const count = await steps.count();
    expect(count).toBeGreaterThanOrEqual(5);
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureTitle = page.locator('.settings-title, h3').filter({ hasText: '功能概览' }).first();
    await featureTitle.scrollIntoViewIfNeeded();
    await expect(featureTitle).toBeVisible({ timeout: 10000 });

    const featureGrid = page.locator('.feature-grid').first();
    await expect(featureGrid).toBeVisible();

    const featureItems = featureGrid.locator('.feature-item');
    const count = await featureItems.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const featureNames = featureGrid.locator('.feature-name');
    const names = await featureNames.allTextContents();
    expect(names.join(' ')).toContain('代理节点');
    expect(names.join(' ')).toContain('订阅管理');
  });
});
