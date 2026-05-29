import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Wait for dashboard page to render
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });
  });

  test('should display dashboard title', async ({ page }) => {
    const title = page.locator('h1.header-title');
    await expect(title).toHaveText('仪表盘');
  });

  test('should display statistics cards', async ({ page }) => {
    // Wait for stat grid to be visible
    const statGrid = page.locator('.stat-grid.dashboard-stat-grid');
    await expect(statGrid).toBeVisible();

    // Verify each stat card label exists
    const expectedLabels = ['节点总数', '可用节点', '可用率', '平均延迟'];
    for (const label of expectedLabels) {
      const statCard = page.locator('.stat-card').filter({ hasText: label });
      await expect(statCard.first()).toBeVisible();
    }
  });

  test('should display protocol distribution chart', async ({ page }) => {
    const chartCard = page.locator('.card').filter({ hasText: '协议分布' });
    await expect(chartCard.first()).toBeVisible();

    // Verify either the chart (donut SVG) or empty state is shown
    const donutChart = chartCard.locator('.dashboard-donut-chart');
    const emptyState = chartCard.locator('.empty-state-small, .empty-state');
    const hasChart = await donutChart.isVisible().catch(() => false);
    const hasEmpty = await emptyState.first().isVisible().catch(() => false);
    expect(hasChart || hasEmpty).toBeTruthy();
  });

  test('should display system status section', async ({ page }) => {
    const statusCard = page.locator('.card').filter({ hasText: '系统状态' });
    await expect(statusCard.first()).toBeVisible();

    // Verify key status items exist
    const statusList = statusCard.locator('.dashboard-status-list');
    await expect(statusList).toBeVisible();

    // Check for specific status labels
    const backendLabel = statusCard.locator('.dashboard-status-label').filter({ hasText: '后端引擎' });
    await expect(backendLabel).toBeVisible();
  });

  test('should have auto-refresh dropdown', async ({ page }) => {
    const refreshSelect = page.locator('select[aria-label="自动刷新间隔"]');
    await expect(refreshSelect).toBeVisible();

    // Verify it has the expected options
    const options = refreshSelect.locator('option');
    await expect(options).toHaveCount(5);

    // Default should be "手动刷新" (value 0)
    await expect(refreshSelect).toHaveValue('0');
  });

  test('should have refresh button', async ({ page }) => {
    const refreshBtn = page.locator('button[aria-label="刷新仪表盘数据"]');
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();
    // Button text should contain "刷新"
    await expect(refreshBtn).toContainText('刷新');
  });
});

test.describe('Search Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });
  });

  test('should have global search input in sidebar', async ({ page }) => {
    const searchWrapper = page.locator('.sidebar-search .search-input-wrapper');
    await expect(searchWrapper).toBeVisible();

    const searchInput = searchWrapper.locator('.search-input');
    await expect(searchInput).toBeVisible();
    await expect(searchInput).toHaveAttribute('readonly', '');
  });

  test('should open search dialog when clicking search input', async ({ page }) => {
    const searchWrapper = page.locator('.sidebar-search .search-input-wrapper');
    await searchWrapper.click();

    // The el-dialog should become visible
    const searchDialog = page.locator('.global-search-dialog');
    await expect(searchDialog).toBeVisible({ timeout: 5000 });

    // Search input inside dialog should be visible and focusable
    const dialogInput = page.locator('.global-search-input');
    await expect(dialogInput).toBeVisible();
  });

  test('should show search hint and results when typing', async ({ page }) => {
    // Open search dialog
    await page.locator('.sidebar-search .search-input-wrapper').click();
    const dialogInput = page.locator('.global-search-input');
    await expect(dialogInput).toBeVisible({ timeout: 5000 });

    // Initially should show hint text
    const searchHint = page.locator('.search-hint');
    await expect(searchHint).toBeVisible();

    // Type a search query (need at least 2 characters)
    await dialogInput.fill('http');
    await page.waitForTimeout(500);

    // After typing, the search should either show results or a "no results" message
    // Both are valid outcomes depending on app data
    const resultsArea = page.locator('.global-search-results');
    await expect(resultsArea).toBeVisible();
  });

  test('should close search dialog', async ({ page }) => {
    // Open search dialog
    await page.locator('.sidebar-search .search-input-wrapper').click();
    const searchDialog = page.locator('.global-search-dialog');
    await expect(searchDialog).toBeVisible({ timeout: 5000 });

    // Close with Escape key
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    // Dialog should no longer be visible
    await expect(searchDialog).not.toBeVisible();
  });

  test('should open search with Ctrl+K keyboard shortcut', async ({ page }) => {
    // Ensure search is not open
    const searchDialog = page.locator('.global-search-dialog');
    const isAlreadyOpen = await searchDialog.isVisible().catch(() => false);
    if (isAlreadyOpen) {
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);
    }

    // Press Ctrl+K
    await page.keyboard.press('Control+k');
    await page.waitForTimeout(500);

    // Search dialog should be visible
    await expect(searchDialog).toBeVisible({ timeout: 5000 });

    // Input should be focused
    const dialogInput = page.locator('.global-search-input');
    await expect(dialogInput).toBeVisible();
  });
});

test.describe('Dark Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });
  });

  test('should have dark mode toggle button', async ({ page }) => {
    const toggleBtn = page.locator('button.sidebar-toggle');
    await expect(toggleBtn).toBeVisible();
  });

  test('should toggle dark mode on and off', async ({ page }) => {
    // Check initial state
    const initialDark = await page.evaluate(() => document.documentElement.classList.contains('dark'));

    // Click toggle via JS dispatch (button is in a fixed sidebar that may be outside viewport)
    await page.evaluate(() => {
      const btn = document.querySelector('button.sidebar-toggle');
      if (btn) btn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await page.waitForTimeout(500);

    // Dark class should have changed
    const afterFirstClick = await page.evaluate(() => document.documentElement.classList.contains('dark'));
    expect(afterFirstClick).not.toBe(initialDark);

    // Click again to toggle back
    await page.evaluate(() => {
      const btn = document.querySelector('button.sidebar-toggle');
      if (btn) btn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await page.waitForTimeout(500);

    // Should return to original state
    const afterSecondClick = await page.evaluate(() => document.documentElement.classList.contains('dark'));
    expect(afterSecondClick).toBe(initialDark);
  });
});
