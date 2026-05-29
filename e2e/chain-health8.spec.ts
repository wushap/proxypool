import { test, expect } from '@playwright/test';

test.describe('Chain Health Check (Proxy Pools Page)', () => {
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

  test('should click chain view tab and verify content loads', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await chainViewTab.click();

    await page.waitForLoadState('networkidle');

    // Either flow visualization or empty state should appear
    const hasFlow = await page.locator('.chain-flow').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasFlow || hasEmpty).toBeTruthy();
  });

  test('should display chain flow visualization', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const chainVisualization = page.locator('.chain-visualization');
    const hasVis = await chainVisualization.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasVis) {
      const chainFlow = page.locator('.chain-flow');
      await expect(chainFlow).toBeVisible();

      // Flow container should have child elements (nodes, arrows, connectors)
      const children = chainFlow.locator('> *');
      const count = await children.count();
      expect(count).toBeGreaterThan(0);
    } else {
      // If no data, empty state or section divider is acceptable
      const hasEmpty = await page.locator('.empty-state').isVisible().catch(() => false);
      const hasDivider = await page.locator('.section-divider').isVisible().catch(() => false);
      expect(hasEmpty || hasDivider).toBeTruthy();
    }
  });

  test('should have chain node elements', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const chainNodes = page.locator('.chain-node');
    const nodeCount = await chainNodes.count();

    if (nodeCount > 0) {
      // Verify node structure: each node should have a header with type and name
      const firstNode = chainNodes.first();
      await expect(firstNode.locator('.chain-node-header')).toBeVisible();
      await expect(firstNode.locator('.chain-node-type')).toBeVisible();
      await expect(firstNode.locator('.chain-node-name')).toBeVisible();

      // Should have entry, front pool, exit pool, and output nodes
      const nodeTypes = page.locator('.chain-node-type');
      const typeCount = await nodeTypes.count();
      expect(typeCount).toBeGreaterThanOrEqual(4);

      // Verify specific node types exist
      await expect(page.locator('.chain-type-entry')).toBeVisible();
      await expect(page.locator('.chain-type-output')).toBeVisible();
    } else {
      // No nodes -- page content should still be present
      const hasContent = await page.locator('.chain-visualization, .empty-state, .section-divider').first().isVisible().catch(() => false);
      expect(hasContent).toBeTruthy();
    }
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

  test('should have select-all checkbox in table header', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    const headerCheckbox = page.locator(
      'table.data-table thead input[type="checkbox"], table.data-table thead .el-checkbox'
    );
    const count = await headerCheckbox.count();
    expect(count).toBeGreaterThanOrEqual(1);

    // Verify it is interactable
    await expect(headerCheckbox.first()).toBeEnabled();
  });

  test('should have batch action buttons', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    const rowCheckbox = page.locator('table.data-table tbody input[type="checkbox"]').first();
    if (!(await rowCheckbox.isVisible().catch(() => false))) return;

    await rowCheckbox.click();
    await page.waitForTimeout(500);

    // Selection bar with batch action buttons should appear
    const selectionBar = page.locator('.selection-bar, [role="status"]').first();
    await expect(selectionBar).toBeVisible();

    const buttons = selectionBar.locator('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);

    // Verify specific batch actions are present: enable, disable, delete
    const batchEnable = selectionBar.locator('button:has-text("批量启用")');
    const batchDisable = selectionBar.locator('button:has-text("批量停用")');
    const batchDelete = selectionBar.locator('button:has-text("批量删除")');

    const hasEnable = await batchEnable.isVisible().catch(() => false);
    const hasDisable = await batchDisable.isVisible().catch(() => false);
    const hasDelete = await batchDelete.isVisible().catch(() => false);

    expect(hasEnable || hasDisable || hasDelete).toBeTruthy();
  });

  test('should have group management UI', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // "全部" (All) filter tab
    const allTab = groupTabs.locator('button:has-text("全部")').first();
    await expect(allTab).toBeVisible();

    // Group creation button
    const createGroupBtn = groupTabs.locator('button:has-text("新建分组")');
    await expect(createGroupBtn).toBeVisible();

    // Verify role attribute for accessibility
    await expect(groupTabs).toHaveAttribute('role', 'tablist');
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

  test('should have export button that is initially disabled', async ({ page }) => {
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeDisabled();
  });

  test('should enable export button after diagnostics run completes', async ({ page }) => {
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await diagBtn.click();

    // Verify diagnostics are running (button text changes)
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible({ timeout: 5000 });

    // Wait for diagnostics to finish (button text reverts from "诊断中...")
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();
  });
});
