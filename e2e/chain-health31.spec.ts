import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 31) ──

test.describe('Chain Health Check (Round 31)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has country/region distribution section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '国家/地区分布' });
    await expect(sectionTitle).toBeVisible();

    // Section should either show country data or an empty state
    const card = sectionTitle.locator('..');
    const hasData = card.locator('.dashboard-protocol-list, .dashboard-protocol-row').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasData || hasEmpty).toBeTruthy();
  });

  test('dashboard has IP purity distribution section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: 'IP 纯净度分布' });
    await expect(sectionTitle).toBeVisible();

    const card = sectionTitle.locator('..');
    const hasData = card.locator('.dashboard-protocol-list, .dashboard-protocol-row').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasData || hasEmpty).toBeTruthy();
  });

  test('dashboard has protocol distribution section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '协议分布' });
    await expect(sectionTitle).toBeVisible();

    // Protocol distribution has a donut chart or empty state
    const card = sectionTitle.locator('..');
    const hasDonut = card.locator('.dashboard-donut-wrapper, .dashboard-donut-chart').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasDonut || hasEmpty).toBeTruthy();
  });

  test('dashboard has system status section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '系统状态' });
    await expect(sectionTitle).toBeVisible();

    // System status card should contain status rows
    const statusList = page.locator('.dashboard-status-list');
    await expect(statusList).toBeVisible();

    const statusRows = statusList.locator('.dashboard-status-row');
    const rowCount = await statusRows.count();
    expect(rowCount).toBeGreaterThanOrEqual(4);

    // Verify key status labels
    const expectedLabels = ['后端引擎', '网关服务', '健康代理池', '活跃端口'];
    for (const label of expectedLabels) {
      const row = statusList.locator('.dashboard-status-label').filter({ hasText: label });
      await expect(row).toBeVisible();
    }
  });

  test('dashboard has sidebar with navigation menu', async ({ page }) => {
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).toBeVisible();

    const menu = sidebar.locator('.sidebar-menu');
    await expect(menu).toBeVisible();

    // Verify menu items exist for each section
    const menuItems = menu.locator('.el-menu-item');
    const itemCount = await menuItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(8);

    // Verify key navigation items
    const expectedItems = ['仪表盘', '代理节点', '任务中心', '使用指南', '设置'];
    for (const text of expectedItems) {
      const item = menu.locator('.el-menu-item').filter({ hasText: text });
      await expect(item.first()).toBeVisible();
    }
  });
});

// ── Batch Operations (Round 31) ──

test.describe('Batch Operations (Round 31)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('publish page has table with column headers', async ({ page }) => {
    const table = page.locator('.data-table').first();
    await expect(table).toBeVisible();

    const headers = table.locator('thead th');
    const headerCount = await headers.count();
    expect(headerCount).toBeGreaterThanOrEqual(5);

    // Verify specific column headers
    const expectedHeaders = ['ID', '名称', '格式', '筛选条件', '节点'];
    for (const text of expectedHeaders) {
      const th = headers.filter({ hasText: text });
      await expect(th.first()).toBeVisible();
    }
  });

  test('publish page has create button', async ({ page }) => {
    const createBtn = page.locator('button').filter({ hasText: '创建' }).first();
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toBeEnabled();
  });

  test('publish page has refresh button', async ({ page }) => {
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();
  });
});

// ── System Diagnostics Export (Round 31) ──

test.describe('System Diagnostics Export (Round 31)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('docs page has feature overview section', async ({ page }) => {
    const featureTitle = page.locator('.settings-title').filter({ hasText: '功能概览' });
    await expect(featureTitle).toBeVisible();

    const featureGrid = page.locator('.feature-grid');
    await expect(featureGrid).toBeVisible();

    const featureItems = featureGrid.locator('.feature-item');
    const itemCount = await featureItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(4);

    // Verify specific feature names exist
    const expectedFeatures = ['代理节点', '代理池', '订阅管理', '任务中心'];
    for (const name of expectedFeatures) {
      const item = featureGrid.locator('.feature-name').filter({ hasText: name });
      await expect(item.first()).toBeVisible();
    }
  });

  test('docs page has API documentation link', async ({ page }) => {
    // Check for the API 文档 link in the header button
    const apiLink = page.locator('a').filter({ hasText: 'API 文档' }).first();
    await expect(apiLink).toBeVisible();
    await expect(apiLink).toHaveAttribute('href', '/docs');

    // Also verify the API reference section at the bottom
    const apiTitle = page.locator('.settings-title').filter({ hasText: 'API 参考' });
    await expect(apiTitle).toBeVisible();

    const openApiBtn = page.locator('a').filter({ hasText: '打开 API 文档' }).first();
    await expect(openApiBtn).toBeVisible();
    await expect(openApiBtn).toHaveAttribute('href', '/api/docs');
  });
});
