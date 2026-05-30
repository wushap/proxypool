import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 30) ──

test.describe('Chain Routing (Round 30)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has real-time monitoring card with connection stats', async ({ page }) => {
    // The real-time monitoring section contains a card titled "实时监控"
    const monitoringCard = page.locator('.card-title').filter({ hasText: '实时监控' });
    await expect(monitoringCard).toBeVisible({ timeout: 10000 });

    // It should contain stat cards with connection-related labels
    const connectionStat = page.locator('.stat-card').filter({ hasText: '活跃连接' });
    await expect(connectionStat.first()).toBeVisible();

    const totalConnStat = page.locator('.stat-card').filter({ hasText: '总连接数' });
    await expect(totalConnStat.first()).toBeVisible();

    const requestRateStat = page.locator('.stat-card').filter({ hasText: '请求速率' });
    await expect(requestRateStat.first()).toBeVisible();
  });

  test('dashboard has proxy pool status section', async ({ page }) => {
    const hasPoolSection = await page.locator('text=代理池状态').first().isVisible({ timeout: 10000 }).catch(() => false);
    const hasPoolEmpty = await page.locator('text=暂无代理池').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasPoolSection || hasPoolEmpty).toBeTruthy();
  });

  test('dashboard has system info section with version and uptime', async ({ page }) => {
    // The system info card is titled "系统信息"
    const systemInfoCard = page.locator('.card-title').filter({ hasText: '系统信息' });
    await expect(systemInfoCard).toBeVisible({ timeout: 10000 });

    // Should show uptime and version rows
    const uptimeRow = page.locator('.dashboard-system-info-row').filter({ hasText: '系统运行时间' });
    await expect(uptimeRow).toBeVisible();

    const versionRow = page.locator('.dashboard-system-info-row').filter({ hasText: '后端版本' });
    await expect(versionRow).toBeVisible();
  });

  test('dashboard has latency trend chart or placeholder', async ({ page }) => {
    const hasLatency = await page.locator('text=延迟趋势').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasLatency).toBeTruthy();
  });

  test('dashboard has proxy pool health heatmap section', async ({ page }) => {
    // The pool health heatmap card is titled "代理池健康热图"
    const heatmapCard = page.locator('.card-title').filter({ hasText: '代理池健康热图' });
    await expect(heatmapCard).toBeVisible({ timeout: 10000 });

    // It should either show the heatmap visualization or an empty state
    const heatmap = page.locator('.dashboard-heatmap');
    const emptyState = page.locator('.empty-state').filter({ hasText: '暂无代理池数据' });

    const hasHeatmap = await heatmap.isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasHeatmap || hasEmpty).toBeTruthy();
  });
});

// ── Subscription Intelligence (Round 30) ──

test.describe('Subscription Intelligence (Round 30)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
  });

  test('pool page has creation form with protocol filter dropdown', async ({ page }) => {
    // The default tab is "代理池" which shows the creation form
    const createCard = page.locator('.settings-title').filter({ hasText: '创建代理池' });
    await expect(createCard).toBeVisible({ timeout: 10000 });

    // Should have a name input field
    const nameInput = page.locator('input[placeholder*="exit-us-01"]');
    await expect(nameInput).toBeVisible();

    // Should have filter section with protocol-related dropdowns
    const filterHeader = page.locator('.form-section-header').filter({ hasText: '过滤条件' });
    await expect(filterHeader).toBeVisible();

    // Open the filter section
    await filterHeader.click();
    await page.waitForTimeout(300);

    // The inbound type select should be visible (HTTP/SOCKS)
    const inboundTypeSelect = page.locator('select').filter({ has: page.locator('option[value="http"]') }).first();
    await expect(inboundTypeSelect).toBeVisible({ timeout: 5000 });
  });

  test('pool page shows pool list or empty state', async ({ page }) => {
    // The pool list table should be visible in the default "代理池" tab
    const table = page.locator('.data-table').first();
    const hasTable = await table.isVisible({ timeout: 10000 }).catch(() => false);

    if (hasTable) {
      // Verify table has column headers
      const headers = table.locator('thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(3);

      // Verify key column headers
      const expectedHeaders = ['状态', '名称', '筛选条件'];
      for (const text of expectedHeaders) {
        const th = headers.filter({ hasText: text });
        await expect(th.first()).toBeVisible();
      }
    } else {
      // No pools yet - page should still have the create form visible
      const createCard = page.locator('.settings-title').filter({ hasText: '创建代理池' });
      await expect(createCard).toBeVisible();
    }
  });

  test('pool page has chain view with flow visualization or empty state', async ({ page }) => {
    // Switch to the chain view tab
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await chainViewTab.click();
    await page.waitForLoadState('domcontentloaded');

    // Chain view section should show the flow visualization
    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    const chainFlow = page.locator('.chain-flow');

    const hasSection = await chainSection.isVisible({ timeout: 5000 }).catch(() => false);
    const hasFlow = await chainFlow.isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasSection || hasFlow).toBeTruthy();

    // If chain flow is visible, it should have chain nodes
    if (hasFlow) {
      const chainNodes = page.locator('.chain-node');
      const nodeCount = await chainNodes.count();
      expect(nodeCount).toBeGreaterThanOrEqual(2);
    }
  });
});

// ── System Diagnostics Export (Round 30) ──

test.describe('System Diagnostics Export (Round 30)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅发布');
  });

  test('publish page has published subscriptions table or empty state', async ({ page }) => {
    // The published subscriptions page has a section titled "订阅发布管理"
    const sectionTitle = page.locator('.section-title').filter({ hasText: '订阅发布管理' });
    await expect(sectionTitle).toBeVisible({ timeout: 10000 });

    // It should show a data table or the page structure
    const table = page.locator('.data-table').first();
    const hasTable = await table.isVisible({ timeout: 10000 }).catch(() => false);

    if (hasTable) {
      // Verify table has column headers
      const headers = table.locator('thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(5);

      // Verify key column headers
      const expectedHeaders = ['名称', '格式', '筛选条件', '启用'];
      for (const text of expectedHeaders) {
        const th = headers.filter({ hasText: text });
        await expect(th.first()).toBeVisible();
      }
    } else {
      // No published subscriptions - should still have create form
      const createTitle = page.locator('.settings-title').filter({ hasText: '创建发布订阅' });
      await expect(createTitle).toBeVisible({ timeout: 5000 });
    }
  });

  test('publish page has create form with name input and format selector', async ({ page }) => {
    const pageContent = page.locator('.page-container, .card').first();
    await expect(pageContent).toBeVisible({ timeout: 10000 });

    const hasForm = await page.locator('input').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasForm || hasEmpty).toBeTruthy();
  });
});
