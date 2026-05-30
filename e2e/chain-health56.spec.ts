import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 56) ──

test.describe('Chain Health Check (Round 56)', () => {
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
    expect(count).toBeGreaterThanOrEqual(8);

    const texts = await menuItems.allTextContents();
    const joined = texts.join(' ');
    expect(joined).toContain('仪表盘');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('多跳代理池');
    expect(joined).toContain('入站端口');
    expect(joined).toContain('订阅管理');
    expect(joined).toContain('任务中心');
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.stat-grid.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 30000 });

    const statCards = statGrid.locator('.stat-card');
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
    expect(count).toBeGreaterThanOrEqual(4);

    const rowLabels = statusList.locator('.dashboard-status-label');
    const labels = await rowLabels.allTextContents();
    expect(labels).toContain('后端引擎');
    expect(labels).toContain('网关服务');
    expect(labels).toContain('健康代理池');
  });

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await protocolCard.scrollIntoViewIfNeeded();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    const cardTitle = protocolCard.locator('.card-title');
    await expect(cardTitle).toContainText('协议分布');

    // Either a donut chart or empty state should be present
    const donut = protocolCard.locator('.dashboard-donut-wrapper').first();
    const emptyState = protocolCard.locator('.empty-state').first();

    const hasDonut = await donut.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasDonut || hasEmpty).toBe(true);
  });

  test('dashboard has quick actions', async ({ page }) => {
    const quickActionsTitle = page.locator('h3.card-title').filter({ hasText: '快速操作' }).first();
    await quickActionsTitle.scrollIntoViewIfNeeded();
    await expect(quickActionsTitle).toBeVisible({ timeout: 10000 });

    const quickActionsCard = quickActionsTitle.locator('..').first();
    const actionBar = quickActionsCard.locator('.action-bar');
    await expect(actionBar).toBeVisible({ timeout: 10000 });

    const buttons = actionBar.locator('button, a');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(3);

    const actionText = await actionBar.textContent();
    expect(actionText).toContain('任务中心');
    expect(actionText).toContain('代理节点');
    expect(actionText).toContain('订阅管理');
  });
});

// ── Batch Operations (Round 56) ──

test.describe('Batch Operations (Round 56)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('pool page has creation form', async ({ page }) => {
    const createTitle = page.locator('.settings-title').filter({ hasText: '创建代理池' }).first();
    await expect(createTitle).toBeVisible({ timeout: 15000 });

    // Name input for the pool
    const nameInput = page.locator('input[placeholder="如 exit-us-01"]').first();
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    // Inbound type select
    const inboundSelect = page.locator('select').filter({ hasText: 'HTTP' }).first();
    await expect(inboundSelect).toBeVisible();

    // Create button
    const createBtn = page.locator('button').filter({ hasText: '创建代理池' }).last();
    await expect(createBtn).toBeVisible();
  });

  test('pool page has chain view', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' }).first();
    await expect(chainViewTab).toBeVisible({ timeout: 10000 });
    await chainViewTab.click();

    const hasChain = await page.locator('text=链路可视化').first().isVisible({ timeout: 10000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasChain || hasEmpty).toBeTruthy();
  });

  test('pool page has filter section', async ({ page }) => {
    // The filter section is inside the creation form under "过滤条件"
    const filterHeader = page.locator('.form-section-header').filter({ hasText: '过滤条件' }).first();
    await filterHeader.scrollIntoViewIfNeeded();
    await expect(filterHeader).toBeVisible({ timeout: 10000 });

    // Expand the filter section by clicking the header
    await filterHeader.click();

    // Verify filter fields are visible
    const chatgptFilter = page.locator('.advanced-filters .form-label').filter({ hasText: 'ChatGPT' }).first();
    await expect(chatgptFilter).toBeVisible({ timeout: 10000 });

    const latencyField = page.locator('.advanced-filters .form-label').filter({ hasText: '延迟范围' }).first();
    await expect(latencyField).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 56) ──

test.describe('System Diagnostics Export (Round 56)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics has health overview', async ({ page }) => {
    const healthTitle = page.locator('.settings-title').filter({ hasText: '系统健康概览' }).first();
    await expect(healthTitle).toBeVisible({ timeout: 10000 });

    // Verify health summary grid with key items
    const healthGrid = page.locator('.health-summary-grid').first();
    await expect(healthGrid).toBeVisible({ timeout: 10000 });

    const healthItems = healthGrid.locator('.health-item');
    const count = await healthItems.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const labels = healthGrid.locator('.health-label');
    const labelTexts = await labels.allTextContents();
    expect(labelTexts).toContain('后端进程');
    expect(labelTexts).toContain('网关服务');
    expect(labelTexts).toContain('代理池');
    expect(labelTexts).toContain('代理节点');
  });

  test('diagnostics has diagnostic button', async ({ page }) => {
    const diagBtn = page.locator('button').filter({ hasText: '一键诊断' }).first();
    await expect(diagBtn).toBeVisible({ timeout: 10000 });
    await expect(diagBtn).toBeEnabled();

    const exportBtn = page.locator('button').filter({ hasText: '导出报告' }).first();
    await expect(exportBtn).toBeVisible();

    // Verify the section title
    const sectionTitle = page.locator('.section-title').filter({ hasText: '系统诊断' }).first();
    await expect(sectionTitle).toBeVisible();
  });
});
