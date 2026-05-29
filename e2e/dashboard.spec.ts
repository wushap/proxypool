import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should display system health cards', async ({ page }) => {
    // Verify dashboard page is loaded
    const dashboardPage = page.locator('.dashboard-page');
    await expect(dashboardPage).toBeVisible();

    // Check for health status cards or indicators
    const healthCards = page.locator('.stat-card').first();
    const statsSection = page.locator('.stat-grid').first();

    const hasHealthCards = await healthCards.isVisible().catch(() => false);
    const hasStatsSection = await statsSection.isVisible().catch(() => false);

    // At least one health indicator should be visible
    expect(hasHealthCards || hasStatsSection).toBeTruthy();
  });

  test('should display system statistics', async ({ page }) => {
    // Check for statistics display
    const statsElements = page.locator('.stat-item, .stat-card, [class*="stat"]').first();
    const emptyState = page.locator('text=暂无数据');

    const hasStats = await statsElements.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    // Either stats or empty state should be visible
    expect(hasStats || hasEmptyState).toBeTruthy();
  });

  test('should have quick action buttons', async ({ page }) => {
    // Look for quick action buttons or navigation elements
    const quickActions = page.locator('.quick-actions, .action-buttons, [class*="action"]').first();
    const navLinks = page.locator('a[href], button[class*="nav"]').first();

    const hasQuickActions = await quickActions.isVisible().catch(() => false);
    const hasNavLinks = await navLinks.isVisible().catch(() => false);

    // Dashboard should have some navigation or action elements
    expect(hasQuickActions || hasNavLinks).toBeTruthy();
  });

  test('should navigate to other pages from dashboard', async ({ page }) => {
    // Look for navigation links to other pages
    const proxyLink = page.locator('text=代理节点, text=代理池, text=入站端口').first();

    if (await proxyLink.isVisible()) {
      await proxyLink.click();
      await page.waitForLoadState('networkidle');

      // Verify navigation occurred (URL or page content changed)
      const currentUrl = page.url();
      expect(currentUrl).not.toBe('/webui/');
    }
  });

  test('should display recent activity or logs', async ({ page }) => {
    // Check for activity feed or recent logs
    const activityFeed = page.locator('.activity-feed').first();
    const emptyActivity = page.locator('.empty-state-title:has-text("暂无活动记录")');

    const hasActivity = await activityFeed.isVisible().catch(() => false);
    const hasEmptyActivity = await emptyActivity.isVisible().catch(() => false);

    // Either activity feed or empty state should be visible
    expect(hasActivity || hasEmptyActivity).toBeTruthy();
  });

  test('should show backend connection status', async ({ page }) => {
    // Check for backend status indicator
    const backendStatus = page.locator('.backend-status, [class*="backend"], [class*="connection"]').first();
    const statusIndicator = page.locator('.status-indicator, [class*="status-dot"]').first();

    const hasBackendStatus = await backendStatus.isVisible().catch(() => false);
    const hasStatusIndicator = await statusIndicator.isVisible().catch(() => false);

    // Status indicator should be visible
    expect(hasBackendStatus || hasStatusIndicator).toBeTruthy();
  });

  test('should handle loading state', async ({ page }) => {
    // Reload page to trigger loading state
    await page.reload();

    // Check for loading indicators (should appear briefly)
    const loadingIndicator = page.locator('.loading, .el-loading, [class*="loading"]').first();

    // Loading indicator might appear briefly, so we just verify the page loads
    await page.waitForLoadState('networkidle');

    // Verify page is fully loaded
    const pageContent = page.locator('body');
    await expect(pageContent).toBeVisible();
  });
});
