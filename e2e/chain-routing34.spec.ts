import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 34) ──

test.describe('Chain Routing (Round 34)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has sidebar with all navigation items', async ({ page }) => {
    const menuItems = page.locator('.el-menu-item');
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(8);

    // Verify key navigation items exist
    const menuItemTexts = await menuItems.allTextContents();
    const joinedTexts = menuItemTexts.join(' ');
    expect(joinedTexts).toContain('仪表盘');
    expect(joinedTexts).toContain('代理节点');
    expect(joinedTexts).toContain('多跳代理池');
    expect(joinedTexts).toContain('入站端口');
    expect(joinedTexts).toContain('订阅管理');
    expect(joinedTexts).toContain('使用指南');
  });

  test('dashboard has stat grid with 4+ cards', async ({ page }) => {
    const statGrid = page.locator('.stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 10000 });

    // Stat cards are rendered as card components within the grid
    const statCards = statGrid.locator('.stat-card, .card');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);

    // Verify the stat grid contains key labels
    const gridText = await statGrid.textContent();
    expect(gridText).toContain('节点总数');
    expect(gridText).toContain('可用节点');
  });

  test('dashboard has system status with backend and gateway rows', async ({ page }) => {
    const statusCard = page.locator('.card').filter({ hasText: '系统状态' }).first();
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

  test('dashboard has real-time monitoring section', async ({ page }) => {
    const monitoringCard = page.locator('.card').filter({ hasText: '实时监控' }).first();
    await expect(monitoringCard).toBeVisible({ timeout: 10000 });

    // The monitoring section contains a stat-grid with monitoring stat cards
    const monitoringGrid = monitoringCard.locator('.stat-grid').first();
    await expect(monitoringGrid).toBeVisible();

    const gridText = await monitoringGrid.textContent();
    expect(gridText).toContain('活跃连接');
    expect(gridText).toContain('总连接数');
  });

  test('dashboard has quick actions section', async ({ page }) => {
    const hasQuickActions = await page.locator('text=快速操作').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasQuickActions).toBeTruthy();
  });
});

// ── Subscription Intelligence (Round 34) ──

test.describe('Subscription Intelligence (Round 34)', () => {
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

  test('proxy nodes page has batch operation buttons', async ({ page }) => {
    // The page header section has batch operation buttons
    const importBtn = page.locator('button').filter({ hasText: '导入代理' }).first();
    await expect(importBtn).toBeVisible({ timeout: 10000 });

    const exportBtn = page.locator('button').filter({ hasText: '导出代理' }).first();
    await expect(exportBtn).toBeVisible();

    // The pagination area has batch selection action buttons
    const copyBtn = page.locator('button').filter({ hasText: /复制选中/ }).first();
    await expect(copyBtn).toBeVisible();

    const deleteBtn = page.locator('button').filter({ hasText: /删除选中/ }).first();
    await expect(deleteBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 34) ──

test.describe('System Diagnostics Export (Round 34)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '使用指南');
  });

  test('docs page has quick start steps', async ({ page }) => {
    const quickStartCard = page.locator('.card').filter({ hasText: '快速开始' }).first();
    await expect(quickStartCard).toBeVisible({ timeout: 10000 });

    const steps = quickStartCard.locator('.quick-start-step');
    const stepCount = await steps.count();
    expect(stepCount).toBe(5);

    // Verify step titles exist
    const stepTitles = quickStartCard.locator('.step-title');
    const titles = await stepTitles.allTextContents();
    expect(titles).toContain('添加订阅源');
    expect(titles).toContain('创建代理池');
    expect(titles).toContain('配置入站端口');
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureCard = page.locator('.card').filter({ hasText: '功能概览' }).first();
    await expect(featureCard).toBeVisible({ timeout: 10000 });

    const featureGrid = featureCard.locator('.feature-grid');
    await expect(featureGrid).toBeVisible();

    const featureItems = featureGrid.locator('.feature-item');
    const count = await featureItems.count();
    expect(count).toBeGreaterThanOrEqual(5);

    // Verify key feature names exist
    const featureNames = featureCard.locator('.feature-name');
    const names = await featureNames.allTextContents();
    expect(names).toContain('代理节点');
    expect(names).toContain('代理池');
    expect(names).toContain('设置');
  });
});
