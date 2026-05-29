import { test, expect } from '@playwright/test';

test.describe('Chain Health Check (via Proxy Pools)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('chain view tab exists', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await expect(chainViewTab).toBeEnabled();
  });

  test('click chain view tab and verify content loads', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await expect(chainViewTab).toHaveClass(/active/);

    // The chain-view tab panel should be visible
    const chainPanel = page.locator('.tab-panel:visible');
    await expect(chainPanel).toBeVisible({ timeout: 5000 });
  });

  test('chain flow visualization exists', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Either visualization or empty state should be present
    const hasVis = await page.locator('.chain-visualization').isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state').isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasVis || hasEmpty).toBeTruthy();

    // If visualization exists, it must contain chain-flow
    if (hasVis) {
      const chainFlow = page.locator('.chain-visualization .chain-flow');
      await expect(chainFlow).toBeVisible();
    }
  });

  test('chain node elements exist', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const nodes = page.locator('.chain-node');
    const nodeCount = await nodes.count();

    if (nodeCount > 0) {
      // At least one entry and one output node
      const entryNode = page.locator('.chain-type-entry');
      const outputNode = page.locator('.chain-type-output');
      await expect(entryNode).toBeVisible();
      await expect(outputNode).toBeVisible();

      // Each node should have a header with type and name
      const firstNode = nodes.first();
      await expect(firstNode.locator('.chain-node-header')).toBeVisible();
      await expect(firstNode.locator('.chain-node-type')).toBeVisible();
      await expect(firstNode.locator('.chain-node-name')).toBeVisible();
    } else {
      // No chain data -- empty state or section divider acceptable
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

  test('subscription page has select-all checkbox', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    const headerCheckbox = table.locator('thead input[type="checkbox"]');
    await expect(headerCheckbox).toBeVisible();
    await expect(headerCheckbox).toBeEnabled();
  });

  test('subscription page has batch action buttons', async ({ page }) => {
    const table = page.locator('table.data-table');
    if (!(await table.isVisible({ timeout: 3000 }).catch(() => false))) {
      await expect(page.locator('.empty-state')).toBeVisible();
      return;
    }

    // Select the first row to trigger selection bar
    const rowCheckbox = table.locator('tbody input[type="checkbox"]').first();
    if (!(await rowCheckbox.isVisible().catch(() => false))) return;

    await rowCheckbox.click();
    await page.waitForTimeout(500);

    // Selection bar should appear
    const selectionBar = page.locator('.selection-bar').first();
    await expect(selectionBar).toBeVisible();

    // Verify at least one batch action button exists
    const btnCount = await selectionBar.locator('button').count();
    expect(btnCount).toBeGreaterThanOrEqual(1);

    // Check that at least one of the standard batch labels is present
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

  test('subscription page has group management UI', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // The "All" filter tab should be present
    const allTab = groupTabs.locator('button').filter({ hasText: '全部' }).first();
    await expect(allTab).toBeVisible();

    // The create-group button should be present
    const createBtn = groupTabs.locator('button').filter({ hasText: '新建分组' }).first();
    await expect(createBtn).toBeVisible();

    // The container should have the tablist role
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

  test('diagnostics page has export button', async ({ page }) => {
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeDisabled();
  });

  test('run diagnostics and verify export button becomes enabled', async ({ page }) => {
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await diagBtn.click();

    // Diagnostics is running: button should show running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible({ timeout: 5000 });

    // Wait for the diagnostics button to revert (meaning it finished)
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    // Export button should now be enabled
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();
  });
});
