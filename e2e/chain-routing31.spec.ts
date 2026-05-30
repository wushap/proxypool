import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 31) ──

test.describe('Chain Routing (Round 31)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has success rate trend chart section', async ({ page }) => {
    // The success rate trend card is titled "成功率趋势"
    const successRateCard = page.locator('.card-title').filter({ hasText: '成功率趋势' });
    await expect(successRateCard).toBeVisible({ timeout: 10000 });

    // It should either show the SVG trend chart or an empty state
    const trendSvg = page.locator('.dashboard-trend-svg').first();
    const emptyState = page.locator('.empty-state').filter({ hasText: '暂无成功率数据' });

    const hasSvg = await trendSvg.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasSvg || hasEmpty).toBeTruthy();
  });

  test('dashboard has protocol latency comparison section', async ({ page }) => {
    // The protocol latency comparison card is titled "协议延迟对比"
    const protoLatencyCard = page.locator('.card-title').filter({ hasText: '协议延迟对比' });
    await expect(protoLatencyCard).toBeVisible({ timeout: 10000 });

    // It should either show protocol latency rows or an empty state
    const latencyRows = page.locator('.dashboard-protocol-latency-row');
    const emptyState = page.locator('.empty-state').filter({ hasText: '暂无协议延迟数据' });

    const rowCount = await latencyRows.count();
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(rowCount > 0 || hasEmpty).toBeTruthy();
  });

  test('dashboard has top 10 fastest nodes section', async ({ page }) => {
    const hasFastest = await page.locator('text=最快节点').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasFastest).toBeTruthy();
  });

  test('dashboard has top 10 slowest nodes section', async ({ page }) => {
    const hasSlowest = await page.locator('text=最慢节点').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasSlowest).toBeTruthy();
  });

  test('dashboard has geographic distribution section', async ({ page }) => {
    // The geographic distribution card is titled "地理位置分布"
    const geoCard = page.locator('.card-title').filter({ hasText: '地理位置分布' });
    await expect(geoCard).toBeVisible({ timeout: 10000 });

    // It should either show geo region bars or an empty state
    const geoRegions = page.locator('.dashboard-geo-region');
    const emptyState = page.locator('.empty-state').filter({ hasText: '暂无地理位置数据' });

    const regionCount = await geoRegions.count();
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(regionCount > 0 || hasEmpty).toBeTruthy();
  });
});

// ── Subscription Intelligence (Round 31) ──

test.describe('Subscription Intelligence (Round 31)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
  });

  test('subscription page has intelligence panel or data table', async ({ page }) => {
    // The subscription intelligence section is titled "订阅智能分析"
    const intelligencePanel = page.locator('.subscription-intelligence').first();
    const hasIntelligence = await intelligencePanel.isVisible({ timeout: 10000 }).catch(() => false);

    // Also check for the data table
    const dataTable = page.locator('.data-table').first();
    const hasTable = await dataTable.isVisible({ timeout: 5000 }).catch(() => false);

    // Check for section title
    const sectionTitle = page.locator('.section-title').filter({ hasText: '订阅管理' });
    const hasTitle = await sectionTitle.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasIntelligence || hasTable || hasTitle).toBeTruthy();
  });

  test('subscription page has group management tabs', async ({ page }) => {
    // The group tabs are in a div with role="tablist" and class "sub-group-tabs"
    const groupTabs = page.locator('.sub-group-tabs').first();
    await expect(groupTabs).toBeVisible({ timeout: 10000 });

    // Should have at least one tab button with "全部"
    const allTab = groupTabs.locator('button').filter({ hasText: '全部' });
    await expect(allTab.first()).toBeVisible();
  });

  test('subscription page has batch operation buttons', async ({ page }) => {
    // The batch operations are in the btn-group header area
    // "刷新全部" button is always visible
    const refreshAllBtn = page.locator('button').filter({ hasText: '刷新全部' });
    await expect(refreshAllBtn.first()).toBeVisible({ timeout: 10000 });

    // "删除不可用" button should be present
    const deleteUnavailableBtn = page.locator('button').filter({ hasText: '删除不可用' });
    await expect(deleteUnavailableBtn.first()).toBeVisible();

    // "刷新列表" button should be present
    const refreshListBtn = page.locator('button').filter({ hasText: '刷新列表' });
    await expect(refreshListBtn.first()).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 31) ──

test.describe('System Diagnostics Export (Round 31)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '系统诊断');
  });

  test('diagnostics page has health overview with 4 categories', async ({ page }) => {
    // The health overview card is titled "系统健康概览"
    const healthOverview = page.locator('.settings-title').filter({ hasText: '系统健康概览' });
    await expect(healthOverview).toBeVisible({ timeout: 10000 });

    // Should have 4 health categories in the health-summary-grid
    const healthGrid = page.locator('.health-summary-grid');
    await expect(healthGrid).toBeVisible();

    const healthItems = healthGrid.locator('.health-item');
    const itemCount = await healthItems.count();
    expect(itemCount).toBe(4);

    // Verify the 4 category labels
    const expectedLabels = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const label of expectedLabels) {
      const item = healthItems.filter({ hasText: label });
      await expect(item.first()).toBeVisible();
    }
  });

  test('diagnostics page has one-click diagnostic button', async ({ page }) => {
    // The one-click diagnostic button is titled "一键诊断"
    const diagnosticBtn = page.locator('button').filter({ hasText: '一键诊断' });
    await expect(diagnosticBtn.first()).toBeVisible({ timeout: 10000 });

    // The button should not be disabled initially
    await expect(diagnosticBtn.first()).toBeEnabled();
  });
});
