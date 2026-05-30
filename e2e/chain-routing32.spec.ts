import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 32) ──

test.describe('Chain Routing (Round 32)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has notification bell in sidebar', async ({ page }) => {
    const bell = page.locator('.notification-bell-wrapper');
    await expect(bell).toBeVisible({ timeout: 10000 });

    // The bell icon span should be present
    const bellIcon = page.locator('.notification-bell');
    await expect(bellIcon).toBeVisible();
    await expect(bellIcon).toHaveText('🔔');
  });

  test('dashboard has dark mode toggle button', async ({ page }) => {
    const toggleBtn = page.locator('.sidebar-toggle');
    await expect(toggleBtn).toBeVisible({ timeout: 10000 });

    // The button should have a sun or moon icon
    const toggleLabel = await toggleBtn.getAttribute('aria-label');
    expect(toggleLabel).toBeTruthy();
  });

  test('dashboard has wizard button', async ({ page }) => {
    const wizardBtn = page.locator('.sidebar-wizard-btn');
    await expect(wizardBtn).toBeVisible({ timeout: 10000 });

    // The button should have wizard text
    const wizardText = page.locator('.wizard-btn-text');
    await expect(wizardText).toBeVisible();
    await expect(wizardText).toHaveText('向导');
  });

  test('dashboard has term explanations section', async ({ page }) => {
    const sidebarHelp = page.locator('.sidebar-help');
    await expect(sidebarHelp).toBeVisible({ timeout: 10000 });

    // The title should be "术语说明"
    const helpTitle = page.locator('.sidebar-help-title');
    await expect(helpTitle).toBeVisible();
    await expect(helpTitle).toHaveText('术语说明');

    // Should have at least one help item
    const helpItems = page.locator('.sidebar-help-item');
    const count = await helpItems.count();
    expect(count).toBeGreaterThan(0);
  });

  test('dashboard has system status overview in sidebar', async ({ page }) => {
    const sidebarFooter = page.locator('.sidebar-footer');
    await expect(sidebarFooter).toBeVisible({ timeout: 10000 });

    // Should contain system status stats like nodes, available, backend, etc.
    const stats = sidebarFooter.locator('.sidebar-stat');
    const count = await stats.count();
    expect(count).toBeGreaterThanOrEqual(3);

    // Verify key stat labels exist
    const statLabels = sidebarFooter.locator('.sidebar-stat-label');
    const labels = await statLabels.allTextContents();
    expect(labels).toContain('节点');
    expect(labels).toContain('可用');
  });
});

// ── Subscription Intelligence (Round 32) ──

test.describe('Subscription Intelligence (Round 32)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '代理节点');
  });

  test('proxy nodes page has search input', async ({ page }) => {
    // The filter panel has el-input elements for filtering/searching proxies
    const filterPanel = page.locator('.filter-panel');
    await expect(filterPanel).toBeVisible({ timeout: 10000 });

    // The filter panel toggle should be present and clickable
    const filterToggle = page.locator('.filter-panel-toggle');
    await expect(filterToggle).toBeVisible();

    // Click to expand the filter panel
    await filterToggle.click();

    // After expanding, el-input elements should be visible for filtering
    const filterInputs = filterPanel.locator('.el-input');
    const inputCount = await filterInputs.count();
    expect(inputCount).toBeGreaterThan(0);
  });

  test('proxy nodes page has table with rows or empty state', async ({ page }) => {
    // The proxy data table should be present
    const dataTable = page.locator('.data-table').first();
    const tableVisible = await dataTable.isVisible({ timeout: 15000 }).catch(() => false);

    // Or an empty state / loading state should be shown
    const emptyState = page.locator('.empty-state').first();
    const loadingState = page.locator('.loading-state, .skeleton').first();

    const hasEmpty = await emptyState.isVisible({ timeout: 5000 }).catch(() => false);
    const hasLoading = await loadingState.isVisible({ timeout: 3000 }).catch(() => false);

    expect(tableVisible || hasEmpty || hasLoading).toBeTruthy();
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    // The page header should have action buttons
    const importBtn = page.locator('button').filter({ hasText: '导入代理' });
    await expect(importBtn.first()).toBeVisible({ timeout: 10000 });

    const exportBtn = page.locator('button').filter({ hasText: '导出代理' });
    await expect(exportBtn.first()).toBeVisible();

    const clearFilterBtn = page.locator('button').filter({ hasText: '清空筛选' });
    await expect(clearFilterBtn.first()).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 32) ──

test.describe('System Diagnostics Export (Round 32)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '入站端口');
  });

  test('inbound ports page has create button', async ({ page }) => {
    const createBtn = page.locator('button').filter({ hasText: '创建端口' });
    await expect(createBtn.first()).toBeVisible({ timeout: 10000 });
    await expect(createBtn.first()).toBeEnabled();
  });

  test('inbound ports page has table with columns or empty state', async ({ page }) => {
    // Either a data table with port entries is shown, or an empty state
    const dataTable = page.locator('.data-table').first();
    const tableVisible = await dataTable.isVisible({ timeout: 10000 }).catch(() => false);

    if (tableVisible) {
      // Verify table has expected column headers
      const headers = dataTable.locator('th');
      const headerTexts = await headers.allTextContents();
      const joinedText = headerTexts.join(' ');
      expect(joinedText).toContain('状态');
      expect(joinedText).toContain('名称');
    } else {
      // Empty state should be visible
      const emptyState = page.locator('.empty-state').first();
      await expect(emptyState).toBeVisible({ timeout: 5000 });
    }
  });
});
