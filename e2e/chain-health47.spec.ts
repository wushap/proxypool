import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 47) ──

test.describe('Chain Health Check (Round 47)', () => {
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

// ── Batch Operations (Round 47) ──

test.describe('Batch Operations (Round 47)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('inbound ports has create button', async ({ page }) => {
    const createBtn = page.locator('button').filter({ hasText: '创建端口' });
    await expect(createBtn.first()).toBeVisible();
  });

  test('inbound ports has table or empty state', async ({ page }) => {
    const table = page.locator('.data-table');
    const emptyState = page.locator('.empty-state');
    const hasTable = await table.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();
  });

  test('inbound ports has refresh button', async ({ page }) => {
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' });
    await expect(refreshBtn.first()).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 47) ──

test.describe('System Diagnostics Export (Round 47)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('publish page has table or empty state', async ({ page }) => {
    const table = page.locator('.data-table');
    const emptyState = page.locator('.empty-state');
    const hasTable = await table.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();
  });

  test('publish page has create form', async ({ page }) => {
    const createTitle = page.locator('.settings-title').filter({ hasText: '创建发布订阅' });
    await expect(createTitle).toBeVisible();

    const nameInput = page.locator('input[placeholder*="发布订阅名称"]');
    await expect(nameInput).toBeVisible();

    const createBtn = page.locator('button').filter({ hasText: '创建' });
    await expect(createBtn.first()).toBeVisible();
  });
});
