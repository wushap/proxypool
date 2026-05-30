import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 58) ──

test.describe('Chain Routing (Round 58)', () => {
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

// ── Subscription Intelligence (Round 58) ──

test.describe('Subscription Intelligence (Round 58)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
  });

  test('pool page has creation form', async ({ page }) => {
    const creationCard = page.locator('.settings-title').filter({ hasText: '创建代理池' }).first();
    await expect(creationCard).toBeVisible({ timeout: 15000 });

    const nameInput = page.locator('input[placeholder="如 exit-us-01"]').first();
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    const createBtn = page.locator('button').filter({ hasText: '创建代理池' }).first();
    await expect(createBtn).toBeVisible({ timeout: 10000 });
    await expect(createBtn).toBeEnabled();
  });

  test('pool page has chain view', async ({ page }) => {
    const chainViewTab = page.locator('button.tab-btn').filter({ hasText: '链路视图' }).first();
    await expect(chainViewTab).toBeVisible({ timeout: 15000 });
    await chainViewTab.click();

    await page.waitForLoadState('domcontentloaded');

    const chainFlow = page.locator('.chain-flow').first();
    await expect(chainFlow).toBeVisible({ timeout: 20000 });

    const chainNodes = page.locator('.chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);
  });

  test('pool page has filter section', async ({ page }) => {
    const filterHeader = page.locator('.form-section-header').filter({ hasText: '过滤条件' }).first();
    await expect(filterHeader).toBeVisible({ timeout: 15000 });
    await filterHeader.scrollIntoViewIfNeeded();
    await filterHeader.click();

    const filterPanel = page.locator('.advanced-filters').first();
    await expect(filterPanel).toBeVisible({ timeout: 10000 });

    const selects = filterPanel.locator('select');
    const selectCount = await selects.count();
    expect(selectCount).toBeGreaterThanOrEqual(2);
  });
});

// ── System Diagnostics Export (Round 58) ──

test.describe('System Diagnostics Export (Round 58)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '使用指南');
  });

  test('docs page has quick start', async ({ page }) => {
    const quickStartCard = page.locator('.settings-title').filter({ hasText: '快速开始' }).first();
    await expect(quickStartCard).toBeVisible({ timeout: 15000 });

    const steps = page.locator('.quick-start-step');
    const stepCount = await steps.count();
    expect(stepCount).toBeGreaterThanOrEqual(5);

    const stepTexts = await steps.allTextContents();
    const joined = stepTexts.join(' ');
    expect(joined).toContain('添加订阅源');
    expect(joined).toContain('创建代理池');
    expect(joined).toContain('配置入站端口');
  });

  test('docs page has feature grid', async ({ page }) => {
    const featureCard = page.locator('.settings-title').filter({ hasText: '功能概览' }).first();
    await featureCard.scrollIntoViewIfNeeded();
    await expect(featureCard).toBeVisible({ timeout: 15000 });

    const featureItems = page.locator('.feature-item');
    const featureCount = await featureItems.count();
    expect(featureCount).toBeGreaterThanOrEqual(6);

    const featureTexts = await featureItems.allTextContents();
    const joined = featureTexts.join(' ');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('代理池');
    expect(joined).toContain('订阅管理');
  });
});
