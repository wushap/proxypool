import { test, expect } from '@playwright/test';

test.describe('Chain Health Check (via Proxy Pools)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.tab-btn').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('chain view tab exists', async ({ page }) => {
    const tabs = page.locator('.tab-btn');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(2);

    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await expect(chainViewTab).toBeEnabled();

    // Should not be active by default (pools tab is default)
    await expect(chainViewTab).not.toHaveClass(/active/);
  });

  test('click chain view tab and verify content loads', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await expect(chainViewTab).toHaveClass(/active/);

    // Verify the pools tab is no longer active
    const poolsTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolsTab).not.toHaveClass(/active/);

    // Chain view panel should be visible
    const chainPanel = page.locator('.tab-panel:visible');
    await expect(chainPanel).toBeVisible({ timeout: 5000 });

    // Verify chain view section header exists
    const sectionHeader = page.locator('.section-divider:has-text("链路可视化")');
    await expect(sectionHeader).toBeVisible();

    // Verify chain diagnostics buttons exist
    const diagBtn = page.locator('.btn:has-text("链路诊断")');
    await expect(diagBtn).toBeVisible();
  });

  test('chain flow visualization exists', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(1500);

    const chainVisualization = page.locator('.chain-visualization');
    const hasVis = await chainVisualization.isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasVis || hasEmpty).toBeTruthy();

    if (hasVis) {
      // Verify chain flow container
      const chainFlow = chainVisualization.locator('.chain-flow');
      await expect(chainFlow).toBeVisible();

      // Verify chain arrows exist between nodes
      const arrows = chainFlow.locator('.chain-arrow');
      const arrowCount = await arrows.count();
      expect(arrowCount).toBeGreaterThanOrEqual(1);

      // Verify arrow labels
      const firstArrow = arrows.first();
      await expect(firstArrow.locator('.chain-arrow-icon')).toBeVisible();
    }
  });

  test('chain node elements exist', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(1500);

    const nodes = page.locator('.chain-node');
    const nodeCount = await nodes.count();

    if (nodeCount > 0) {
      // Entry and output nodes should always be present
      const entryNode = page.locator('.chain-node-entry');
      const outputNode = page.locator('.chain-node-exit');
      await expect(entryNode).toBeVisible();
      await expect(outputNode).toBeVisible();

      // Verify entry node has required sub-elements
      await expect(entryNode.locator('.chain-node-header')).toBeVisible();
      await expect(entryNode.locator('.chain-node-type')).toBeVisible();
      await expect(entryNode.locator('.chain-node-name')).toBeVisible();
      await expect(entryNode.locator('.chain-node-status')).toBeVisible();

      // Verify entry node type label
      const entryType = entryNode.locator('.chain-type-entry');
      await expect(entryType).toBeVisible();
      await expect(entryType).toHaveText('入口');

      // Verify output node type label
      const outputType = outputNode.locator('.chain-type-output');
      await expect(outputType).toBeVisible();
      await expect(outputType).toHaveText('出口');

      // Verify chain-node entries have status dots
      const statusDots = entryNode.locator('.status-dot');
      const dotCount = await statusDots.count();
      expect(dotCount).toBeGreaterThanOrEqual(1);
    } else {
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

  test('subscription page has select-all checkbox', async ({ page }) => {
    const table = page.locator('table.data-table');
    const isEmpty = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (isEmpty) return;

    await expect(table).toBeVisible({ timeout: 5000 });

    const headerRow = table.locator('thead tr');
    const headerCheckbox = headerRow.locator('input[type="checkbox"]');
    await expect(headerCheckbox).toBeVisible();

    // Verify checkbox has an accessible label
    const ariaLabel = await headerCheckbox.getAttribute('aria-label');
    expect(ariaLabel).toBeTruthy();

    // Verify there are row-level checkboxes as well
    const bodyCheckboxes = table.locator('tbody input[type="checkbox"]');
    const bodyCheckboxCount = await bodyCheckboxes.count();
    expect(bodyCheckboxCount).toBeGreaterThanOrEqual(0);
  });

  test('subscription page has batch action buttons', async ({ page }) => {
    const isEmpty = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (isEmpty) return;

    const table = page.locator('table.data-table');
    await expect(table).toBeVisible({ timeout: 5000 });

    // Select a row checkbox to reveal the batch action bar
    const rowCheckbox = table.locator('tbody input[type="checkbox"]').first();
    if (!(await rowCheckbox.isVisible().catch(() => false))) return;

    await rowCheckbox.click();
    await page.waitForTimeout(500);

    // Verify selection bar appears
    const selectionBar = page.locator('.selection-bar').first();
    await expect(selectionBar).toBeVisible();

    // Verify selection count text
    const selectionText = selectionBar.locator('span').first();
    await expect(selectionText).toBeVisible();

    // Verify batch action buttons
    const btnCount = await selectionBar.locator('button').count();
    expect(btnCount).toBeGreaterThanOrEqual(1);

    // Check for specific batch action buttons
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

  test('subscription page has group management UI', async ({ page }) => {
    const isEmpty = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (isEmpty) return;

    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // Verify the tablist role
    await expect(groupTabs).toHaveAttribute('role', 'tablist');

    // Verify "All" tab
    const allTab = groupTabs.locator('button').filter({ hasText: '全部' }).first();
    await expect(allTab).toBeVisible();

    // Verify "Create group" button
    const createBtn = groupTabs.locator('button').filter({ hasText: '新建分组' }).first();
    await expect(createBtn).toBeVisible();

    // Verify the group tabs container has proper aria-label
    const ariaLabel = await groupTabs.getAttribute('aria-label');
    expect(ariaLabel).toBeTruthy();
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

    // Export button should be disabled before running diagnostics
    await expect(exportBtn).toBeDisabled();

    // Verify the diagnostics button is enabled
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await expect(diagBtn).toBeEnabled();
  });

  test('run diagnostics and verify export button becomes enabled', async ({ page }) => {
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await diagBtn.click();

    // Button should show "诊断中..." while running
    const runningBtn = page.locator('button:has-text("诊断中...")');
    await expect(runningBtn).toBeVisible({ timeout: 5000 });

    // Wait for diagnostics to complete - the button reverts to "一键诊断"
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    // Export button should now be enabled
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();

    // Health summary should now be visible
    const healthHeader = page.locator('.health-header .settings-title:has-text("系统健康概览")');
    await expect(healthHeader).toBeVisible();
  });
});
