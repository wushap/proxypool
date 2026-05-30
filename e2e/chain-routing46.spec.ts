import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 46) ──

test.describe('Chain Routing (Round 46)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('.sidebar-menu').first();
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    const menuItems = page.locator('.el-menu-item');
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(8);

    const texts = await menuItems.allTextContents();
    const joined = texts.join(' ');
    expect(joined).toContain('仪表盘');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('入站端口');
    expect(joined).toContain('订阅管理');
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.stat-grid.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 30000 });

    const statCards = statGrid.locator('.stat-card, .card');
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
    expect(count).toBeGreaterThanOrEqual(2);

    const rowLabels = statusList.locator('.dashboard-status-label');
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

// ── Subscription Intelligence (Round 46) ──

test.describe('Subscription Intelligence (Round 46)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
  });

  test('pool page has creation form', async ({ page }) => {
    const nameInput = page.locator('input[placeholder*="exit-us"]');
    await expect(nameInput).toBeVisible({ timeout: 10000 });
  });

  test('pool page has chain view', async ({ page }) => {
    const poolsList = page.locator('.data-table').first();
    const emptyState = page.locator('.empty-state-small');
    const chainView = page.locator('.pool-item, .chain-view, .el-card').first();

    const hasPools = await poolsList.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);
    const hasChain = await chainView.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasPools || hasEmpty || hasChain).toBeTruthy();
  });

  test('pool page has filter section', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '多跳代理池' }).first();
    await expect(sectionTitle).toBeVisible({ timeout: 10000 });

    const poolSection = page.locator('.page-container, .card').first();
    await expect(poolSection).toBeVisible({ timeout: 10000 });

    const sectionText = await poolSection.textContent();
    expect(sectionText).toBeTruthy();
  });
});

// ── System Diagnostics Export (Round 46) ──

test.describe('System Diagnostics Export (Round 46)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '系统诊断');
  });

  test('diagnostics has health overview', async ({ page }) => {
    const title = page.locator('h2.section-title').filter({ hasText: '系统诊断' }).first();
    await expect(title).toBeVisible({ timeout: 10000 });

    const subtitle = page.locator('text=全面检查系统健康状态').first();
    const subtitleVisible = await subtitle.isVisible({ timeout: 5000 }).catch(() => false);

    const alertingRules = page.locator('.alerting-rule-item, .rule-name').first();
    const rulesVisible = await alertingRules.isVisible({ timeout: 5000 }).catch(() => false);

    expect(subtitleVisible || rulesVisible).toBeTruthy();
  });

  test('diagnostics has diagnostic button', async ({ page }) => {
    const diagButton = page.locator('button').filter({ hasText: '一键诊断' }).first();
    await expect(diagButton).toBeVisible({ timeout: 10000 });
    await expect(diagButton).toBeEnabled();
  });
});
