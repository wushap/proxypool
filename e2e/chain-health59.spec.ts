import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 59) ──

test.describe('Chain Health Check (Round 59)', () => {
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

  test('dashboard has real-time monitoring', async ({ page }) => {
    const refreshSelect = page.locator('select[aria-label="自动刷新间隔"]');
    await expect(refreshSelect).toBeVisible({ timeout: 10000 });

    const options = refreshSelect.locator('option');
    const optionCount = await options.count();
    expect(optionCount).toBeGreaterThanOrEqual(4);

    const refreshBtn = page.locator('button[aria-label="刷新仪表盘数据"]');
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();
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

// ── Batch Operations (Round 59) ──

test.describe('Batch Operations (Round 59)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('inbound ports has create button', async ({ page }) => {
    const createBtn = page.locator('button[aria-label="创建新的入站端口"]');
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toBeEnabled();
    await expect(createBtn).toHaveText('创建端口');
  });

  test('inbound ports has table or empty state', async ({ page }) => {
    const hasTable = await page.locator('.data-table').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();
  });

  test('inbound ports has refresh button', async ({ page }) => {
    const refreshBtn = page.locator('button[aria-label="刷新入站端口列表"]');
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();
    await expect(refreshBtn).toHaveText('刷新');
  });
});

// ── System Diagnostics Export (Round 59) ──

test.describe('System Diagnostics Export (Round 59)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('settings page has theme options', async ({ page }) => {
    const themeCard = page.locator('.settings-title').filter({ hasText: '外观设置' }).first();
    await expect(themeCard).toBeVisible();

    const themeRadioGroup = page.locator('el-radio-group, [aria-label="主题模式选择"]').first();
    await expect(themeRadioGroup).toBeVisible();

    const lightBtn = page.locator('button, span, label').filter({ hasText: '浅色' }).first();
    const darkBtn = page.locator('button, span, label').filter({ hasText: '深色' }).first();
    const autoBtn = page.locator('button, span, label').filter({ hasText: '跟随系统' }).first();

    await expect(lightBtn).toBeVisible();
    await expect(darkBtn).toBeVisible();
    await expect(autoBtn).toBeVisible();
  });

  test('settings page has about section', async ({ page }) => {
    const aboutCard = page.locator('.settings-title').filter({ hasText: '关于' }).first();
    await expect(aboutCard).toBeVisible({ timeout: 10000 });

    const aboutSection = aboutCard.locator('..').first();
    const aboutText = await aboutSection.textContent();
    expect(aboutText).toContain('关于');
  });
});
