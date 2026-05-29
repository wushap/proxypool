import { test, expect } from '@playwright/test';

test.describe('Chain Health (Proxy Pools Page)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have chain view tab visible', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
  });

  test('should load content after clicking chain view tab', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await chainViewTab.click();

    await page.waitForLoadState('networkidle');

    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    const chainFlow = page.locator('.chain-flow');

    const hasSection = await chainSection.isVisible().catch(() => false);
    const hasFlow = await chainFlow.isVisible().catch(() => false);
    expect(hasSection || hasFlow).toBeTruthy();
  });

  test('should display chain flow visualization', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-visualization, .chain-flow').first().waitFor({ state: 'visible', timeout: 5000 });

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('should have chain node elements', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Batch Operations (Subscriptions Page)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have select-all checkbox', async ({ page }) => {
    const tableExists = await page.locator('table.data-table').isVisible().catch(() => false);
    if (tableExists) {
      const selectAll = page.locator('input[type="checkbox"][aria-label="选择所有订阅"]');
      await expect(selectAll).toBeVisible();
    } else {
      // Empty state is acceptable - no rows to select
      const emptyState = page.locator('.empty-state');
      await expect(emptyState).toBeVisible();
    }
  });

  test('should have batch action buttons in selection bar', async ({ page }) => {
    const tableExists = await page.locator('table.data-table').isVisible().catch(() => false);
    if (!tableExists) {
      test.skip();
      return;
    }

    // Select first row checkbox to trigger selection bar
    const firstRowCheckbox = page.locator('table.data-table tbody input[type="checkbox"]').first();
    if (await firstRowCheckbox.isVisible()) {
      await firstRowCheckbox.click();

      const selectionBar = page.locator('.selection-bar');
      await expect(selectionBar).toBeVisible();

      const batchEnable = selectionBar.locator('button:has-text("批量启用")');
      const batchDisable = selectionBar.locator('button:has-text("批量停用")');
      const batchDelete = selectionBar.locator('button:has-text("批量删除")');

      const hasEnable = await batchEnable.isVisible().catch(() => false);
      const hasDisable = await batchDisable.isVisible().catch(() => false);
      const hasDelete = await batchDelete.isVisible().catch(() => false);

      expect(hasEnable || hasDisable || hasDelete).toBeTruthy();
    }
  });

  test('should have group management UI', async ({ page }) => {
    // Group tabs or "new group" button indicate group management
    const groupTabs = page.locator('.sub-group-tabs');
    const newGroupBtn = page.locator('button:has-text("新建分组")');

    const hasTabs = await groupTabs.isVisible().catch(() => false);
    const hasNewBtn = await newGroupBtn.isVisible().catch(() => false);

    expect(hasTabs || hasNewBtn).toBeTruthy();
  });
});

test.describe('System Diagnostics Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should have export button on diagnostics page', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    // Button should be disabled before running diagnostics
    await expect(exportButton).toBeDisabled();
  });

  test('should enable export button after running diagnostics', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Wait for diagnostics to complete (button returns to non-running state)
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(1000);

    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();
  });
});
