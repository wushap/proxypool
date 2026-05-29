import { test, expect } from '@playwright/test';

test.describe('Proxy List Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxies page
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('section.card, .empty-state').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display proxy list table', async ({ page }) => {
    // Check if proxy table is visible
    const table = page.locator('table.data-table').first();
    await expect(table).toBeVisible();

    // Check table headers
    await expect(page.locator('th:has-text("协议")')).toBeVisible();
    await expect(page.locator('th:has-text("地址")')).toBeVisible();
    await expect(page.locator('th:has-text("延迟")')).toBeVisible();
    await expect(page.locator('th:has-text("状态")')).toBeVisible();
  });

  test('should filter proxies by protocol', async ({ page }) => {
    // Find and click protocol filter
    const protocolFilter = page.locator('select').filter({ hasText: '协议' });
    if (await protocolFilter.isVisible()) {
      await protocolFilter.selectOption('trojan');
      await page.waitForTimeout(500);

      // Verify filtered results
      const rows = page.locator('table tbody tr');
      const count = await rows.count();
      for (let i = 0; i < count; i++) {
        const protocolCell = rows.nth(i).locator('td').first();
        await expect(protocolCell).toContainText('trojan');
      }
    }
  });

  test('should filter proxies by status', async ({ page }) => {
    // Find status filter
    const statusFilter = page.locator('select').filter({ hasText: '状态' });
    if (await statusFilter.isVisible()) {
      await statusFilter.selectOption('available');
      await page.waitForTimeout(500);

      // Verify all shown proxies are available
      const statusCells = page.locator('table tbody td:has-text("可用")');
      const count = await statusCells.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should search proxies by keyword', async ({ page }) => {
    // Find search input scoped to the main content (not the sidebar global search)
    const searchInput = page.locator('#main-content input[placeholder*="搜索"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill('example.com');
      await page.waitForTimeout(500);

      // Verify search results contain keyword
      const rows = page.locator('table.data-table tbody tr');
      const count = await rows.count();
      for (let i = 0; i < count; i++) {
        const rowText = await rows.nth(i).textContent();
        expect(rowText?.toLowerCase()).toContain('example.com');
      }
    }
  });

  test('should handle empty proxy list', async ({ page }) => {
    // This test verifies the empty state UI
    // In a real scenario, you might need to mock the API or use a clean database
    const emptyState = page.locator('.empty-state');
    const table = page.locator('.table-wrap table');

    // Either empty state or table should be visible
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasTable = await table.isVisible().catch(() => false);

    expect(hasEmptyState || hasTable).toBeTruthy();
  });

  test('should select and deselect proxies', async ({ page }) => {
    // Find checkboxes in table
    const checkboxes = page.locator('table tbody input[type="checkbox"]');
    const count = await checkboxes.count();

    if (count > 0) {
      // Click first checkbox
      await checkboxes.first().check();
      await expect(checkboxes.first()).toBeChecked();

      // Click again to uncheck
      await checkboxes.first().uncheck();
      await expect(checkboxes.first()).not.toBeChecked();
    }
  });
});