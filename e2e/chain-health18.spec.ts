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
    const allTabs = page.locator('.tab-btn');
    const tabCount = await allTabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(3);

    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await expect(chainViewTab).toBeEnabled();

    // Default active tab should be pools, not chain view
    await expect(chainViewTab).not.toHaveClass(/active/);

    // Verify other expected tabs are present
    const poolsTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolsTab).toBeVisible();
    await expect(poolsTab).toHaveClass(/active/);
  });

  test('click chain view tab and verify content loads', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await expect(chainViewTab).toHaveClass(/active/);

    // Pools tab should become inactive
    const poolsTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolsTab).not.toHaveClass(/active/);

    // Chain view panel should become visible
    await page.waitForTimeout(500);
    const chainPanel = page.locator('.tab-panel:visible');
    await expect(chainPanel).toBeVisible({ timeout: 5000 });

    // Chain visualization section header
    await expect(page.locator('.section-divider:has-text("链路可视化")')).toBeVisible();

    // Diagnostic action buttons in the chain view
    await expect(page.locator('.btn:has-text("链路诊断")')).toBeVisible();
    await expect(page.locator('.btn:has-text("测试链路延迟")')).toBeVisible();
    await expect(page.locator('.btn:has-text("测试整条链路")')).toBeVisible();
  });

  test('verify chain flow visualization exists', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(1000);

    const chainVisualization = page.locator('.chain-visualization');

    // Either visualization or empty state should be present
    const hasVis = await chainVisualization.isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasVis || hasEmpty).toBeTruthy();

    if (hasVis) {
      const chainFlow = page.locator('.chain-flow');
      await expect(chainFlow).toBeVisible();

      // Flow should have arrows connecting nodes
      const arrows = chainFlow.locator('.chain-arrow');
      const arrowCount = await arrows.count();
      expect(arrowCount).toBeGreaterThanOrEqual(1);

      // Arrow elements should have icon and label
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
      // Entry node (always rendered in template)
      const entryNode = page.locator('.chain-node-entry');
      await expect(entryNode).toBeVisible();
      await expect(entryNode.locator('.chain-node-header')).toBeVisible();
      await expect(entryNode.locator('.chain-node-type')).toBeVisible();
      await expect(entryNode.locator('.chain-node-name')).toBeVisible();
      await expect(entryNode.locator('.chain-node-status')).toBeVisible();

      const entryType = entryNode.locator('.chain-type-entry');
      await expect(entryType).toBeVisible();
      await expect(entryType).toHaveText('入口');

      // Exit node (always rendered in template)
      const exitNode = page.locator('.chain-node-exit');
      await expect(exitNode).toBeVisible();
      await expect(exitNode.locator('.chain-node-header')).toBeVisible();

      const exitType = exitNode.locator('.chain-type-output');
      await expect(exitType).toBeVisible();
      await expect(exitType).toHaveText('出口');

      // Dynamic intermediate nodes
      const frontPoolNode = page.locator('.chain-node .chain-type-front').first();
      if (await frontPoolNode.isVisible().catch(() => false)) {
        await expect(frontPoolNode).toHaveText('前置池');
      }

      const exitPoolNode = page.locator('.chain-node .chain-type-exit').first();
      if (await exitPoolNode.isVisible().catch(() => false)) {
        await expect(exitPoolNode).toHaveText('落地池');
      }

      // Entry node should have a status dot
      const statusDots = entryNode.locator('.status-dot');
      expect(await statusDots.count()).toBeGreaterThanOrEqual(1);
    } else {
      // No chain data - expect a fallback element
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

  test('verify subscription page has select-all checkbox', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const table = page.locator('table.data-table');
    await expect(table).toBeVisible({ timeout: 5000 });

    // Header checkbox for selecting all subscriptions
    const headerCheckbox = table.locator('thead input[type="checkbox"]');
    await expect(headerCheckbox).toBeVisible();
    await expect(headerCheckbox).toHaveAttribute('aria-label', '选择所有订阅');

    // Table should have a header row with the checkbox column
    const thCells = table.locator('thead th');
    const firstTh = thCells.first();
    await expect(firstTh.locator('input[type="checkbox"]')).toBeVisible();
  });

  test('verify subscription page has batch action buttons', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const table = page.locator('table.data-table');
    await expect(table).toBeVisible({ timeout: 5000 });

    // Selection bar should not be visible before any row is selected
    const selectionBar = page.locator('.selection-bar');
    const initiallyVisible = await selectionBar.isVisible().catch(() => false);
    expect(initiallyVisible).toBeFalsy();

    // Select the first row checkbox to trigger the batch action bar
    const firstRowCheckbox = table.locator('tbody input[type="checkbox"]').first();
    if (!(await firstRowCheckbox.isVisible().catch(() => false))) return;

    await firstRowCheckbox.click();
    await page.waitForTimeout(500);

    // Selection bar with batch actions should appear
    await expect(selectionBar).toBeVisible({ timeout: 5000 });

    const batchBtns = selectionBar.locator('button');
    const btnCount = await batchBtns.count();
    expect(btnCount).toBeGreaterThanOrEqual(1);

    // Verify at least one of the expected batch action buttons is present
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

  test('verify subscription page has group management UI', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // Verify ARIA role and label
    await expect(groupTabs).toHaveAttribute('role', 'tablist');
    const ariaLabel = await groupTabs.getAttribute('aria-label');
    expect(ariaLabel).toBeTruthy();

    // "All" tab should exist
    const allTab = groupTabs.locator('button').filter({ hasText: '全部' }).first();
    await expect(allTab).toBeVisible();

    // "Create group" button should exist
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

    // Export should be disabled before any diagnostics run
    await expect(exportBtn).toBeDisabled();

    // The diagnostics trigger should be available
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await expect(diagBtn).toBeEnabled();
  });

  test('run diagnostics and verify export button becomes enabled', async ({ page }) => {
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await diagBtn.click();

    // Button should show running state
    const runningBtn = page.locator('button:has-text("诊断中...")');
    await expect(runningBtn).toBeVisible({ timeout: 5000 });

    // Wait for diagnostics to complete
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    // Export button should now be enabled
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();

    // Health overview should be visible after diagnostics
    await expect(page.locator('.health-header .settings-title:has-text("系统健康概览")')).toBeVisible();
  });
});
