import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 58) ──

test.describe('Chain Health Check (Round 58)', () => {
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

    const cardTitle = protocolCard.locator('.card-title, h3').filter({ hasText: '协议分布' });
    await expect(cardTitle).toContainText('协议分布');

    const content = await protocolCard.textContent();
    expect(content).toContain('协议分布');
  });

  test('dashboard has quick actions', async ({ page }) => {
    const quickActionsTitle = page.locator('h3.card-title').filter({ hasText: '快速操作' }).first();
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
    expect(actionText).toContain('订阅管理');
    expect(actionText).toContain('代理节点');
  });
});

// ── Batch Operations (Round 58) ──

test.describe('Batch Operations (Round 58)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('proxy nodes page has data table', async ({ page }) => {
    const statusBar = page.locator('.status-bar').first();
    await expect(statusBar).toBeVisible({ timeout: 15000 });

    const statusText = await statusBar.textContent();
    expect(statusText).toContain('显示');
    expect(statusText).toContain('总节点');

    const pagination = page.locator('.pagination').first();
    await expect(pagination).toBeVisible({ timeout: 10000 });
  });

  test('proxy nodes page has filter inputs', async ({ page }) => {
    const filterPanel = page.locator('.filter-panel').first();
    await expect(filterPanel).toBeVisible({ timeout: 10000 });

    const toggle = filterPanel.locator('.filter-panel-toggle');
    await expect(toggle).toBeVisible();
    await expect(toggle).toContainText('高级筛选');

    await toggle.click();

    const filterBody = filterPanel.locator('.filter-panel-body');
    await expect(filterBody).toBeVisible({ timeout: 5000 });

    const filterFields = filterBody.locator('.filter-panel-field');
    const fieldCount = await filterFields.count();
    expect(fieldCount).toBeGreaterThanOrEqual(4);
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    const sectionHeader = page.locator('.section-header').first();
    await expect(sectionHeader).toBeVisible({ timeout: 10000 });

    const btnGroup = sectionHeader.locator('.btn-group');
    await expect(btnGroup).toBeVisible();

    const buttons = btnGroup.locator('button, .el-button');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(3);

    const btnText = await btnGroup.textContent();
    expect(btnText).toContain('导入代理');
    expect(btnText).toContain('导出代理');
    expect(btnText).toContain('清空筛选');
  });
});

// ── System Diagnostics Export (Round 58) ──

test.describe('System Diagnostics Export (Round 58)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics has health overview', async ({ page }) => {
    const healthCard = page.locator('.card').filter({ hasText: '系统健康概览' }).first();
    await expect(healthCard).toBeVisible({ timeout: 15000 });

    const healthGrid = healthCard.locator('.health-summary-grid');
    await expect(healthGrid).toBeVisible();

    const healthItems = healthGrid.locator('.health-item');
    const itemCount = await healthItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(4);

    const gridText = await healthGrid.textContent();
    expect(gridText).toContain('后端进程');
    expect(gridText).toContain('网关服务');
    expect(gridText).toContain('代理池');
    expect(gridText).toContain('代理节点');
  });

  test('diagnostics has diagnostic button', async ({ page }) => {
    const sectionHeader = page.locator('.section-header').first();
    await expect(sectionHeader).toBeVisible({ timeout: 10000 });

    const diagButton = sectionHeader.locator('button').filter({ hasText: '一键诊断' }).first();
    await expect(diagButton).toBeVisible();
    await expect(diagButton).toBeEnabled();

    const exportButton = sectionHeader.locator('button').filter({ hasText: '导出报告' }).first();
    await expect(exportButton).toBeVisible();
  });
});
