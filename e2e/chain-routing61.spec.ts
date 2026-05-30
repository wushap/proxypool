import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 61) ──

test.describe('Chain Routing (Round 61)', () => {
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

// ── Subscription Intelligence (Round 61) ──

test.describe('Subscription Intelligence (Round 61)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
  });

  test('subscription page has add form', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });

    const nameInput = page.locator('input[placeholder="订阅名称"]').first();
    const urlInput = page.locator('input[placeholder="订阅链接 URL"]').first();
    const addBtn = page.locator('button:has-text("添加订阅")').first();

    const hasName = await nameInput.isVisible({ timeout: 5000 }).catch(() => false);
    const hasUrl = await urlInput.isVisible({ timeout: 5000 }).catch(() => false);
    const hasBtn = await addBtn.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasName).toBeTruthy();
    expect(hasUrl).toBeTruthy();
    expect(hasBtn).toBeTruthy();
  });

  test('subscription page has group tabs', async ({ page }) => {
    const tabsArea = page.locator('.sub-group-tabs').first();
    await tabsArea.waitFor({ state: 'visible', timeout: 15000 });

    const tabs = tabsArea.locator('button[role="tab"], .btn');
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(1);

    const tabTexts = await tabs.allTextContents();
    const joined = tabTexts.join(' ');
    expect(joined).toContain('全部');
  });

  test('subscription page has batch buttons', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });

    const refreshAll = page.locator('button:has-text("刷新全部")').first();
    const refreshList = page.locator('button:has-text("刷新列表")').first();

    const hasRefreshAll = await refreshAll.isVisible({ timeout: 5000 }).catch(() => false);
    const hasRefreshList = await refreshList.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasRefreshAll || hasRefreshList).toBeTruthy();
  });
});

// ── System Diagnostics Export (Round 61) ──

test.describe('System Diagnostics Export (Round 61)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '使用指南');
  });

  test('docs page has quick start', async ({ page }) => {
    const quickStartCard = page.locator('.card').filter({ hasText: '快速开始' }).first();
    await expect(quickStartCard).toBeVisible({ timeout: 15000 });

    const steps = quickStartCard.locator('.quick-start-step');
    const count = await steps.count();
    expect(count).toBeGreaterThanOrEqual(3);

    const stepsText = await steps.allTextContents();
    const joined = stepsText.join(' ');
    expect(joined).toContain('添加订阅源');
    expect(joined).toContain('创建代理池');
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureCard = page.locator('.card').filter({ hasText: '功能概览' }).first();
    await featureCard.scrollIntoViewIfNeeded();
    await expect(featureCard).toBeVisible({ timeout: 15000 });

    const featureItems = featureCard.locator('.feature-item');
    const count = await featureItems.count();
    expect(count).toBeGreaterThanOrEqual(5);

    const featureNames = featureCard.locator('.feature-name');
    const names = await featureNames.allTextContents();
    expect(names).toContain('代理节点');
    expect(names).toContain('代理池');
    expect(names).toContain('订阅管理');
  });
});
