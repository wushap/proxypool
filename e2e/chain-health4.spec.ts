import { test, expect } from '@playwright/test';

test.describe('Chain Health Check - Proxy Pools Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have chain view tab visible', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
  });

  test('should switch to chain view and load content', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await chainViewTab.click();

    // Chain view content should appear: either chain flow or an empty state
    const chainFlow = page.locator('.chain-flow');
    const emptyState = page.locator('.empty-state');

    const hasFlow = await chainFlow.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasFlow || hasEmpty).toBeTruthy();
  });

  test('should show chain flow visualization when data exists', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();

    const chainFlow = page.locator('.chain-flow');
    if (await chainFlow.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Verify the flow container has meaningful content
      await expect(chainFlow).toBeVisible();
      const flowChildren = chainFlow.locator(':scope > *');
      const childCount = await flowChildren.count();
      expect(childCount).toBeGreaterThan(0);
    }
  });

  test('should display chain node elements in flow', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();

    const chainFlow = page.locator('.chain-flow');
    if (await chainFlow.isVisible({ timeout: 3000 }).catch(() => false)) {
      const chainNodes = page.locator('.chain-flow .chain-node, .chain-flow .chain-node-entry, .chain-flow .chain-node-exit');
      const nodeCount = await chainNodes.count();
      expect(nodeCount).toBeGreaterThanOrEqual(1);
    }
  });
});

test.describe('Batch Operations - Subscriptions Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('domcontentloaded');
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

  test('should display batch action buttons after row selection', async ({ page }) => {
    const tableExists = await page.locator('table.data-table').isVisible().catch(() => false);
    if (!tableExists) {
      const emptyState = page.locator('.empty-state');
      await expect(emptyState).toBeVisible();
      return;
    }

    const firstRowCheckbox = page.locator('table.data-table tbody input[type="checkbox"]').first();
    if (!(await firstRowCheckbox.isVisible().catch(() => false))) return;

    await firstRowCheckbox.click();
    await page.waitForTimeout(500);

    // The selection bar may use .selection-bar class or role="status"
    const selectionBar = page.locator('.selection-bar, [role="status"]').filter({ hasText: '已选中' }).first();
    await expect(selectionBar).toBeVisible();

    // Verify at least one batch action button exists
    const batchButtons = selectionBar.locator('button');
    const buttonCount = await batchButtons.count();
    expect(buttonCount).toBeGreaterThan(0);
  });

  test('should display group management UI', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // "全部" (All) tab should exist as the default filter
    const allTab = groupTabs.locator('button:has-text("全部")').first();
    await expect(allTab).toBeVisible();

    // "新建分组" button for creating new groups
    const newGroupBtn = groupTabs.locator('button:has-text("新建分组")');
    await expect(newGroupBtn).toBeVisible();
  });
});

test.describe('System Diagnostics Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have export button that is disabled before diagnostics', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeDisabled();
  });

  test('should enable export button after running diagnostics', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Wait for diagnostics to complete - button reverts from "诊断中..." back to "一键诊断"
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();
  });
});
