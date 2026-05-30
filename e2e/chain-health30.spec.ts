import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 30) ──

test.describe('Chain Health Check (Round 30)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has auto-refresh select dropdown', async ({ page }) => {
    // The auto-refresh dropdown is in the header-actions area
    const headerActions = page.locator('.header-actions').first();
    await expect(headerActions).toBeVisible();

    const select = headerActions.locator('select.select');
    await expect(select).toBeVisible();

    // Verify it has the expected refresh interval options
    const options = select.locator('option');
    const optionCount = await options.count();
    expect(optionCount).toBeGreaterThanOrEqual(4);

    // Verify specific options exist
    const optionTexts = await options.allTextContents();
    expect(optionTexts.some(t => t.includes('手动刷新'))).toBeTruthy();
    expect(optionTexts.some(t => t.includes('5 秒'))).toBeTruthy();
    expect(optionTexts.some(t => t.includes('30 秒'))).toBeTruthy();
  });

  test('dashboard has real-time monitoring with active connections', async ({ page }) => {
    // Scroll down to find the real-time monitoring card
    const monitoringTitle = page.locator('.card-title').filter({ hasText: '实时监控' });
    await expect(monitoringTitle).toBeVisible();

    // The monitoring section contains StatCard components in a stat-grid
    const monitoringCard = monitoringTitle.locator('..').locator('..');
    const statCards = monitoringCard.locator('.stat-card, .dashboard-stat-card');

    // Should have multiple stat cards (active connections, total connections, etc.)
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);

    // Verify specific labels exist in the monitoring section
    const sectionText = await monitoringCard.textContent();
    expect(sectionText).toContain('活跃连接');
    expect(sectionText).toContain('总连接数');
  });

  test('dashboard has bandwidth usage display', async ({ page }) => {
    const hasBw = await page.locator('text=带宽使用').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasBwDist = await page.locator('text=带宽分布').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasBw || hasBwDist).toBeTruthy();
  });

  test('dashboard has error rate display', async ({ page }) => {
    // The error rate StatCard is in the real-time monitoring section
    const errorRateStat = page.locator('.stat-card, .dashboard-stat-card').filter({ hasText: '错误率' });
    await expect(errorRateStat.first()).toBeVisible();

    // The card should display a percentage value
    const cardText = await errorRateStat.first().textContent();
    expect(cardText).toContain('%');
  });

  test('dashboard has gateway status display', async ({ page }) => {
    // The gateway status StatCard is in the real-time monitoring section
    const gatewayStat = page.locator('.stat-card, .dashboard-stat-card').filter({ hasText: '网关状态' });
    await expect(gatewayStat.first()).toBeVisible();

    // The card should display either "运行中" or "已停止"
    const cardText = await gatewayStat.first().textContent();
    const hasStatus = cardText.includes('运行中') || cardText.includes('已停止');
    expect(hasStatus).toBeTruthy();
  });
});

// ── Batch Operations (Round 30) ──

test.describe('Batch Operations (Round 30)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('pool page has chain view tab', async ({ page }) => {
    // The "链路视图" tab should be visible in the tabs bar
    const chainViewTab = page.locator('.tab-btn, .workspace-tabs button').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await expect(chainViewTab).toBeEnabled();
  });

  test('pool page has pool management tab', async ({ page }) => {
    // The "代理池" tab should be visible and active by default
    const poolsTab = page.locator('.tab-btn, .workspace-tabs button').filter({ hasText: '代理池' }).first();
    await expect(poolsTab).toBeVisible();
    await expect(poolsTab).toBeEnabled();

    // Verify the tab is active (default tab)
    await expect(poolsTab).toHaveClass(/active/);

    // The pools tab should show the pool creation form or pool table
    const sectionTitle = page.locator('.section-title, .settings-title').filter({ hasText: '多跳代理池' });
    await expect(sectionTitle).toBeVisible();
  });

  test('pool page has filter section with protocol dropdown', async ({ page }) => {
    // The filter conditions section is inside the "代理池" tab
    // Expand the filter section by clicking its header
    const filterHeader = page.locator('.form-section-header').filter({ hasText: '过滤条件' });
    await expect(filterHeader).toBeVisible();
    await filterHeader.click();

    // After expanding, verify the filter content is visible
    const filterSection = page.locator('.advanced-filters, .form-section').filter({ hasText: '过滤条件' });
    await expect(filterSection.first()).toBeVisible();

    // Verify filter fields exist (ChatGPT, 家宽, etc.)
    const filterText = await filterSection.first().textContent();
    expect(filterText).toContain('ChatGPT');
    expect(filterText).toContain('家宽');
    expect(filterText).toContain('国家/地区');
  });
});

// ── System Diagnostics Export (Round 30) ──

test.describe('System Diagnostics Export (Round 30)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('config history page has save snapshot button', async ({ page }) => {
    // The save snapshot button should be visible in the section header
    const saveBtn = page.locator('button').filter({ hasText: '保存快照' });
    await expect(saveBtn.first()).toBeVisible();

    // Button should be enabled (not currently saving)
    await expect(saveBtn.first()).toBeEnabled();

    // Verify the section title is present
    const sectionTitle = page.locator('.section-title').filter({ hasText: '配置历史' });
    await expect(sectionTitle).toBeVisible();
  });

  test('config history page has empty state or snapshot list', async ({ page }) => {
    // The page should show either an empty state or a list of snapshots
    const emptyState = page.locator('.empty-state, .empty-state-small').filter({ hasText: '暂无配置快照' });
    const snapshotList = page.locator('.config-snapshot-list');

    const hasEmpty = await emptyState.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasList = await snapshotList.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasEmpty || hasList).toBeTruthy();

    // If empty state is shown, verify it has the expected message
    if (hasEmpty) {
      const emptyText = await emptyState.first().textContent();
      expect(emptyText).toContain('暂无配置快照');
    }

    // If snapshot list is shown, verify it has snapshot items
    if (hasList) {
      const items = snapshotList.locator('.config-snapshot-item');
      const itemCount = await items.count();
      expect(itemCount).toBeGreaterThanOrEqual(1);
    }
  });
});
