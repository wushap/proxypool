import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 55) ──

test.describe('Chain Health Check (Round 55)', () => {
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
    const monitoringTitle = page.locator('h3.card-title').filter({ hasText: '实时监控' }).first();
    await monitoringTitle.scrollIntoViewIfNeeded();
    await expect(monitoringTitle).toBeVisible({ timeout: 10000 });

    // Verify auto-refresh control exists nearby
    const refreshSelect = page.locator('select[aria-label="自动刷新间隔"]').first();
    await expect(refreshSelect).toBeVisible({ timeout: 10000 });
  });

  test('dashboard has quick actions', async ({ page }) => {
    const quickActionsTitle = page.locator('h3.card-title').filter({ hasText: '快速操作' }).filter({ hasNotText: '历史' }).first();
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

// ── Batch Operations (Round 55) ──

test.describe('Batch Operations (Round 55)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscription page has add form', async ({ page }) => {
    // The add subscription form has a name input and URL input
    const nameInput = page.locator('input[aria-label="订阅名称"]').first();
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    const urlInput = page.locator('input[aria-label="订阅链接URL"]').first();
    await expect(urlInput).toBeVisible();

    const addButton = page.locator('button[aria-label="添加新订阅"]').first();
    await expect(addButton).toBeVisible();
    await expect(addButton).toBeEnabled();
  });

  test('subscription page has group tabs', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs').first();
    await expect(groupTabs).toBeVisible({ timeout: 15000 });

    const tabButtons = groupTabs.locator('button[role="tab"]');
    const count = await tabButtons.count();
    expect(count).toBeGreaterThanOrEqual(1);

    // Verify there is a "new group" button
    const newGroupBtn = page.locator('button[aria-label="新建订阅分组"]').first();
    await expect(newGroupBtn).toBeVisible();
  });

  test('subscription page has batch buttons', async ({ page }) => {
    // Verify the top-level batch action buttons are present
    const refreshAllBtn = page.locator('button[aria-label="刷新所有订阅"]').first();
    await expect(refreshAllBtn).toBeVisible({ timeout: 10000 });

    const refreshListBtn = page.locator('button[aria-label="刷新订阅列表"]').first();
    await expect(refreshListBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 55) ──

test.describe('System Diagnostics Export (Round 55)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('config history has save snapshot button', async ({ page }) => {
    const saveBtn = page.locator('button').filter({ hasText: '保存快照' }).first();
    await expect(saveBtn).toBeVisible({ timeout: 10000 });

    // Verify the section title
    const title = page.locator('.section-title').filter({ hasText: '配置历史' }).first();
    await expect(title).toBeVisible();
  });

  test('config history has empty state or snapshot list', async ({ page }) => {
    // Either an empty state or a list of snapshots should be present
    const emptyState = page.locator('.empty-state, [class*="empty"]').first();
    const snapshotList = page.locator('.config-snapshot-list').first();

    const hasEmpty = await emptyState.isVisible().catch(() => false);
    const hasList = await snapshotList.isVisible().catch(() => false);
    expect(hasEmpty || hasList).toBe(true);
  });
});
