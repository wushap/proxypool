import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 48) ──

test.describe('Chain Health Check (Round 48)', () => {
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

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolSection = page.locator('.card-title').filter({ hasText: '协议分布' });
    const protocolGrid = page.locator('.protocol-distribution, .protocol-grid');
    const hasTitle = await protocolSection.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasGrid = await protocolGrid.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasTitle || hasGrid).toBeTruthy();
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

// ── Batch Operations (Round 48) ──

test.describe('Batch Operations (Round 48)', () => {
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

    const nameInput = page.locator('input[placeholder*="exit-us"]');
    await expect(nameInput).toBeVisible();
  });

  test('pool page has chain view', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
  });

  test('pool page has filter section', async ({ page }) => {
    const tabs = page.locator('.tabs');
    await expect(tabs.first()).toBeVisible();

    const tabButtons = tabs.first().locator('.tab-btn');
    const tabCount = await tabButtons.count();
    expect(tabCount).toBeGreaterThanOrEqual(3);
  });
});

// ── System Diagnostics Export (Round 48) ──

test.describe('System Diagnostics Export (Round 48)', () => {
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

    const healthItems = page.locator('.health-item');
    const itemCount = await healthItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(3);
  });

  test('diagnostics has diagnostic button', async ({ page }) => {
    const diagBtn = page.locator('button').filter({ hasText: '一键诊断' });
    await expect(diagBtn).toBeVisible();
    await expect(diagBtn).toBeEnabled();
  });
});
