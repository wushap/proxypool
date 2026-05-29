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

    // Wait for the section divider indicating chain visualization loaded
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainFlow = page.locator('.chain-flow');
    const hasFlow = await chainFlow.isVisible().catch(() => false);

    if (hasFlow) {
      // Flow container should have child elements (nodes, arrows, connectors)
      const children = chainFlow.locator('> *');
      const count = await children.count();
      expect(count).toBeGreaterThan(0);
    } else {
      // If no data, empty state is acceptable
      await expect(page.locator('.empty-state')).toBeVisible();
    }
  });

  test('should have chain node elements', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(2000);

    // Check for chain nodes or page content
    const hasNodes = await page.locator('.chain-node').count() > 0;
    const hasContent = await page.locator('.section-divider, .chain-flow, .empty-state').first().isVisible().catch(() => false);
    expect(hasNodes || hasContent).toBeTruthy();
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

    // Wait for diagnostics to finish (button text reverts from "诊断中...")
    await page.locator('button:has-text("一键诊断")').waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(500);

    const exportBtn = page.locator('button:has-text("导出报告")');
    await expect(exportBtn).toBeVisible();
    await expect(exportBtn).toBeEnabled();
  });
});
