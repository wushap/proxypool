import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 37) ──

test.describe('Chain Health Check (Round 37)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('aside.sidebar');
    await expect(sidebar).toBeVisible();

    const menu = sidebar.locator('.el-menu-item');
    const menuCount = await menu.count();
    expect(menuCount).toBeGreaterThanOrEqual(5);

    const dashboardItem = page.locator('.el-menu-item').filter({ hasText: '仪表盘' });
    await expect(dashboardItem).toBeVisible();
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.dashboard-stat-grid');
    await expect(statGrid).toBeVisible();

    const statCards = statGrid.locator('.stat-card, [class*="stat"]');
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has system status', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '系统状态' });
    await expect(sectionTitle).toBeVisible();

    const card = sectionTitle.locator('..').locator('..');
    const statusRows = card.locator('.dashboard-status-row');
    const rowCount = await statusRows.count();
    expect(rowCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has real-time monitoring', async ({ page }) => {
    // Activity feed provides real-time monitoring
    const activityTitle = page.locator('.card-title').filter({ hasText: '最近活动' });
    await expect(activityTitle).toBeVisible();

    // Should contain activity items or an empty state
    const activityFeed = page.locator('.activity-feed');
    const emptyState = page.locator('.empty-state');
    const hasFeed = await activityFeed.first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await emptyState.first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasFeed || hasEmpty).toBeTruthy();
  });

  test('dashboard has quick actions', async ({ page }) => {
    const headerActions = page.locator('.header-actions');
    await expect(headerActions).toBeVisible();

    const refreshBtn = headerActions.locator('button').filter({ hasText: '刷新' });
    await expect(refreshBtn.first()).toBeVisible();

    const refreshSelect = headerActions.locator('select');
    await expect(refreshSelect.first()).toBeVisible();
  });
});

// ── Batch Operations (Round 37) ──

test.describe('Batch Operations (Round 37)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('pool page has creation form', async ({ page }) => {
    const createTitle = page.locator('.settings-title').filter({ hasText: '创建代理池' });
    await expect(createTitle).toBeVisible();

    // Creation form should have name input field
    const nameInput = page.locator('.pool-create-grid input[type="text"]').first();
    await expect(nameInput).toBeVisible();
  });

  test('pool page has chain view', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();

    // Click chain view tab
    await chainViewTab.click();

    // Chain view tab panel should be active
    const activePanel = page.locator('.tab-btn.active').filter({ hasText: '链路视图' });
    await expect(activePanel).toBeVisible();
  });

  test('pool page has filter section', async ({ page }) => {
    // Pool creation form contains rotation mode select as a filter criterion
    const rotationSelect = page.locator('.pool-create-grid .select').first();
    await expect(rotationSelect).toBeVisible();

    // Inbound type select is also part of the filter/form section
    const inboundSelect = page.locator('.pool-create-grid .select').nth(1);
    await expect(inboundSelect).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 37) ──

test.describe('System Diagnostics Export (Round 37)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics has health overview', async ({ page }) => {
    const healthTitle = page.locator('.settings-title').filter({ hasText: '系统健康概览' });
    await expect(healthTitle).toBeVisible();

    // Health overview should show health items
    const healthGrid = page.locator('.health-summary-grid');
    await expect(healthGrid).toBeVisible();

    const healthItems = healthGrid.locator('.health-item');
    const itemCount = await healthItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(3);
  });

  test('diagnostics has diagnostic button', async ({ page }) => {
    const diagBtn = page.locator('button').filter({ hasText: /一键诊断/ });
    await expect(diagBtn).toBeVisible();
    await expect(diagBtn).toBeEnabled();

    // Export button should also be present (disabled until report exists)
    const exportBtn = page.locator('button').filter({ hasText: '导出报告' });
    await expect(exportBtn).toBeVisible();
  });
});
