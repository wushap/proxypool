import { test, expect } from '@playwright/test';

test.describe('Chain Visualization', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display chain view tab in workspace tabs', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
  });

  test('should load chain view tab content when clicked', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(300);

    // Verify the chain visualization section header appears
    const sectionHeader = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(sectionHeader).toBeVisible();
  });

  test('should display chain flow visualization', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(300);

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('should display chain node elements', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(300);

    // Chain should have entry, front pool, exit pool, and exit point nodes
    const chainNodes = page.locator('.chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(3);

    // Verify specific node types exist
    await expect(page.locator('.chain-node-entry')).toBeVisible();
    await expect(page.locator('.chain-node-exit')).toBeVisible();
  });

  test('should display chain node type labels', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(300);

    // Verify entry and exit type labels exist
    await expect(page.locator('.chain-type-entry')).toBeVisible();
    await expect(page.locator('.chain-type-output')).toBeVisible();
  });

  test('should display chain arrows between nodes', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(300);

    const arrows = page.locator('.chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Batch Operations', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display select-all checkbox in subscriptions table', async ({ page }) => {
    // The select-all checkbox is in the thead of the data table
    const selectAllCheckbox = page.locator('table.data-table thead input[type="checkbox"]').first();
    await expect(selectAllCheckbox).toBeVisible();
  });

  test('should display batch action buttons when items are selected', async ({ page }) => {
    // Select all to trigger the batch bar
    const selectAllCheckbox = page.locator('table.data-table thead input[type="checkbox"]').first();
    if (await selectAllCheckbox.isEnabled()) {
      await selectAllCheckbox.click();
      await page.waitForTimeout(200);

      // Selection bar should appear with batch buttons
      const selectionBar = page.locator('.selection-bar');
      await expect(selectionBar).toBeVisible();

      // Verify batch action buttons exist
      await expect(selectionBar.locator('button:has-text("批量启用")')).toBeVisible();
      await expect(selectionBar.locator('button:has-text("批量停用")')).toBeVisible();
      await expect(selectionBar.locator('button:has-text("批量删除")')).toBeVisible();
    }
  });

  test('should display group management UI', async ({ page }) => {
    // Group tabs should be present (at minimum the "全部" tab and "新建分组" button)
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // "新建分组" button should be visible
    await expect(page.locator('button:has-text("新建分组")')).toBeVisible();

    // The "全部" tab should exist as the default group filter
    await expect(groupTabs.locator('button:has-text("全部")')).toBeVisible();
  });
});

test.describe('System Diagnostics Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-title').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display export button on diagnostics page', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    // Export should be disabled before running diagnostics
    await expect(exportButton).toBeDisabled();
  });

  test('should enable export button after running diagnostics', async ({ page }) => {
    // Run diagnostics
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeEnabled();
    await diagButton.click();

    // Wait for diagnostics to complete
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Export button should now be enabled
    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();
  });
});
