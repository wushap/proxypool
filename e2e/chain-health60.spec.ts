import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 60) ──

test.describe('Chain Health Check (Round 60)', () => {
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
    expect(joined).toContain('入站端口');
    expect(joined).toContain('订阅管理');
    expect(joined).toContain('任务中心');
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
    expect(labels).toContain('健康代理池');
  });

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await protocolCard.scrollIntoViewIfNeeded();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    const cardTitle = protocolCard.locator('.card-title');
    await expect(cardTitle).toContainText('协议分布');

    // Either donut chart with protocol data or empty state is shown
    const hasDonut = await protocolCard.locator('.dashboard-donut-wrapper').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await protocolCard.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasDonut || hasEmpty).toBeTruthy();
  });

  test('dashboard has quick actions', async ({ page }) => {
    const hasQuickActions = await page.locator('text=快速操作').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasQuickActions).toBeTruthy();
  });
});

// ── Batch Operations (Round 60) ──

test.describe('Batch Operations (Round 60)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('pool page has creation form', async ({ page }) => {
    const createSection = page.locator('.settings-title').filter({ hasText: '创建代理池' }).first();
    await expect(createSection).toBeVisible({ timeout: 10000 });

    const nameInput = page.locator('input[placeholder*="exit-us"]').first();
    await expect(nameInput).toBeVisible();

    const listenInput = page.locator('input[placeholder="0.0.0.0"]').first();
    await expect(listenInput).toBeVisible();

    const inboundSelect = page.locator('select').filter({ hasText: 'HTTP' }).first();
    await expect(inboundSelect).toBeVisible();
  });

  test('pool page has chain view', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible({ timeout: 10000 });
    await chainViewTab.click();

    const chainPanel = page.locator('.tab-panel').filter({ hasText: '链路可视化' }).first();
    await expect(chainPanel).toBeVisible({ timeout: 10000 });

    const diagBtn = page.locator('button').filter({ hasText: '链路诊断' }).first();
    await expect(diagBtn).toBeVisible();
  });

  test('pool page has filter section', async ({ page }) => {
    const hasFilter = await page.locator('text=过滤条件').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasFilter).toBeTruthy();
  });
});

// ── System Diagnostics Export (Round 60) ──

test.describe('System Diagnostics Export (Round 60)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics has health overview', async ({ page }) => {
    const healthCard = page.locator('.card').filter({ hasText: '系统健康概览' }).first();
    await expect(healthCard).toBeVisible({ timeout: 10000 });

    const healthGrid = healthCard.locator('.health-summary-grid');
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
    const diagBtn = page.locator('button').filter({ hasText: '一键诊断' }).first();
    await expect(diagBtn).toBeVisible({ timeout: 10000 });
    await expect(diagBtn).toBeEnabled();

    const exportBtn = page.locator('button').filter({ hasText: '导出报告' }).first();
    await expect(exportBtn).toBeVisible();
  });
});
