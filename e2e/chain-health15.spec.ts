import { test, expect } from '@playwright/test';

test.describe('Chain Health Check (via Proxy Pools)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.tab-btn').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('verify chain view tab exists', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await expect(chainViewTab).toBeEnabled();

    // Pool tab should be the active default, chain view should not
    await expect(chainViewTab).not.toHaveClass(/active/);

    // Verify other tabs coexist (at least 3 tabs in the bar)
    const allTabs = page.locator('.tab-btn');
    const tabCount = await allTabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(3);
  });

  test('click chain view tab and verify content loads', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await expect(chainViewTab).toHaveClass(/active/);

    // The pools tab should now be inactive
    const poolsTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolsTab).not.toHaveClass(/active/);

    // Chain view panel should appear
    const chainPanel = page.locator('.tab-panel:visible');
    await expect(chainPanel).toBeVisible({ timeout: 5000 });

    // Verify section header for chain visualization
    await expect(page.locator('.section-divider:has-text("链路可视化")')).toBeVisible();

    // Verify diagnostic action buttons are present
    const diagBtn = page.locator('.btn:has-text("链路诊断")');
    await expect(diagBtn).toBeVisible();

    const latencyBtn = page.locator('.btn:has-text("测试链路延迟")');
    await expect(latencyBtn).toBeVisible();

    const fullChainBtn = page.locator('.btn:has-text("测试整条链路")');
    await expect(fullChainBtn).toBeVisible();
  });

  test('verify chain flow visualization exists', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(1000);

    const chainVisualization = page.locator('.chain-visualization');
    const chainFlow = page.locator('.chain-flow');

    // Visualization should exist or an empty state should be shown
    const hasVis = await chainVisualization.isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasVis || hasEmpty).toBeTruthy();

    if (hasVis) {
      await expect(chainFlow).toBeVisible();

      // Chain flow should contain arrows between nodes
      const arrows = chainFlow.locator('.chain-arrow');
      const arrowCount = await arrows.count();
      expect(arrowCount).toBeGreaterThanOrEqual(1);

      // Each arrow should have an icon element
      const firstArrow = arrows.first();
      await expect(firstArrow.locator('.chain-arrow-icon')).toBeVisible();
      await expect(firstArrow.locator('.chain-arrow-label')).toBeVisible();
    }
  });

  test('verify chain node elements exist', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(1000);

    const nodes = page.locator('.chain-node');
    const nodeCount = await nodes.count();

    if (nodeCount > 0) {
      // Entry node is always rendered (hardcoded in template)
      const entryNode = page.locator('.chain-node-entry');
      await expect(entryNode).toBeVisible();
      await expect(entryNode.locator('.chain-node-header')).toBeVisible();
      await expect(entryNode.locator('.chain-node-type')).toBeVisible();
      await expect(entryNode.locator('.chain-node-name')).toBeVisible();
      await expect(entryNode.locator('.chain-node-status')).toBeVisible();

      // Entry node type should say "入口"
      const entryType = entryNode.locator('.chain-type-entry');
      await expect(entryType).toBeVisible();
      await expect(entryType).toHaveText('入口');

      // Exit node is always rendered (hardcoded in template)
      const exitNode = page.locator('.chain-node-exit');
      await expect(exitNode).toBeVisible();
      await expect(exitNode.locator('.chain-node-header')).toBeVisible();

      // Exit node type should say "出口"
      const exitType = exitNode.locator('.chain-type-output');
      await expect(exitType).toBeVisible();
      await expect(exitType).toHaveText('出口');

      // Intermediate nodes (front pool, exit pool) are dynamic
      // They may have warning or active classes
      const frontPoolNode = page.locator('.chain-node .chain-type-front').first();
      if (await frontPoolNode.isVisible().catch(() => false)) {
        await expect(frontPoolNode).toHaveText('前置池');
      }

      const exitPoolNode = page.locator('.chain-node .chain-type-exit').first();
      if (await exitPoolNode.isVisible().catch(() => false)) {
        await expect(exitPoolNode).toHaveText('落地池');
      }

      // All chain nodes should have status indicators
      const statusDots = entryNode.locator('.status-dot');
      expect(await statusDots.count()).toBeGreaterThanOrEqual(1);
    } else {
      // No chain data - empty state or fallback
      const fallback = await page.locator('.empty-state, .section-divider').first().isVisible().catch(() => false);
      expect(fallback).toBeTruthy();
    }
  });
});

test.describe('Batch Operations (via Subscriptions)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await Promise.race([
      page.locator('.status-bar').waitFor({ state: 'visible', timeout: 15000 }),
      page.locator('.loading-state, .error-state').first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => {}),
    ]);
    await page.waitForTimeout(500);
  });

  test('verify select-all checkbox exists', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const table = page.locator('table.data-table');
    await expect(table).toBeVisible({ timeout: 5000 });

    // Header row should contain a select-all checkbox with proper aria-label
    const headerCheckbox = table.locator('thead input[type="checkbox"]');
    await expect(headerCheckbox).toBeVisible();
    await expect(headerCheckbox).toHaveAttribute('aria-label', '选择所有订阅');

    // Verify row-level checkboxes also exist (or at least the column)
    const thCells = table.locator('thead th');
    const firstTh = thCells.first();
    await expect(firstTh.locator('input[type="checkbox"]')).toBeVisible();
  });

  test('verify batch action buttons appear on selection', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const table = page.locator('table.data-table');
    await expect(table).toBeVisible({ timeout: 5000 });

    // Selection bar should not be visible initially
    const selectionBar = page.locator('.selection-bar');
    const initiallyVisible = await selectionBar.isVisible().catch(() => false);
    expect(initiallyVisible).toBeFalsy();

    // Select the first row checkbox to trigger the selection bar
    const firstRowCheckbox = table.locator('tbody input[type="checkbox"]').first();
    if (!(await firstRowCheckbox.isVisible().catch(() => false))) return;

    await firstRowCheckbox.click();
    await page.waitForTimeout(500);

    // Selection bar should now be visible
    await expect(selectionBar).toBeVisible({ timeout: 5000 });

    // Verify selection bar contains batch action buttons
    const batchBtns = selectionBar.locator('button');
    const btnCount = await batchBtns.count();
    expect(btnCount).toBeGreaterThanOrEqual(1);

    // Verify specific batch action labels exist
    const expectedLabels = ['批量启用', '批量停用', '批量删除'];
    let foundCount = 0;
    for (const label of expectedLabels) {
      const btn = selectionBar.locator(`button:has-text("${label}")`);
      if (await btn.isVisible().catch(() => false)) {
        foundCount++;
      }
    }
    expect(foundCount).toBeGreaterThanOrEqual(1);
  });

  test('verify group management UI', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // Verify the group tabs have proper ARIA attributes
    await expect(groupTabs).toHaveAttribute('role', 'tablist');
    const ariaLabel = await groupTabs.getAttribute('aria-label');
    expect(ariaLabel).toBeTruthy();

    // Verify "All" tab exists
    const allTab = groupTabs.locator('button').filter({ hasText: '全部' }).first();
    await expect(allTab).toBeVisible();

    // Verify "Create group" button
    const createBtn = groupTabs.locator('button').filter({ hasText: '新建分组' }).first();
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toHaveAttribute('aria-label', '新建订阅分组');
  });
});

test.describe('System Diagnostics Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics page has export button', async ({ page }) => {
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();

    // Export button should be disabled before running diagnostics (no report data)
    await expect(exportBtn).toBeDisabled();

    // The diagnostics trigger button should be enabled
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeEnabled();
  });

  test('run diagnostics and verify export button becomes enabled', async ({ page }) => {
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await diagBtn.click();

    // Button text should change to "诊断中..." while running
    const runningBtn = page.locator('button:has-text("诊断中...")');
    await expect(runningBtn).toBeVisible({ timeout: 5000 });

    // Wait for diagnostics to finish (button reverts to original text)
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    // Export button should now be enabled
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();

    // Health overview section should be visible after diagnostics
    await expect(page.locator('.health-header .settings-title:has-text("系统健康概览")')).toBeVisible();
  });
});
