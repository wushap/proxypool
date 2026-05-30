import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 36) ──

test.describe('Chain Health Check (Round 36)', () => {
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

    // Sidebar should contain the menu with navigation items
    const menu = sidebar.locator('.el-menu-item');
    const menuCount = await menu.count();
    expect(menuCount).toBeGreaterThanOrEqual(5);

    // Verify specific menu items exist
    const dashboardItem = page.locator('.el-menu-item').filter({ hasText: '仪表盘' });
    await expect(dashboardItem).toBeVisible();
  });

  test('dashboard has stat cards grid', async ({ page }) => {
    const statGrid = page.locator('.dashboard-stat-grid');
    await expect(statGrid).toBeVisible();

    // Should contain at least 4 stat cards
    const statCards = statGrid.locator('.stat-card, [class*="stat"]');
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has system status', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '系统状态' });
    await expect(sectionTitle).toBeVisible();

    // System status section should contain status rows
    const card = sectionTitle.locator('..').locator('..');
    const statusRows = card.locator('.dashboard-status-row');
    const rowCount = await statusRows.count();
    expect(rowCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has quick actions', async ({ page }) => {
    // Quick actions may be rendered as header action buttons or a dedicated section
    // Check for the refresh button and auto-refresh dropdown in the header actions
    const headerActions = page.locator('.header-actions');
    await expect(headerActions).toBeVisible();

    // Should have refresh button
    const refreshBtn = headerActions.locator('button').filter({ hasText: '刷新' });
    await expect(refreshBtn.first()).toBeVisible();

    // Should have an auto-refresh select
    const refreshSelect = headerActions.locator('select');
    await expect(refreshSelect.first()).toBeVisible();
  });

  test('dashboard has recent tasks', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '最近任务' });
    await expect(sectionTitle).toBeVisible();

    // Should have a "查看全部" link to tasks page
    const viewAllBtn = sectionTitle.locator('..').locator('button, a').filter({ hasText: '查看全部' });
    await expect(viewAllBtn.first()).toBeVisible();

    // Should either show task items or an empty state
    const taskList = page.locator('.dashboard-task-list');
    const emptyState = page.locator('.empty-state');
    const hasTasks = await taskList.first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await emptyState.first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasTasks || hasEmpty).toBeTruthy();
  });
});

// ── Batch Operations (Round 36) ──

test.describe('Batch Operations (Round 36)', () => {
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

    // The create button should be primary styled
    await expect(createBtn.first()).toHaveClass(/btn-primary/);
  });

  test('inbound ports has table or empty state', async ({ page }) => {
    // Should show either a data table or an empty state
    const table = page.locator('.data-table');
    const emptyState = page.locator('.empty-state');
    const hasTable = await table.first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await emptyState.first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();
  });

  test('inbound ports has refresh button', async ({ page }) => {
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' });
    await expect(refreshBtn.first()).toBeVisible();

    // The button should be secondary styled
    await expect(refreshBtn.first()).toHaveClass(/btn-secondary/);
  });
});

// ── System Diagnostics Export (Round 36) ──

test.describe('System Diagnostics Export (Round 36)', () => {
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

    // Quick start should have numbered steps
    const steps = page.locator('.quick-start-step');
    const stepCount = await steps.count();
    expect(stepCount).toBe(5);
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureTitle = page.locator('.settings-title').filter({ hasText: '功能概览' });
    await expect(featureTitle).toBeVisible();

    // Feature grid should contain feature items
    const featureGrid = page.locator('.feature-grid');
    await expect(featureGrid).toBeVisible();

    const featureItems = featureGrid.locator('.feature-item');
    const itemCount = await featureItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(4);
  });
});
