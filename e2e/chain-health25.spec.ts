import { test, expect } from '@playwright/test';

test.describe('Chain Health Check (Round 25)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.tab-btn').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('chain view tab is visible', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await expect(chainViewTab).toBeEnabled();
  });

  test('click chain view tab shows content or empty state', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await expect(chainViewTab).toHaveClass(/active/);

    // Wait for tab panel content to render - use waitFor which does support timeout
    await page.locator('.page-container, .card, .section-divider, .chain-visualization, .empty-state').first()
      .waitFor({ state: 'visible', timeout: 10000 });
  });

  test('chain flow has child elements when nodes exist', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await page.waitForTimeout(1000);

    const chainFlow = page.locator('.chain-flow');
    const flowVisible = await chainFlow.isVisible({ timeout: 5000 }).catch(() => false);

    if (flowVisible) {
      // Chain flow should have child elements (nodes, arrows)
      const childCount = await chainFlow.locator('.chain-node, .chain-arrow').count();
      expect(childCount).toBeGreaterThanOrEqual(1);
    } else {
      // If no chain flow, page should still have content
      const pageContent = await page.locator('.page-container, .card, .empty-state').first()
        .isVisible({ timeout: 5000 }).catch(() => false);
      expect(pageContent).toBeTruthy();
    }
  });

  test('chain node elements exist or page has content', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await page.waitForTimeout(1000);

    // Check for chain nodes or page having content
    const chainNodes = page.locator('.chain-node');
    const nodeCount = await chainNodes.count();

    if (nodeCount > 0) {
      expect(nodeCount).toBeGreaterThanOrEqual(2);
      // Nodes should have visible content
      await expect(chainNodes.first()).toBeVisible();
    } else {
      // Page should have some visible content (empty state, visualization container, etc.)
      const hasContent = await page.locator('.page-container, .card, .empty-state, .chain-visualization').first()
        .isVisible({ timeout: 5000 }).catch(() => false);
      expect(hasContent).toBeTruthy();
    }
  });

  test('clicking between pool and chain tabs switches content', async ({ page }) => {
    const poolsTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });

    // Start on pools tab (default)
    await expect(poolsTab).toHaveClass(/active/);
    await expect(chainViewTab).not.toHaveClass(/active/);

    // Switch to chain view
    await chainViewTab.click();
    await expect(chainViewTab).toHaveClass(/active/);
    await expect(poolsTab).not.toHaveClass(/active/);
    await page.waitForTimeout(500);

    // Switch back to pools
    await poolsTab.click();
    await expect(poolsTab).toHaveClass(/active/);
    await expect(chainViewTab).not.toHaveClass(/active/);
    await page.waitForTimeout(500);

    // Pools content should be visible again
    const poolsContent = await page.locator('.page-container, .card, .pool-list, .pool-card').first()
      .isVisible({ timeout: 5000 }).catch(() => false);
    expect(poolsContent).toBeTruthy();
  });
});

test.describe('Batch Operations (Round 25)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await Promise.race([
      page.locator('.status-bar').waitFor({ state: 'visible', timeout: 15000 }),
      page.locator('.empty-state, .error-state').first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => {}),
    ]);
    await page.waitForTimeout(500);
  });

  test('table has select-all checkbox in header', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const table = page.locator('table.data-table');
    await expect(table).toBeVisible({ timeout: 5000 });

    const headerCheckbox = table.locator('thead input[type="checkbox"]');
    await expect(headerCheckbox).toBeVisible();
  });

  test('batch action buttons appear after row selection', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const table = page.locator('table.data-table');
    await expect(table).toBeVisible({ timeout: 5000 });

    // Selection bar should not be visible before selection
    const selectionBar = page.locator('.selection-bar');
    const initiallyVisible = await selectionBar.isVisible().catch(() => false);
    expect(initiallyVisible).toBeFalsy();

    // Select the first row
    const firstRowCheckbox = table.locator('tbody input[type="checkbox"]').first();
    if (!(await firstRowCheckbox.isVisible().catch(() => false))) return;

    await firstRowCheckbox.click();
    await page.waitForTimeout(500);

    // Selection bar should appear with batch action buttons
    await expect(selectionBar).toBeVisible({ timeout: 5000 });
    const btnCount = await selectionBar.locator('button').count();
    expect(btnCount).toBeGreaterThanOrEqual(1);
  });

  test('group management UI has tabs and create button', async ({ page }) => {
    const emptyState = await page.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);
    if (emptyState) return;

    const groupTabs = page.locator('.sub-group-tabs');
    await expect(groupTabs).toBeVisible();

    // All tab
    const allTab = groupTabs.locator('button').filter({ hasText: '全部' }).first();
    await expect(allTab).toBeVisible();

    // Create group button
    const createBtn = groupTabs.locator('button').filter({ hasText: '新建分组' }).first();
    await expect(createBtn).toBeVisible();
  });
});

test.describe('System Diagnostics Export (Round 25)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
  });

  test('export button is initially disabled', async ({ page }) => {
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeDisabled();
  });

  test('export button enables after diagnostics run', async ({ page }) => {
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await diagBtn.click();

    // Wait for diagnostics to complete
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    // Export button should now be enabled
    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();
  });
});
