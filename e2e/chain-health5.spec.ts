import { test, expect } from '@playwright/test';

test.describe('Chain Health Check - Additional Coverage', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have chain view tab visible alongside other tabs', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();

    // Verify other tabs coexist without conflict
    const allTabs = page.locator('.tab-btn');
    const tabCount = await allTabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(2);
  });

  test('should click chain view tab and display either flow or empty state', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await chainViewTab.click();

    // After clicking, at least one of flow or empty state should be visible
    const hasFlow = await page.locator('.chain-flow').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasFlow || hasEmpty).toBeTruthy();
  });

  test('should render chain flow container with child elements', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();

    const chainFlow = page.locator('.chain-flow');
    if (await chainFlow.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Flow should contain structural children (nodes, arrows, connectors)
      const children = chainFlow.locator('> *');
      const count = await children.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should show chain node entries or exit nodes in the flow', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();

    const chainFlow = page.locator('.chain-flow');
    if (await chainFlow.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Look for individual node elements within the flow
      const nodeElements = chainFlow.locator('[class*="chain-node"], [class*="node-entry"], [class*="node-exit"]');
      const nodeCount = await nodeElements.count();
      expect(nodeCount).toBeGreaterThanOrEqual(1);
    }
  });
});

test.describe('Batch Operations - Additional Coverage', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have a checkbox in the table header for select-all', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    // Header row should contain a checkbox for select-all
    const headerCheckbox = page.locator('table.data-table thead input[type="checkbox"], table.data-table thead .el-checkbox');
    const checkboxCount = await headerCheckbox.count();
    expect(checkboxCount).toBeGreaterThanOrEqual(1);
  });

  test('should show batch action buttons when a row is selected', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    const rowCheckbox = page.locator('table.data-table tbody input[type="checkbox"]').first();
    if (!(await rowCheckbox.isVisible().catch(() => false))) return;

    await rowCheckbox.click();
    await page.waitForTimeout(500);

    // Selection bar with batch actions should appear
    const selectionBar = page.locator('.selection-bar, [role="status"]').first();
    await expect(selectionBar).toBeVisible();

    // Should contain action buttons
    const buttons = selectionBar.locator('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should have group management UI with all tab and create button', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // "全部" (All) filter tab
    const allTab = groupTabs.locator('button:has-text("全部")').first();
    await expect(allTab).toBeVisible();

    // Group creation button
    const createGroupBtn = groupTabs.locator('button:has-text("新建分组")');
    await expect(createGroupBtn).toBeVisible();
  });
});

test.describe('System Diagnostics Export - Additional Coverage', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should show export button that is initially disabled', async ({ page }) => {
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeDisabled();
  });

  test('should enable export button after diagnostics run completes', async ({ page }) => {
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await diagBtn.click();

    // Wait for diagnostics to finish (button text reverts from "诊断中...")
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    // Export should now be enabled
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();
  });
});
