import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 42) ──

test.describe('Chain Health Check (Round 42)', () => {
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
    const monitoringTitle = page.locator('.card-title').filter({ hasText: '实时监控' });
    await monitoringTitle.scrollIntoViewIfNeeded();
    await expect(monitoringTitle).toBeVisible({ timeout: 10000 });

    const monitoringCard = monitoringTitle.locator('..').first();
    const statGrid = monitoringCard.locator('.stat-grid');
    await expect(statGrid.first()).toBeVisible({ timeout: 10000 });

    const statCards = monitoringCard.locator('.stat-card');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);
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
  });
});

// ── Batch Operations (Round 42) ──

test.describe('Batch Operations (Round 42)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('pool page has creation form', async ({ page }) => {
    const createTitle = page.locator('.settings-title').filter({ hasText: '创建代理池' }).first();
    await createTitle.scrollIntoViewIfNeeded();
    await expect(createTitle).toBeVisible({ timeout: 10000 });

    const nameInput = page.locator('input[placeholder="如 exit-us-01"]');
    await expect(nameInput).toBeVisible();

    const createBtn = page.locator('button').filter({ hasText: '创建代理池' }).first();
    await expect(createBtn).toBeVisible();
  });

  test('pool page has chain view', async ({ page }) => {
    const chainViewTab = page.locator('.tabs .tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible({ timeout: 10000 });
    await chainViewTab.click();

    await page.locator('.chain-visualization, .chain-flow').first().waitFor({ state: 'visible', timeout: 15000 });

    const sectionHeader = page.locator('.section-header').filter({ hasText: '链路可视化' }).first();
    await expect(sectionHeader).toBeVisible({ timeout: 10000 });
  });

  test('pool page has filter section', async ({ page }) => {
    const filterHeader = page.locator('.form-section-header').filter({ hasText: '过滤条件' }).first();
    await filterHeader.scrollIntoViewIfNeeded();
    await expect(filterHeader).toBeVisible({ timeout: 10000 });

    await filterHeader.click();

    const advancedFilters = page.locator('.advanced-filters').first();
    await expect(advancedFilters).toBeVisible({ timeout: 10000 });

    const filterText = await advancedFilters.textContent();
    expect(filterText).toContain('ChatGPT');
    expect(filterText).toContain('家宽');
  });
});

// ── System Diagnostics Export (Round 42) ──

test.describe('System Diagnostics Export (Round 42)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics has health overview', async ({ page }) => {
    const healthTitle = page.locator('.settings-title').filter({ hasText: '系统健康概览' }).first();
    await expect(healthTitle).toBeVisible({ timeout: 10000 });

    const healthGrid = page.locator('.health-summary-grid').first();
    await expect(healthGrid).toBeVisible();

    const healthItems = healthGrid.locator('.health-item');
    const count = await healthItems.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const labels = healthGrid.locator('.health-label');
    const labelTexts = await labels.allTextContents();
    expect(labelTexts).toContain('后端进程');
    expect(labelTexts).toContain('网关服务');
  });

  test('diagnostics has diagnostic button', async ({ page }) => {
    const diagBtn = page.locator('button').filter({ hasText: '一键诊断' });
    await expect(diagBtn).toBeVisible({ timeout: 10000 });
    await expect(diagBtn).toBeEnabled();

    const exportBtn = page.locator('button').filter({ hasText: '导出报告' });
    await expect(exportBtn).toBeVisible();
  });
});
