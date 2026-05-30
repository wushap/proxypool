import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 41) ──

test.describe('Chain Health Check (Round 41)', () => {
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
    expect(joined).toContain('入站端口');
    expect(joined).toContain('订阅管理');
    expect(joined).toContain('订阅发布');
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
    const hasMonitoring = await page.locator('text=实时监控').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasMonitoring).toBeTruthy();
  });

  test('dashboard has quick actions', async ({ page }) => {
    const hasQuickActions = await page.locator('text=快速操作').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasQuickActions).toBeTruthy();
  });
});

// ── Batch Operations (Round 41) ──

test.describe('Batch Operations (Round 41)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('inbound ports has create button', async ({ page }) => {
    const sectionHeader = page.locator('.section-header').first();
    await expect(sectionHeader).toBeVisible({ timeout: 10000 });

    const createBtn = sectionHeader.locator('button').filter({ hasText: '创建端口' });
    await expect(createBtn).toBeVisible();
  });

  test('inbound ports has table or empty state', async ({ page }) => {
    const hasTable = await page.locator('.data-table').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmptyState = await page.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasTable || hasEmptyState).toBeTruthy();

    if (hasTable) {
      const table = page.locator('.data-table').first();
      const ths = table.locator('thead th');
      const thCount = await ths.count();
      expect(thCount).toBeGreaterThanOrEqual(5);
    }
  });

  test('inbound ports has refresh button', async ({ page }) => {
    const sectionHeader = page.locator('.section-header').first();
    await expect(sectionHeader).toBeVisible({ timeout: 10000 });

    const refreshBtn = sectionHeader.locator('button').filter({ hasText: '刷新' });
    await expect(refreshBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 41) ──

test.describe('System Diagnostics Export (Round 41)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('publish page has table or empty state', async ({ page }) => {
    const hasTable = await page.locator('.data-table').isVisible({ timeout: 10000 }).catch(() => false);
    const hasEmptyState = await page.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasTable || hasEmptyState).toBeTruthy();

    if (hasTable) {
      const table = page.locator('.data-table').first();
      const headers = await table.locator('thead th').allTextContents();
      expect(headers.join(' ')).toContain('名称');
    }
  });

  test('publish page has create form', async ({ page }) => {
    const createTitle = page.locator('.settings-title').filter({ hasText: '创建发布订阅' }).first();
    await createTitle.scrollIntoViewIfNeeded();
    await expect(createTitle).toBeVisible({ timeout: 10000 });

    const nameInput = page.locator('input[placeholder="发布订阅名称"]');
    await expect(nameInput).toBeVisible();

    const createBtn = page.locator('button').filter({ hasText: '创建' }).first();
    await expect(createBtn).toBeVisible();
  });
});
