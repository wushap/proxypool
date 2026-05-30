import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 33) ──

test.describe('Chain Routing (Round 33)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has protocol distribution with donut chart', async ({ page }) => {
    // The protocol distribution card contains a donut chart (SVG)
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    // It should contain either data (donut SVG + legend) or an empty state
    const donutSvg = protocolCard.locator('.dashboard-donut-svg');
    const emptyState = protocolCard.locator('.empty-state');
    const hasDonut = await donutSvg.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasDonut || hasEmpty).toBeTruthy();

    // When data exists, verify the donut center shows total node count
    if (hasDonut) {
      const donutCenter = protocolCard.locator('.dashboard-donut-center');
      await expect(donutCenter).toBeVisible();
      const centerText = await donutCenter.textContent();
      expect(centerText).toContain('节点');
    }
  });

  test('dashboard has country/region distribution', async ({ page }) => {
    const hasGeo = await page.locator('text=国家/地区分布').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasGeo).toBeTruthy();
  });

  test('dashboard has IP purity distribution', async ({ page }) => {
    // The IP purity card
    const purityCard = page.locator('.card').filter({ hasText: 'IP 纯净度分布' }).first();
    await expect(purityCard).toBeVisible({ timeout: 10000 });

    // It should contain either purity bars or an empty state
    const barRows = purityCard.locator('.dashboard-protocol-row');
    const emptyState = purityCard.locator('.empty-state');
    const hasBars = (await barRows.count()) > 0;
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasBars || hasEmpty).toBeTruthy();

    // When data exists, verify purity entries have name and count
    if (hasBars) {
      const firstRow = barRows.first();
      const name = firstRow.locator('.dashboard-protocol-name');
      await expect(name).toBeVisible();
      const count = firstRow.locator('.dashboard-protocol-count');
      await expect(count).toBeVisible();
    }
  });

  test('dashboard has success rate trend', async ({ page }) => {
    // The success rate trend card with 24-hour label
    const trendCard = page.locator('.card').filter({ hasText: '成功率趋势' }).first();
    await expect(trendCard).toBeVisible({ timeout: 10000 });

    // It should contain either an SVG trend chart or an empty state
    const trendSvg = trendCard.locator('.dashboard-trend-svg');
    const emptyState = trendCard.locator('.empty-state');
    const hasSvg = await trendSvg.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasSvg || hasEmpty).toBeTruthy();

    // When data exists, verify the trend labels show percentage values
    if (hasSvg) {
      const trendLabels = trendCard.locator('.dashboard-trend-label');
      const labelCount = await trendLabels.count();
      expect(labelCount).toBeGreaterThanOrEqual(2);
      const labels = await trendLabels.allTextContents();
      expect(labels.some(l => l.includes('%'))).toBeTruthy();
    }
  });

  test('dashboard has protocol latency comparison', async ({ page }) => {
    // The protocol latency comparison card
    const latencyCard = page.locator('.card').filter({ hasText: '协议延迟对比' }).first();
    await expect(latencyCard).toBeVisible({ timeout: 10000 });

    // It should contain either protocol latency rows or an empty state
    const protoRows = latencyCard.locator('.dashboard-protocol-latency-row');
    const emptyState = latencyCard.locator('.empty-state');
    const hasRows = (await protoRows.count()) > 0;
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasRows || hasEmpty).toBeTruthy();

    // When data exists, verify each protocol row has a name and latency value
    if (hasRows) {
      const firstRow = protoRows.first();
      const name = firstRow.locator('.dashboard-protocol-latency-name');
      await expect(name).toBeVisible();
      const value = firstRow.locator('.dashboard-protocol-latency-value');
      await expect(value).toBeVisible();
      const text = await value.textContent();
      expect(text).toContain('ms');
    }
  });
});

// ── Subscription Intelligence (Round 33) ──

test.describe('Subscription Intelligence (Round 33)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
  });

  test('pool page has creation form', async ({ page }) => {
    // The creation form card with "创建代理池" title
    const createForm = page.locator('.card').filter({ hasText: '创建代理池' }).first();
    await expect(createForm).toBeVisible({ timeout: 10000 });

    // The form should have a name input
    const nameInput = createForm.locator('input[placeholder]').first();
    await expect(nameInput).toBeVisible();

    // The create button should be present
    const createBtn = createForm.locator('button').filter({ hasText: '创建代理池' }).first();
    await expect(createBtn).toBeVisible();
  });

  test('pool page has chain view tab', async ({ page }) => {
    // The tab bar should contain "链路视图" tab
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' }).first();
    await expect(chainViewTab).toBeVisible({ timeout: 10000 });

    // Click the chain view tab
    await chainViewTab.click();
    await page.waitForLoadState('domcontentloaded');

    // The chain view panel should show the chain visualization section
    const chainVisualization = page.locator('.chain-visualization, .chain-flow').first();
    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' }).first();
    const hasViz = await chainVisualization.isVisible({ timeout: 5000 }).catch(() => false);
    const hasSection = await chainSection.isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasViz || hasSection).toBeTruthy();
  });

  test('pool page has filter section', async ({ page }) => {
    // The filter section header with "过滤条件" text
    const filterHeader = page.locator('.form-section-title').filter({ hasText: '过滤条件' }).first();
    await expect(filterHeader).toBeVisible({ timeout: 10000 });

    // The filter section should be collapsible - click to expand it
    const filterSection = page.locator('.form-section-header').filter({ hasText: '过滤条件' }).first();
    await filterSection.click();

    // After expanding, filter form groups should be visible
    const advancedFilters = page.locator('.advanced-filters');
    await expect(advancedFilters).toBeVisible({ timeout: 5000 });

    // Verify ChatGPT filter select exists
    const chatgptSelect = advancedFilters.locator('select').first();
    await expect(chatgptSelect).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 33) ──

test.describe('System Diagnostics Export (Round 33)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅发布');
  });

  test('publish page has table or empty state', async ({ page }) => {
    // The published subscriptions table should be present
    const dataTable = page.locator('.data-table').first();
    const tableVisible = await dataTable.isVisible({ timeout: 10000 }).catch(() => false);

    if (tableVisible) {
      // Verify table has expected column headers
      const headers = dataTable.locator('th');
      const headerTexts = await headers.allTextContents();
      const joinedText = headerTexts.join(' ');
      expect(joinedText).toContain('名称');
      expect(joinedText).toContain('格式');
    } else {
      // Empty state should be visible
      const emptyState = page.locator('.empty-state').first();
      await expect(emptyState).toBeVisible({ timeout: 5000 });
    }
  });

  test('publish page has create form', async ({ page }) => {
    // The create form section with "创建发布订阅" title
    const createForm = page.locator('.settings-title').filter({ hasText: '创建发布订阅' }).first();
    await expect(createForm).toBeVisible({ timeout: 10000 });

    // The name input should be present
    const nameInput = page.locator('input[placeholder="发布订阅名称"]').first();
    await expect(nameInput).toBeVisible();

    // The format select should be present
    const formatSelect = page.locator('select').filter({ hasText: '原始链接' }).first();
    await expect(formatSelect).toBeVisible();

    // The create button should be present
    const createBtn = page.locator('button').filter({ hasText: '创建' }).first();
    await expect(createBtn).toBeVisible();
  });
});
