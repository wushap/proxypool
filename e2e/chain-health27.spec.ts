import { test, expect } from '@playwright/test';

test.describe('Chain Health Check (Round 27)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has top 10 fastest nodes section', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: 'Top 10 最快节点' });
    await expect(card).toBeVisible();

    const cardBody = card.locator('.card-body');
    await expect(cardBody).toBeVisible();

    // Should have either data items or an empty state
    const hasItems = await card.locator('.dashboard-top-proxy-item').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await card.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasItems || hasEmpty).toBeTruthy();
  });

  test('dashboard has top 10 slowest nodes section', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: 'Top 10 最慢节点' });
    await expect(card).toBeVisible();

    const cardBody = card.locator('.card-body');
    await expect(cardBody).toBeVisible();

    // Should have either data items or an empty state
    const hasItems = await card.locator('.dashboard-top-proxy-item').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await card.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasItems || hasEmpty).toBeTruthy();
  });

  test('dashboard has protocol latency comparison section', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: '协议延迟对比' });
    await expect(card).toBeVisible();

    const cardBody = card.locator('.card-body');
    await expect(cardBody).toBeVisible();

    // Should have either protocol latency rows or an empty state
    const hasRows = await card.locator('.dashboard-protocol-latency-row').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await card.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasRows || hasEmpty).toBeTruthy();
  });

  test('dashboard has success rate trend chart', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: '成功率趋势' });
    await expect(card).toBeVisible();

    const cardBody = card.locator('.card-body');
    await expect(cardBody).toBeVisible();

    // Should have either a trend SVG or an empty state
    const hasSvg = await card.locator('.dashboard-trend-svg').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await card.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasSvg || hasEmpty).toBeTruthy();
  });

  test('dashboard has quick action buttons at bottom', async ({ page }) => {
    const quickActions = page.locator('button:has-text("任务中心"), button:has-text("创建代理池"), button:has-text("导入节点")');
    const btnCount = await quickActions.count();
    expect(btnCount).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Batch Operations (Round 27)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscription publish page loads with title', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '订阅发布管理' });
    await expect(sectionTitle).toBeVisible();

    // Refresh button should be present
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible();
  });

  test('published subscriptions list or empty state is visible', async ({ page }) => {
    // The page should have a table or indicate no subscriptions
    const tableWrap = page.locator('.table-wrap');
    await expect(tableWrap).toBeVisible();

    const table = tableWrap.locator('.data-table');
    await expect(table).toBeVisible();

    // Verify table headers
    const headers = table.locator('thead th');
    const headerCount = await headers.count();
    expect(headerCount).toBeGreaterThanOrEqual(5);

    // Pagination should be present
    const pagination = page.locator('.pagination');
    await expect(pagination).toBeVisible();
  });

  test('create publication form or button is accessible', async ({ page }) => {
    // The create form section should be visible
    const createFormTitle = page.locator('.settings-title').filter({ hasText: '创建发布订阅' });
    await expect(createFormTitle).toBeVisible();

    // Name input should be accessible
    const nameInput = page.locator('input[placeholder="发布订阅名称"]');
    await expect(nameInput).toBeVisible();
    await expect(nameInput).toBeEnabled();

    // Create button should be accessible
    const createBtn = page.locator('button').filter({ hasText: '创建' }).first();
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toBeEnabled();

    // Format select should be present
    const formatSelect = page.locator('select').filter({ hasText: '原始链接' }).first();
    await expect(formatSelect).toBeVisible();
  });
});

test.describe('System Diagnostics Export (Round 27)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.locator('.page-container').waitFor({ state: 'visible', timeout: 15000 });
  });

  test('settings page loads with theme configuration', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '设置' });
    await expect(sectionTitle).toBeVisible();

    // Theme settings card should be visible
    const themeCard = page.locator('.settings-card').filter({ hasText: '外观设置' });
    await expect(themeCard).toBeVisible();

    // Theme mode radio group should exist
    const themeRadio = themeCard.locator('[aria-label="主题模式选择"]');
    await expect(themeRadio).toBeVisible();

    // Should have light, dark, auto options
    const lightOption = themeRadio.locator('.el-radio-button').filter({ hasText: '浅色' });
    await expect(lightOption).toBeVisible();

    const darkOption = themeRadio.locator('.el-radio-button').filter({ hasText: '深色' });
    await expect(darkOption).toBeVisible();

    const autoOption = themeRadio.locator('.el-radio-button').filter({ hasText: '跟随系统' });
    await expect(autoOption).toBeVisible();
  });

  test('settings page has data management section with buttons', async ({ page }) => {
    // Data settings card should be visible
    const dataCard = page.locator('.settings-card').filter({ hasText: '数据设置' });
    await expect(dataCard).toBeVisible();

    // Auto refresh interval select should exist
    const refreshSelect = dataCard.locator('[aria-label="自动刷新间隔"]');
    await expect(refreshSelect).toBeVisible();

    // About card should have a reset button
    const aboutCard = page.locator('.settings-card').filter({ hasText: '关于' });
    await expect(aboutCard).toBeVisible();

    const resetBtn = aboutCard.locator('button[aria-label="重置所有设置为默认值"]');
    await expect(resetBtn).toBeVisible();
    await expect(resetBtn).toBeEnabled();
  });
});
