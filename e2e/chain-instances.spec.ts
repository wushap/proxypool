import { test, expect } from '@playwright/test';

test.describe('Chain Instances (Proxy Pools Page)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have chain view tab visible', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
  });

  test('should load content after clicking chain view tab', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();

    // Wait for chain view content to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Verify chain flow or visualization section is visible
    const chainFlow = page.locator('.chain-flow');
    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    const hasFlow = await chainFlow.isVisible().catch(() => false);
    const hasSection = await chainSection.isVisible().catch(() => false);
    expect(hasFlow || hasSection).toBeTruthy();
  });

  test('should display chain flow visualization', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('should have chain node elements', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    // Chain flow should have node elements (entry, front, exit, output)
    expect(nodeCount).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Subscription Batch Operations', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have select-all checkbox', async ({ page }) => {
    // Select-all checkbox is in the table header
    const selectAll = page.locator('th input[type="checkbox"], .select-all-checkbox').first();
    // Alternatively it may be rendered as a standalone checkbox near the table
    const anyCheckbox = page.locator('input[type="checkbox"]').first();
    await expect(selectAll.or(anyCheckbox)).toBeVisible();
  });

  test('should have batch action buttons', async ({ page }) => {
    // Batch action buttons appear when items are selected or are always visible
    const batchButtons = page.locator('button:has-text("批量"), .batch-actions button, .selection-bar button');
    const count = await batchButtons.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('should have group management UI', async ({ page }) => {
    // Group management section or controls
    const groupUI = page.locator('text=分组').first();
    const groupButton = page.locator('button:has-text("分组"), button:has-text("管理分组")').first();
    const groupSection = page.locator('.group-management, .subscription-group').first();

    const hasGroup = await groupUI.isVisible().catch(() => false)
      || await groupButton.isVisible().catch(() => false)
      || await groupSection.isVisible().catch(() => false);
    expect(hasGroup).toBeTruthy();
  });
});

test.describe('System Logs (Diagnostics Page)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should have health history section', async ({ page }) => {
    const historySection = page.locator('text=健康历史').first();
    await expect(historySection).toBeVisible();

    // Should show either history data or empty state
    const hasHistory = await page.locator('.health-history').isVisible().catch(() => false);
    const hasEmptyState = await page.locator('text=暂无历史记录').isVisible().catch(() => false);
    expect(hasHistory || hasEmptyState).toBeTruthy();
  });

  test('should have health alerting rules section', async ({ page }) => {
    const alertingSection = page.locator('.settings-title').filter({ hasText: '健康告警规则' });
    await expect(alertingSection).toBeVisible();

    // Should have at least one rule item
    const ruleItems = page.locator('.alerting-rule-item, .rule-name');
    const ruleCount = await ruleItems.count();
    expect(ruleCount).toBeGreaterThanOrEqual(1);
  });

  test('should have export button', async ({ page }) => {
    // Export button may be visible after running diagnostics or always present
    const exportButton = page.locator('button:has-text("导出"), button:has-text("导出报告")').first();
    await expect(exportButton).toBeVisible();
  });
});
