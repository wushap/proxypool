import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 57) ──

test.describe('Chain Health Check (Round 57)', () => {
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

  test('dashboard has real-time monitoring', async ({ page }) => {
    const monitoringCard = page.locator('.card').filter({ hasText: '实时监控' }).first();
    await monitoringCard.scrollIntoViewIfNeeded();
    await expect(monitoringCard).toBeVisible({ timeout: 10000 });

    const cardTitle = monitoringCard.locator('.card-title').filter({ hasText: '实时监控' });
    await expect(cardTitle).toContainText('实时监控');

    const statGrids = monitoringCard.locator('.stat-grid');
    const gridCount = await statGrids.count();
    expect(gridCount).toBeGreaterThanOrEqual(1);

    const allStatCards = monitoringCard.locator('.stat-card');
    const cardCount = await allStatCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);
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

// ── Batch Operations (Round 57) ──

test.describe('Batch Operations (Round 57)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscription page has add form', async ({ page }) => {
    const nameInput = page.locator('input[placeholder="订阅名称"]').first();
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    const urlInput = page.locator('input[placeholder="订阅链接 URL"]').first();
    await expect(urlInput).toBeVisible();

    const addButton = page.locator('button').filter({ hasText: '添加订阅' }).first();
    await expect(addButton).toBeVisible();

    const testButton = page.locator('button').filter({ hasText: '测试URL' }).first();
    await expect(testButton).toBeVisible();
  });

  test('subscription page has group tabs', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible({ timeout: 15000 });

    const tabs = groupTabs.locator('button[role="tab"]');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(1);

    const allTabText = await groupTabs.textContent();
    expect(allTabText).toContain('全部');

    const newGroupBtn = groupTabs.locator('button').filter({ hasText: '新建分组' });
    await expect(newGroupBtn).toBeVisible();
  });

  test('subscription page has batch buttons', async ({ page }) => {
    const btnGroup = page.locator('.section-header .btn-group').first();
    await expect(btnGroup).toBeVisible({ timeout: 10000 });

    const refreshAllBtn = btnGroup.locator('button').filter({ hasText: '刷新全部' });
    await expect(refreshAllBtn).toBeVisible();

    const deleteUnavailableBtn = btnGroup.locator('button').filter({ hasText: '删除不可用' });
    await expect(deleteUnavailableBtn).toBeVisible();

    const refreshListBtn = btnGroup.locator('button').filter({ hasText: '刷新列表' });
    await expect(refreshListBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 57) ──

test.describe('System Diagnostics Export (Round 57)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('config history has save snapshot button', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '配置历史' }).first();
    await expect(sectionTitle).toBeVisible({ timeout: 10000 });

    const saveButton = page.locator('button').filter({ hasText: '保存快照' }).first();
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeEnabled();
  });

  test('config history has empty state or snapshot list', async ({ page }) => {
    const emptyState = page.locator('.empty-state-title').filter({ hasText: '暂无配置快照' }).first();
    const snapshotList = page.locator('.config-snapshot-list').first();

    const hasEmpty = await emptyState.isVisible().catch(() => false);
    const hasList = await snapshotList.isVisible().catch(() => false);
    expect(hasEmpty || hasList).toBeTruthy();
  });
});
