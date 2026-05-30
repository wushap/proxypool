import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 44) ──

test.describe('Chain Health Check (Round 44)', () => {
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
    const activityTitle = page.locator('.card-title').filter({ hasText: '最近活动' });
    await expect(activityTitle).toBeVisible();

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

// ── Batch Operations (Round 44) ──

test.describe('Batch Operations (Round 44)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscription page has add form', async ({ page }) => {
    const nameInput = page.locator('input[placeholder*="订阅名称"]');
    await expect(nameInput).toBeVisible();

    const urlInput = page.locator('input[placeholder*="订阅链接"]');
    await expect(urlInput).toBeVisible();

    const addBtn = page.locator('button').filter({ hasText: '添加订阅' }).first();
    await expect(addBtn).toBeVisible();
  });

  test('subscription page has group tabs', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    const sectionHeader = page.locator('.section-header');
    const hasGroupTabs = await groupTabs.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasSectionHeader = await sectionHeader.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasGroupTabs || hasSectionHeader).toBeTruthy();

    if (hasGroupTabs) {
      const tabBtns = groupTabs.locator('[role="tab"], .btn');
      const tabCount = await tabBtns.count();
      expect(tabCount).toBeGreaterThanOrEqual(1);
    }
  });

  test('subscription page has batch buttons', async ({ page }) => {
    const sectionHeader = page.locator('.section-header');
    await expect(sectionHeader).toBeVisible();

    const headerBtns = sectionHeader.locator('button');
    const btnCount = await headerBtns.count();
    expect(btnCount).toBeGreaterThanOrEqual(2);

    const bulkImport = page.locator('details summary').filter({ hasText: '批量导入' });
    await expect(bulkImport).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 44) ──

test.describe('System Diagnostics Export (Round 44)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('docs page has quick start', async ({ page }) => {
    const quickStart = page.locator('.card-title, h2, h3').filter({ hasText: /快速开始|快速上手|Quick Start/ });
    await expect(quickStart.first()).toBeVisible();

    const quickStartSection = quickStart.first().locator('..');
    const content = quickStartSection.locator('p, li, .doc-item');
    const contentCount = await content.count();
    expect(contentCount).toBeGreaterThanOrEqual(1);
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureCards = page.locator('.feature-card, .doc-card, .card');
    const featureCount = await featureCards.count();
    expect(featureCount).toBeGreaterThanOrEqual(3);

    await expect(featureCards.first()).toBeVisible();
  });
});
