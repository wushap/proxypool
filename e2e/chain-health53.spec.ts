import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 53) ──

test.describe('Chain Health Check (Round 53)', () => {
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
    expect(count).toBeGreaterThanOrEqual(8);

    const texts = await menuItems.allTextContents();
    const joined = texts.join(' ');
    expect(joined).toContain('仪表盘');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('多跳代理池');
    expect(joined).toContain('入站端口');
    expect(joined).toContain('订阅管理');
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.stat-grid.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 30000 });

    const statCards = statGrid.locator('.stat-card');
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
    expect(count).toBeGreaterThanOrEqual(4);

    const rowLabels = statusList.locator('.dashboard-status-label');
    const labels = await rowLabels.allTextContents();
    expect(labels).toContain('后端引擎');
    expect(labels).toContain('网关服务');
  });

  test('dashboard has real-time monitoring', async ({ page }) => {
    const monitoringHeading = page.locator('h3').filter({ hasText: '实时监控' }).first();
    await monitoringHeading.scrollIntoViewIfNeeded();
    await expect(monitoringHeading).toBeVisible({ timeout: 10000 });

    const monitoringSection = monitoringHeading.locator('..').first();
    const sectionText = await monitoringSection.textContent();

    // Verify key monitoring metrics are present
    expect(sectionText).toContain('活跃连接');
    expect(sectionText).toContain('总连接数');
    expect(sectionText).toContain('请求速率');
    expect(sectionText).toContain('错误率');
    expect(sectionText).toContain('网关状态');
  });

  test('dashboard has quick actions', async ({ page }) => {
    const quickActionsTitle = page.locator('h3.card-title').filter({ hasText: '快速操作' }).filter({ hasNotText: '历史' });
    await quickActionsTitle.scrollIntoViewIfNeeded();
    await expect(quickActionsTitle).toBeVisible({ timeout: 10000 });

    const quickActionsCard = quickActionsTitle.locator('..').first();
    const actionBar = quickActionsCard.locator('.action-bar');
    await expect(actionBar).toBeVisible({ timeout: 10000 });

    const buttons = actionBar.locator('button, a');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(3);

    const actionText = await actionBar.textContent();
    expect(actionText).toContain('任务中心');
    expect(actionText).toContain('代理节点');
  });
});

// ── Batch Operations (Round 53) ──

test.describe('Batch Operations (Round 53)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('inbound ports has create button', async ({ page }) => {
    const createButton = page.locator('button:has-text("创建端口")').first();
    await expect(createButton).toBeVisible({ timeout: 10000 });

    // Button should be enabled and clickable
    await expect(createButton).toBeEnabled();
  });

  test('inbound ports has table or empty state', async ({ page }) => {
    await page.locator('.data-table, .empty-state, .port-row-expandable').first().waitFor({ state: 'visible', timeout: 15000 });

    const table = page.locator('.data-table').first();
    const emptyState = page.locator('.empty-state').first();

    const hasTable = await table.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasTable || hasEmpty).toBe(true);
  });

  test('inbound ports has refresh button', async ({ page }) => {
    await page.locator('.data-table, .empty-state, .port-row-expandable').first().waitFor({ state: 'visible', timeout: 15000 });

    // Refresh is typically in the section header or pagination area
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible({ timeout: 10000 });
  });
});

// ── System Diagnostics Export (Round 53) ──

test.describe('System Diagnostics Export (Round 53)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('docs page has quick start', async ({ page }) => {
    await expect(page.locator('h2.section-title:has-text("使用指南")')).toBeVisible({ timeout: 10000 });

    const quickStartTitle = page.locator('.settings-title').filter({ hasText: '快速开始' }).first();
    await quickStartTitle.scrollIntoViewIfNeeded();
    await expect(quickStartTitle).toBeVisible({ timeout: 10000 });

    // Verify quick start has numbered steps
    const steps = page.locator('.step-number');
    const stepCount = await steps.count();
    expect(stepCount).toBeGreaterThanOrEqual(3);
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureTitle = page.locator('text=功能概览').first();
    await featureTitle.scrollIntoViewIfNeeded();
    await expect(featureTitle).toBeVisible({ timeout: 10000 });

    const featureItems = page.locator('.feature-item');
    const count = await featureItems.count();
    expect(count).toBeGreaterThanOrEqual(4);

    // Verify some feature names are present
    const featureNames = page.locator('.feature-name');
    const names = await featureNames.allTextContents();
    const joined = names.join(' ');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('代理池');
  });
});
