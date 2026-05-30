import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 54) ──

test.describe('Chain Health Check (Round 54)', () => {
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

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await protocolCard.scrollIntoViewIfNeeded();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    // Verify card has either chart content or empty state
    const donutWrapper = protocolCard.locator('.dashboard-donut-wrapper');
    const emptyState = protocolCard.locator('.empty-state');
    const hasChart = await donutWrapper.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasChart || hasEmpty).toBe(true);
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

// ── Batch Operations (Round 54) ──

test.describe('Batch Operations (Round 54)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('pool page has creation form', async ({ page }) => {
    const createFormTitle = page.locator('.settings-title').filter({ hasText: '创建代理池' }).first();
    await createFormTitle.scrollIntoViewIfNeeded();
    await expect(createFormTitle).toBeVisible({ timeout: 10000 });

    // Verify form fields exist
    const nameInput = page.locator('.pool-create-grid .input').first();
    await expect(nameInput).toBeVisible();

    // Verify create button exists
    const createButton = page.locator('button').filter({ hasText: '创建代理池' }).first();
    await expect(createButton).toBeVisible({ timeout: 10000 });
  });

  test('pool page has chain view', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' }).first();
    await expect(chainViewTab).toBeVisible({ timeout: 10000 });
    await chainViewTab.click();

    const chainViewSection = page.locator('.chain-visualization, .chain-flow, .section-divider').filter({ hasText: '链路可视化' }).first();
    await expect(chainViewSection).toBeVisible({ timeout: 15000 });

    // Verify chain visualization has entry point or empty state
    const chainContent = page.locator('.chain-node-entry, .chain-flow');
    await expect(chainContent.first()).toBeVisible({ timeout: 10000 });
  });

  test('pool page has filter section', async ({ page }) => {
    const hasFilter = await page.locator('text=过滤条件').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasFilter).toBeTruthy();
  });
});

// ── System Diagnostics Export (Round 54) ──

test.describe('System Diagnostics Export (Round 54)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics has health overview', async ({ page }) => {
    const healthTitle = page.locator('.settings-title').filter({ hasText: '系统健康概览' }).first();
    await healthTitle.scrollIntoViewIfNeeded();
    await expect(healthTitle).toBeVisible({ timeout: 10000 });

    const healthGrid = page.locator('.health-summary-grid').first();
    await expect(healthGrid).toBeVisible();

    const healthItems = healthGrid.locator('.health-item');
    const count = await healthItems.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const gridText = await healthGrid.textContent();
    expect(gridText).toContain('后端进程');
    expect(gridText).toContain('网关服务');
    expect(gridText).toContain('代理池');
    expect(gridText).toContain('代理节点');
  });

  test('diagnostics has diagnostic button', async ({ page }) => {
    const diagnosticBtn = page.locator('button').filter({ hasText: '一键诊断' }).first();
    await expect(diagnosticBtn).toBeVisible({ timeout: 10000 });
    await expect(diagnosticBtn).toBeEnabled();

    // Also verify export button exists (disabled before running diagnostics)
    const exportBtn = page.locator('button').filter({ hasText: '导出报告' }).first();
    await expect(exportBtn).toBeVisible({ timeout: 10000 });
  });
});
