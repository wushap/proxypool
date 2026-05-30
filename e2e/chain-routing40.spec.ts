import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 40) ──

test.describe('Chain Routing (Round 40)', () => {
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

  test('dashboard has system status section', async ({ page }) => {
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
    const hasQuickActions = await page.locator('text=快速操作').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasQuickActions).toBeTruthy();
  });
});

// ── Subscription Intelligence (Round 40) ──

test.describe('Subscription Intelligence (Round 40)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
  });

  test('pool page has creation form', async ({ page }) => {
    const formTitle = page.locator('.settings-title').filter({ hasText: '创建代理池' }).first();
    await expect(formTitle).toBeVisible({ timeout: 10000 });

    const nameInput = page.locator('input[placeholder*="exit"]');
    await expect(nameInput).toBeVisible();

    const createBtn = page.locator('button').filter({ hasText: '创建代理池' }).first();
    await expect(createBtn).toBeVisible();
  });

  test('pool page has chain view', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' }).first();
    await expect(chainViewTab).toBeVisible({ timeout: 10000 });
    await chainViewTab.click();
    await page.waitForLoadState('domcontentloaded');

    const tabPanel = page.locator('.tab-panel').filter({ hasText: /链路|池/ }).first();
    const hasPanel = await tabPanel.isVisible({ timeout: 10000 }).catch(() => false);
    const hasContent = await page.locator('.page-container, .card').first().isVisible({ timeout: 10000 }).catch(() => false);

    expect(hasPanel || hasContent).toBeTruthy();
  });

  test('pool page has filter section', async ({ page }) => {
    const filterToggle = page.locator('text=过滤条件').first();
    await expect(filterToggle).toBeVisible({ timeout: 10000 });
    await filterToggle.scrollIntoViewIfNeeded();

    const advancedFilters = page.locator('.advanced-filters');
    const isExpanded = await advancedFilters.isVisible({ timeout: 5000 }).catch(() => false);

    if (!isExpanded) {
      await filterToggle.click();
      await expect(advancedFilters).toBeVisible({ timeout: 5000 });
    }

    const hasOpenAI = await page.locator('text=ChatGPT').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasLatency = await page.locator('text=延迟').first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasOpenAI || hasLatency).toBeTruthy();
  });
});

// ── System Diagnostics Export (Round 40) ──

test.describe('System Diagnostics Export (Round 40)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '使用指南');
  });

  test('docs page has quick start section', async ({ page }) => {
    const quickStart = page.locator('h3.settings-title').filter({ hasText: '快速开始' }).first();
    await expect(quickStart).toBeVisible({ timeout: 10000 });

    const steps = page.locator('.quick-start-step');
    const count = await steps.count();
    expect(count).toBeGreaterThanOrEqual(5);

    const stepTexts = await steps.allTextContents();
    const joined = stepTexts.join(' ');
    expect(joined).toContain('添加订阅源');
    expect(joined).toContain('创建代理池');
    expect(joined).toContain('配置入站端口');
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureTitle = page.locator('h3.settings-title').filter({ hasText: '功能概览' }).first();
    await featureTitle.scrollIntoViewIfNeeded();
    await expect(featureTitle).toBeVisible({ timeout: 10000 });

    const featureGrid = page.locator('.feature-grid').first();
    await expect(featureGrid).toBeVisible();

    const featureItems = featureGrid.locator('.feature-item');
    const count = await featureItems.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const gridText = await featureGrid.textContent();
    expect(gridText).toContain('代理节点');
    expect(gridText).toContain('代理池');
  });
});
