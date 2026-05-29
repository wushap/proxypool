import { test, expect } from '@playwright/test';

// ---------------------------------------------------------------------------
// Ports Page (入站端口)
// ---------------------------------------------------------------------------
test.describe('Ports Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should load ports page with title', async ({ page }) => {
    await expect(page.locator('h2.section-title')).toContainText('入站端口');
    await expect(page.locator('.section-header .form-hint')).toContainText('管理 HTTP 代理网关的入站端口配置');
  });

  test('should show empty state when no ports exist', async ({ page }) => {
    const table = page.locator('.data-table');
    const tableVisible = await table.isVisible().catch(() => false);

    if (!tableVisible) {
      const emptyState = page.locator('.empty-state');
      await expect(emptyState).toBeVisible();
      await expect(emptyState).toContainText('暂无入站端口');
    }
  });

  test('should have clickable create port button', async ({ page }) => {
    const createBtn = page.locator('button:has-text("创建端口")');
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toBeEnabled();

    await createBtn.click();
    const dialog = page.locator('.el-dialog').filter({ hasText: /创建入站端口/ });
    await expect(dialog).toBeVisible();

    // Close dialog without creating
    const cancelBtn = page.locator('.el-dialog button:has-text("取消")');
    if (await cancelBtn.isVisible()) {
      await cancelBtn.click();
    }
  });

  test('should display ports table headers when data is present', async ({ page }) => {
    const table = page.locator('.data-table');
    if (await table.isVisible().catch(() => false)) {
      await expect(table.locator('th')).toContainText(['状态', '名称', '跳点链路']);
    }
  });
});

// ---------------------------------------------------------------------------
// Gateway Configuration (via Dashboard)
// ---------------------------------------------------------------------------
test.describe('Gateway Configuration via Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display gateway status panel on dashboard', async ({ page }) => {
    // The dashboard has a "系统状态" card in the System Status section
    const systemStatusCard = page.locator('.card').filter({ hasText: '系统状态' });
    await expect(systemStatusCard.first()).toBeVisible();
  });

  test('should show gateway running/stopped state', async ({ page }) => {
    // Find the "网关服务" row in the dashboard status list
    const gatewayRow = page.locator('.dashboard-status-row').filter({ hasText: '网关服务' });
    await expect(gatewayRow).toBeVisible();

    // Should show either "运行中" or "未启动"
    const badge = gatewayRow.locator('.badge');
    const text = await badge.textContent();
    expect(text?.trim()).toMatch(/运行中|未启动/);
  });

  test('should show proxy pool count on dashboard', async ({ page }) => {
    const poolRow = page.locator('.dashboard-status-row').filter({ hasText: '健康代理池' });
    await expect(poolRow).toBeVisible();

    // Should contain a count pattern like "0 / 0" or "1 / 2"
    const value = poolRow.locator('.font-semibold');
    const text = await value.textContent();
    expect(text?.trim()).toMatch(/\d+\s*\/\s*\d+/);
  });

  test('should show backend status on dashboard', async ({ page }) => {
    const backendRow = page.locator('.dashboard-status-row').filter({ hasText: '后端引擎' });
    await expect(backendRow).toBeVisible();

    const badge = backendRow.locator('.badge');
    const text = await badge.textContent();
    expect(text?.trim()).toMatch(/运行中|已停止/);
  });
});

// ---------------------------------------------------------------------------
// System Diagnostics
// ---------------------------------------------------------------------------
test.describe('System Diagnostics', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load diagnostics page with one-click diagnostics button', async ({ page }) => {
    await expect(page.locator('h2.section-title')).toContainText('系统诊断');

    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await expect(diagButton).toBeEnabled();
  });

  test('should display health alerting rules section', async ({ page }) => {
    const rulesSection = page.locator('.settings-title').filter({ hasText: '健康告警规则' });
    await expect(rulesSection).toBeVisible();

    // Verify specific rules exist
    await expect(page.locator('.rule-name').filter({ hasText: '后端进程停止' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '网关服务停止' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '健康评分过低' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '代理池异常' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '代理节点不可用' })).toBeVisible();
  });

  test('should show health summary grid with backend/gateway/proxy status', async ({ page }) => {
    // The health summary grid is always visible (even before running diagnostics)
    const summaryGrid = page.locator('.health-summary-grid');
    await expect(summaryGrid).toBeVisible();

    // Verify labels for backend, gateway, proxy pool, proxy nodes
    await expect(summaryGrid.locator('.health-label').filter({ hasText: '后端进程' })).toBeVisible();
    await expect(summaryGrid.locator('.health-label').filter({ hasText: '网关服务' })).toBeVisible();
    await expect(summaryGrid.locator('.health-label').filter({ hasText: '代理池' })).toBeVisible();
    await expect(summaryGrid.locator('.health-label').filter({ hasText: '代理节点' })).toBeVisible();

    // Each label should have a status value next to it
    const statusItems = summaryGrid.locator('.health-status');
    expect(await statusItems.count()).toBeGreaterThanOrEqual(4);
  });
});
