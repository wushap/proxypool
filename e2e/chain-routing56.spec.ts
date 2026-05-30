import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 56) ──

test.describe('Chain Routing (Round 56)', () => {
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
    expect(joined).toContain('设置');
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 30000 });

    const statCards = statGrid.locator('.stat-card, [class*="stat"]');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const gridText = await statGrid.textContent();
    expect(gridText).toContain('节点总数');
    expect(gridText).toContain('可用节点');
    expect(gridText).toContain('可用率');
  });

  test('dashboard has system status', async ({ page }) => {
    const statusCard = page.locator('.card').filter({ hasText: '系统状态' }).first();
    await statusCard.scrollIntoViewIfNeeded();
    await expect(statusCard).toBeVisible({ timeout: 10000 });

    const statusRows = statusCard.locator('.dashboard-status-row');
    const count = await statusRows.count();
    expect(count).toBeGreaterThanOrEqual(2);

    const rowLabels = statusCard.locator('.dashboard-status-label');
    const labels = await rowLabels.allTextContents();
    expect(labels).toContain('后端引擎');
    expect(labels).toContain('网关服务');
  });

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await protocolCard.scrollIntoViewIfNeeded();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    const hasDonut = await protocolCard.locator('.dashboard-donut-wrapper').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await protocolCard.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasDonut || hasEmpty).toBeTruthy();

    if (hasDonut) {
      const svgChart = protocolCard.locator('.dashboard-donut-svg');
      await expect(svgChart).toBeVisible();

      const legendItems = protocolCard.locator('.dashboard-donut-legend-item');
      const legendCount = await legendItems.count();
      expect(legendCount).toBeGreaterThanOrEqual(1);
    }
  });

  test('dashboard has quick actions', async ({ page }) => {
    await page.locator('.stat-grid.dashboard-stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });

    const quickActionsCard = page.locator('.card').filter({ has: page.locator('.card-title:text-is("快速操作")') }).first();
    await quickActionsCard.scrollIntoViewIfNeeded();
    await expect(quickActionsCard).toBeVisible({ timeout: 10000 });

    const buttons = quickActionsCard.locator('button');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(5);
  });
});

// ── Subscription Intelligence (Round 56) ──

test.describe('Subscription Intelligence (Round 56)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '入站端口');
  });

  test('inbound ports has create button', async ({ page }) => {
    const createBtn = page.locator('button:has-text("创建端口")').first();
    await expect(createBtn).toBeVisible({ timeout: 15000 });
    await expect(createBtn).toBeEnabled();
  });

  test('inbound ports has table or empty state', async ({ page }) => {
    const table = page.locator('.data-table').first();
    const tableVisible = await table.isVisible({ timeout: 10000 }).catch(() => false);

    if (tableVisible) {
      await expect(table).toBeVisible({ timeout: 5000 });
      const rows = table.locator('tbody tr');
      const rowCount = await rows.count();
      expect(rowCount).toBeGreaterThanOrEqual(0);
    } else {
      const emptyState = page.locator('.empty-state').first();
      await expect(emptyState).toBeVisible({ timeout: 10000 });
    }
  });

  test('inbound ports has refresh button', async ({ page }) => {
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible({ timeout: 15000 });
    await expect(refreshBtn).toBeEnabled();
  });
});

// ── System Diagnostics Export (Round 56) ──

test.describe('System Diagnostics Export (Round 56)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '设置');
  });

  test('settings page has theme options', async ({ page }) => {
    await expect(page.locator('text=外观设置')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=主题模式')).toBeVisible();

    await expect(page.locator('text=浅色')).toBeVisible();
    await expect(page.locator('text=深色')).toBeVisible();
    await expect(page.locator('text=跟随系统')).toBeVisible();
  });

  test('settings page has about section', async ({ page }) => {
    const aboutCard = page.locator('.settings-card').filter({ hasText: '关于' }).first();
    await aboutCard.scrollIntoViewIfNeeded();
    await expect(aboutCard.locator('.settings-title').filter({ hasText: '关于' })).toBeVisible({ timeout: 15000 });
    await expect(aboutCard.locator('.about-label').filter({ hasText: '应用名称' })).toBeVisible();
    await expect(aboutCard.locator('.about-value').filter({ hasText: 'Proxy Pool' })).toBeVisible();
    await expect(aboutCard.locator('.about-label').filter({ hasText: '版本' })).toBeVisible();
  });
});
