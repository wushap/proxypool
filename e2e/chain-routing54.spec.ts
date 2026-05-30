import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 54) ──

test.describe('Chain Routing (Round 54)', () => {
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

// ── Subscription Intelligence (Round 54) ──

test.describe('Subscription Intelligence (Round 54)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
  });

  test('subscription page has add form', async ({ page }) => {
    const nameInput = page.locator('input[placeholder="订阅名称"]').first();
    await expect(nameInput).toBeVisible({ timeout: 15000 });

    const urlInput = page.locator('input[placeholder="订阅链接 URL"]').first();
    await expect(urlInput).toBeVisible({ timeout: 5000 });

    const addButton = page.locator('button').filter({ hasText: '添加订阅' }).first();
    await expect(addButton).toBeVisible({ timeout: 5000 });
  });

  test('subscription page has group tabs', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs').first();
    await expect(groupTabs).toBeVisible({ timeout: 15000 });

    const newGroupBtn = page.locator('button').filter({ hasText: '新建分组' }).first();
    await expect(newGroupBtn).toBeVisible({ timeout: 5000 });
  });

  test('subscription page has batch buttons', async ({ page }) => {
    const refreshAllBtn = page.locator('button').filter({ hasText: '刷新全部' }).first();
    await expect(refreshAllBtn).toBeVisible({ timeout: 15000 });

    const refreshListBtn = page.locator('button').filter({ hasText: '刷新列表' }).first();
    await expect(refreshListBtn).toBeVisible({ timeout: 5000 });

    const bulkImportSummary = page.locator('summary').filter({ hasText: '批量导入订阅' }).first();
    await expect(bulkImportSummary).toBeVisible({ timeout: 5000 });
  });
});

// ── System Diagnostics Export (Round 54) ──

test.describe('System Diagnostics Export (Round 54)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅发布');
  });

  test('publish page has table or empty state', async ({ page }) => {
    const tableSection = page.locator('.table-wrap').first();
    const tableVisible = await tableSection.isVisible({ timeout: 10000 }).catch(() => false);

    if (tableVisible) {
      const table = tableSection.locator('table.data-table').first();
      await expect(table).toBeVisible({ timeout: 5000 });
    } else {
      const emptyState = page.locator('.empty-state').first();
      await expect(emptyState).toBeVisible({ timeout: 10000 });
    }
  });

  test('publish page has create form', async ({ page }) => {
    const createTitle = page.locator('.settings-title').filter({ hasText: '创建发布订阅' }).first();
    await expect(createTitle).toBeVisible({ timeout: 15000 });

    const nameInput = page.locator('input[placeholder="发布订阅名称"]').first();
    await expect(nameInput).toBeVisible({ timeout: 5000 });

    const createButton = page.locator('button').filter({ hasText: /^创建$/ }).first();
    await expect(createButton).toBeVisible({ timeout: 5000 });
  });
});
