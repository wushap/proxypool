import { test, expect } from '@playwright/test';

test.describe('Chain Health Check (via Proxy Pools)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('chain view tab exists and is clickable', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await expect(chainViewTab).toBeEnabled();

    // Tab should not be active by default (pools tab is default)
    const poolsTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolsTab).toHaveClass(/active/);
    await expect(chainViewTab).not.toHaveClass(/active/);
  });

  test('clicking chain view tab activates it and loads panel content', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();

    // Tab should now be active
    await expect(chainViewTab).toHaveClass(/active/);

    // The chain-view tab panel should be visible
    const chainPanel = page.locator('.tab-panel:visible');
    await expect(chainPanel).toBeVisible({ timeout: 5000 });

    // Panel should have content (visualization or empty state)
    const hasVis = await page.locator('.chain-visualization').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 3000 }).catch(() => false);
    const hasSection = await page.locator('.section-divider').isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasVis || hasEmpty || hasSection).toBeTruthy();
  });

  test('chain flow visualization container exists with expected structure', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const chainVisualization = page.locator('.chain-visualization');
    if (await chainVisualization.isVisible({ timeout: 3000 }).catch(() => false)) {
      // chain-flow must exist inside chain-visualization
      const chainFlow = chainVisualization.locator('.chain-flow');
      await expect(chainFlow).toBeVisible();

      // chain-flow should contain child elements (nodes and connectors)
      const childCount = await chainFlow.locator('> *').count();
      expect(childCount).toBeGreaterThanOrEqual(2);
    } else {
      // No chain data yet; page still renders something
      const content = await page.locator('.chain-visualization, .empty-state').first().isVisible().catch(() => false);
      expect(content).toBeTruthy();
    }
  });

  test('chain node elements have correct type labels and headers', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const nodes = page.locator('.chain-node');
    const nodeCount = await nodes.count();

    if (nodeCount > 0) {
      // Verify that the expected node types are present as class markers
      const expectedTypes = ['chain-type-entry', 'chain-type-output'];
      for (const typeClass of expectedTypes) {
        await expect(page.locator('.' + typeClass)).toBeVisible();
      }

      // Each visible node should have a header with type and name spans
      const firstNode = nodes.first();
      await expect(firstNode.locator('.chain-node-header')).toBeVisible();
      await expect(firstNode.locator('.chain-node-type')).toBeVisible();
      await expect(firstNode.locator('.chain-node-name')).toBeVisible();

      // Node name should contain an address or placeholder text
      const nodeName = await firstNode.locator('.chain-node-name').textContent();
      expect(nodeName && nodeName.length).toBeGreaterThan(0);
    } else {
      // Fallback: empty state or section divider is acceptable
      const fallback = await page.locator('.empty-state, .section-divider').first().isVisible().catch(() => false);
      expect(fallback).toBeTruthy();
    }
  });
});

test.describe('Batch Operations (via Subscriptions)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('select-all checkbox exists in table header', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    // The select-all checkbox lives in the <td> of the header row
    const headerCheckbox = table.locator('thead input[type="checkbox"]');
    await expect(headerCheckbox).toBeVisible();
    await expect(headerCheckbox).toBeEnabled();
  });

  test('select-all checkbox toggles row selection', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    const headerCheckbox = table.locator('thead input[type="checkbox"]');
    if (!(await headerCheckbox.isVisible())) return;

    // Click select-all
    await headerCheckbox.click();
    await page.waitForTimeout(300);

    // If rows exist, a selection bar should appear
    const rowCount = await table.locator('tbody input[type="checkbox"]').count();
    if (rowCount > 0) {
      const selectionBar = page.locator('.selection-bar').first();
      await expect(selectionBar).toBeVisible({ timeout: 3000 });
    }

    // Deselect all
    await headerCheckbox.click();
    await page.waitForTimeout(300);
  });

  test('batch action buttons appear when a row is selected', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    const rowCheckbox = table.locator('tbody input[type="checkbox"]').first();
    if (!(await rowCheckbox.isVisible().catch(() => false))) return;

    await rowCheckbox.click();
    await page.waitForTimeout(500);

    // Selection bar should appear with batch buttons
    const selectionBar = page.locator('.selection-bar').first();
    await expect(selectionBar).toBeVisible();

    // Verify at least one of the three core batch actions is visible
    const batchBtns = selectionBar.locator('button');
    const btnCount = await batchBtns.count();
    expect(btnCount).toBeGreaterThanOrEqual(1);

    // Check for specific batch labels
    const labels = ['批量启用', '批量停用', '批量删除'];
    let found = false;
    for (const label of labels) {
      const btn = selectionBar.locator(`button:has-text("${label}")`);
      if (await btn.isVisible().catch(() => false)) {
        found = true;
        break;
      }
    }
    expect(found).toBeTruthy();
  });

  test('group management UI has filter tabs and create button', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // The "All" filter tab should be present
    const allTab = groupTabs.locator('button').filter({ hasText: '全部' }).first();
    await expect(allTab).toBeVisible();

    // The create-group button should be present
    const createBtn = groupTabs.locator('button').filter({ hasText: '新建分组' }).first();
    await expect(createBtn).toBeVisible();

    // The container should have the tablist role for accessibility
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

  test('export button is visible but disabled before diagnostics', async ({ page }) => {
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeDisabled();
  });

  test('export button becomes enabled after diagnostics completes', async ({ page }) => {
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await diagBtn.click();

    // Diagnostics is running: button should show running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible({ timeout: 5000 });

    // Wait for the diagnostics button to revert (meaning it finished)
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    // Small extra wait for reactive state to propagate
    await page.waitForTimeout(500);

    // Export button should now be enabled
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();
  });
});
