import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 49) ──

test.describe('Chain Health Check (Round 49)', () => {
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
    const refreshSelect = page.locator('select[aria-label="自动刷新间隔"]');
    await expect(refreshSelect).toBeVisible();

    const options = refreshSelect.locator('option');
    const optionCount = await options.count();
    expect(optionCount).toBeGreaterThanOrEqual(4);

    const refreshBtn = page.locator('button[aria-label="刷新仪表盘数据"]');
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();
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

// ── Batch Operations (Round 49) ──

test.describe('Batch Operations (Round 49)', () => {
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

// ── System Diagnostics Export (Round 49) ──

test.describe('System Diagnostics Export (Round 49)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('docs page has quick start', async ({ page }) => {
    const quickStartTitle = page.locator('.settings-title').filter({ hasText: '快速开始' });
    await expect(quickStartTitle).toBeVisible();

    const steps = page.locator('.quick-start-step');
    const stepCount = await steps.count();
    expect(stepCount).toBeGreaterThanOrEqual(4);
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureGrid = page.locator('.feature-grid');
    await expect(featureGrid).toBeVisible();

    const featureItems = featureGrid.locator('.feature-item');
    const itemCount = await featureItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(5);
  });
});
