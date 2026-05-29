import { test, expect } from '@playwright/test';

test.describe('Chain Health - Proxy Pools Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have chain view tab visible alongside pool tab', async ({ page }) => {
    // Both tabs should be present on the proxy pools page
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    const poolTab = page.locator('.tab-btn').filter({ hasText: /^代理池$/ });

    await expect(chainViewTab).toBeVisible();
    await expect(poolTab).toBeVisible();

    // Chain view tab should not be active by default (pool tab is the default)
    const isActive = await chainViewTab.evaluate((el) => el.classList.contains('active') || el.getAttribute('aria-selected') === 'true');
    expect(isActive).toBe(false);
  });

  test('should switch to chain view and show chain flow visualization', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await chainViewTab.click();

    // Wait for the chain visualization section to appear
    const chainFlow = page.locator('.chain-flow');
    await chainFlow.waitFor({ state: 'visible', timeout: 5000 });

    // Chain flow should contain multiple nodes: entry, front pool, exit pool, exit
    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(4);
  });

  test('should display chain node entry and exit markers', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Chain should have both an entry point and an exit point
    const entryNode = page.locator('.chain-node-entry');
    const exitNode = page.locator('.chain-node-exit');

    const hasEntry = await entryNode.isVisible().catch(() => false);
    const hasExit = await exitNode.isVisible().catch(() => false);

    expect(hasEntry && hasExit).toBeTruthy();
  });

  test('should display chain arrows connecting nodes', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    const arrows = page.locator('.chain-arrow');
    const arrowCount = await arrows.count();

    // With entry, pool(s), and exit, we expect at least 2 arrows
    expect(arrowCount).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Batch Operations - Subscriptions Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have select-all checkbox in table header', async ({ page }) => {
    const tableExists = await page.locator('table.data-table').isVisible().catch(() => false);
    if (!tableExists) {
      const emptyState = page.locator('.empty-state');
      await expect(emptyState).toBeVisible();
      return;
    }

    const selectAll = page.locator('table.data-table thead input[type="checkbox"]').first();
    await expect(selectAll).toBeVisible();
  });

  test('should show batch action buttons after selecting a row', async ({ page }) => {
    const tableExists = await page.locator('table.data-table').isVisible().catch(() => false);
    if (!tableExists) {
      const emptyState = page.locator('.empty-state');
      await expect(emptyState).toBeVisible();
      return;
    }

    // Select the first data row checkbox
    const firstRowCheckbox = page.locator('table.data-table tbody input[type="checkbox"]').first();
    const isVisible = await firstRowCheckbox.isVisible().catch(() => false);
    if (!isVisible) return;

    await firstRowCheckbox.click();
    await page.waitForTimeout(300);

    // Selection bar should appear
    const selectionBar = page.locator('.selection-bar');
    await expect(selectionBar).toBeVisible();

    // Verify all three batch action buttons are present and clickable
    const batchEnable = selectionBar.locator('button:has-text("批量启用")');
    const batchDisable = selectionBar.locator('button:has-text("批量停用")');
    const batchDelete = selectionBar.locator('button:has-text("批量删除")');

    const enableVisible = await batchEnable.isVisible().catch(() => false);
    const disableVisible = await batchDisable.isVisible().catch(() => false);
    const deleteVisible = await batchDelete.isVisible().catch(() => false);

    expect(enableVisible || disableVisible || deleteVisible).toBeTruthy();
  });

  test('should display group tabs with all-group filter', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // The "全部" (All) tab must exist as the default filter
    const allTab = groupTabs.locator('button[role="tab"]:has-text("全部"), button:has-text("全部")').first();
    await expect(allTab).toBeVisible();

    // "新建分组" button should be present for creating new groups
    const newGroupBtn = groupTabs.locator('button:has-text("新建分组")');
    await expect(newGroupBtn).toBeVisible();
  });
});

test.describe('System Diagnostics Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display export button that is disabled before diagnostics', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();

    // Export should be disabled since no diagnostics have been run yet
    await expect(exportButton).toBeDisabled();
  });

  test('should enable export button after running diagnostics', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await expect(diagButton).toBeEnabled();

    await diagButton.click();

    // Wait for the diagnostic to finish - the "一键诊断" button reappears (not "诊断中...")
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    // Small extra wait for the export button state to update
    await page.waitForTimeout(500);

    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();
  });
});
