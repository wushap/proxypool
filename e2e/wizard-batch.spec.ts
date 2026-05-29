import { test, expect } from '@playwright/test';

// The wizard button sits at the very bottom of the sidebar and may be
// clipped by overflow:hidden, so we use JS .click() to bypass the
// actionability check that requires the element to be in the viewport.
async function openWizard(page: import('@playwright/test').Page) {
  await page.locator('.sidebar-wizard-btn').evaluate(el => (el as HTMLElement).click());
  await expect(page.locator('.wizard-dialog')).toBeVisible({ timeout: 5000 });
}

test.describe('Configuration Wizard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should have wizard button in sidebar', async ({ page }) => {
    const wizardBtn = page.locator('.sidebar-wizard-btn');
    // The button exists in the DOM even if clipped by overflow
    await expect(wizardBtn).toHaveCount(1);
    await expect(wizardBtn).toHaveAttribute('aria-label', '打开配置向导');
  });

  test('should have wizard button text label', async ({ page }) => {
    const btnText = page.locator('.sidebar-wizard-btn .wizard-btn-text');
    await expect(btnText).toHaveCount(1);
    await expect(btnText).toContainText('向导');
  });

  test('should open wizard dialog when clicking wizard button', async ({ page }) => {
    await openWizard(page);

    // Wizard dialog title should be visible
    const dialogTitle = page.locator('.wizard-dialog .el-dialog__title');
    await expect(dialogTitle).toContainText('配置向导');

    // Wizard type selection heading should be visible
    const selectTitle = page.locator('.wizard-select-title');
    await expect(selectTitle).toBeVisible();
    await expect(selectTitle).toContainText('选择向导类型');
  });

  test('should have close button visible when no wizard is started', async ({ page }) => {
    await openWizard(page);

    // The "关闭" button appears in the footer when no wizard is active
    const closeBtn = page.locator('.wizard-dialog .el-dialog__footer button:has-text("关闭")');
    await expect(closeBtn).toBeVisible();
  });

  test('should close wizard via footer close button', async ({ page }) => {
    await openWizard(page);

    const closeBtn = page.locator('.wizard-dialog .el-dialog__footer button:has-text("关闭")');
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();

    await page.waitForTimeout(300);
    const wizardDialog = page.locator('.wizard-dialog');
    await expect(wizardDialog).not.toBeVisible();
  });

  test('should close wizard via dialog header X button', async ({ page }) => {
    await openWizard(page);

    // Click the X close button in the dialog header
    const headerCloseBtn = page.locator('.wizard-dialog .el-dialog__headerbtn');
    await expect(headerCloseBtn).toBeVisible();
    await headerCloseBtn.click();

    await page.waitForTimeout(300);
    const wizardDialog = page.locator('.wizard-dialog');
    await expect(wizardDialog).not.toBeVisible();
  });

  test('should have wizard select container in dialog body', async ({ page }) => {
    await openWizard(page);

    // The wizard-select container holds the type cards area
    const wizardSelect = page.locator('.wizard-select');
    await expect(wizardSelect).toBeVisible();

    // The title should be inside this container
    await expect(wizardSelect.locator('.wizard-select-title')).toBeVisible();
  });
});

test.describe('Batch Operations on Proxies Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxies page
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have select-all checkbox in table header', async ({ page }) => {
    const table = page.locator('table.data-table').first();
    await expect(table).toBeVisible();

    // The select-all checkbox is in the first th
    const selectAll = table.locator('thead th input[type="checkbox"]');
    await expect(selectAll).toBeVisible();
    await expect(selectAll).toHaveAttribute('aria-label', '选择所有代理');
  });

  test('should select all proxies and show selection count', async ({ page }) => {
    const table = page.locator('table.data-table').first();
    const selectAll = table.locator('thead th input[type="checkbox"]');

    // Skip if table is empty (disabled checkbox)
    if (await selectAll.isDisabled().catch(() => true)) {
      test.skip();
      return;
    }

    await selectAll.check();
    await page.waitForTimeout(300);

    // Verify selection count in status bar
    const selectionInfo = page.locator('.status-item').filter({ hasText: '选中' });
    await expect(selectionInfo).toBeVisible({ timeout: 3000 });

    // The count should be greater than 0
    const countEl = selectionInfo.locator('strong');
    const countText = await countEl.textContent();
    expect(parseInt(countText || '0')).toBeGreaterThan(0);
  });

  test('should show batch action bar when proxies are selected', async ({ page }) => {
    const table = page.locator('table.data-table').first();
    const selectAll = table.locator('thead th input[type="checkbox"]');

    if (await selectAll.isDisabled().catch(() => true)) {
      test.skip();
      return;
    }

    await selectAll.check();
    await page.waitForTimeout(500);

    // Selection bar should appear
    const selectionBar = page.locator('.selection-bar');
    await expect(selectionBar).toBeVisible({ timeout: 3000 });

    // Selection bar should contain batch action buttons
    await expect(selectionBar.locator('button:has-text("导出选中")')).toBeVisible();
    await expect(selectionBar.locator('button:has-text("复制链接")')).toBeVisible();
    await expect(selectionBar.locator('button:has-text("删除")')).toBeVisible();
  });

  test('should deselect all and hide batch action bar', async ({ page }) => {
    const table = page.locator('table.data-table').first();
    const selectAll = table.locator('thead th input[type="checkbox"]');

    if (await selectAll.isDisabled().catch(() => true)) {
      test.skip();
      return;
    }

    // Select all first
    await selectAll.check();
    await page.waitForTimeout(500);
    await expect(page.locator('.selection-bar')).toBeVisible({ timeout: 3000 });

    // Deselect all
    await selectAll.uncheck();
    await page.waitForTimeout(500);

    // Selection bar should disappear
    const selectionBar = page.locator('.selection-bar');
    await expect(selectionBar).not.toBeVisible();
  });
});

test.describe('Proxy Pool Chain View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxy pools page
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should navigate to proxy pools page and see tabs', async ({ page }) => {
    // The proxy pools page should have tab buttons
    const tabs = page.locator('.tab-btn');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(1);

    // Chain view tab should be one of them
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
  });

  test('should switch to chain view tab and load visualization', async ({ page }) => {
    // Click the chain view tab
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await chainTab.click();

    // Wait for the chain view panel to become visible
    const chainPanel = page.locator('.tab-panel:has(.chain-flow)');
    await expect(chainPanel).toBeVisible({ timeout: 5000 });
  });

  test('should display chain flow visualization', async ({ page }) => {
    // Switch to chain view tab
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Chain flow element should be present
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible({ timeout: 5000 });
  });

  test('should have chain node elements in visualization', async ({ page }) => {
    // Switch to chain view tab
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Chain nodes should exist (entry, front pool, exit pool, exit)
    const chainNodes = page.locator('.chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(1);

    // Entry node should always be present
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode).toBeVisible();

    // Each node should have a type label
    const nodeTypes = page.locator('.chain-node-type');
    const typeCount = await nodeTypes.count();
    expect(typeCount).toBeGreaterThanOrEqual(1);
  });
});
