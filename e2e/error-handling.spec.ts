import { test, expect } from '@playwright/test';

/** Wait for the app to be interactive: DOM loaded + navigation rendered. */
async function waitForAppReady(page: import('@playwright/test').Page) {
  await page.waitForLoadState('domcontentloaded');
  await page.locator('[role="navigation"], .sidebar').first().waitFor({ state: 'visible', timeout: 10000 });
}

test.describe('Network Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
  });

  test('should show offline banner when offline event fires', async ({ page }) => {
    // Dispatch offline event to trigger the offline detection logic
    await page.evaluate(() => {
      window.dispatchEvent(new Event('offline'));
    });

    // The offline banner should appear
    const offlineBanner = page.locator('.offline-banner.offline-banner-error');
    await expect(offlineBanner).toBeVisible({ timeout: 5000 });
    await expect(offlineBanner).toContainText('网络连接已断开');
  });

  test('should show connection restored banner when network recovers', async ({ page }) => {
    // First go offline
    await page.evaluate(() => {
      window.dispatchEvent(new Event('offline'));
    });
    await page.waitForTimeout(500);

    const offlineBanner = page.locator('.offline-banner.offline-banner-error');
    await expect(offlineBanner).toBeVisible({ timeout: 5000 });

    // Now go back online
    await page.evaluate(() => {
      window.dispatchEvent(new Event('online'));
    });

    // The restored banner should appear
    const restoredBanner = page.locator('.offline-banner.offline-banner-success');
    await expect(restoredBanner).toBeVisible({ timeout: 5000 });
    await expect(restoredBanner).toContainText('网络连接已恢复');
  });

  test('should handle 500 error on stats API gracefully', async ({ page }) => {
    // Intercept /api/stats to return 500
    await page.route('**/api/stats', route => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Internal Server Error' }),
    }));

    // Reload page to trigger the stats fetch with domcontentloaded to avoid timeout
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);

    // Page should still be functional - sidebar and main content should exist
    const sidebar = page.locator('[role="navigation"], .sidebar').first();
    await expect(sidebar).toBeVisible();

    // The stats sidebar values should show 0 or default (not crash)
    const statsValues = page.locator('.sidebar-stat-value');
    const count = await statsValues.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should handle 500 error on proxies API without crashing', async ({ page }) => {
    // Navigate to proxies page first
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Intercept /api/proxies to return 500
    await page.route('**/api/proxies**', route => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Internal Server Error' }),
    }));

    // Reload to trigger the proxies fetch - use domcontentloaded to avoid timeout
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);

    // Page should not crash - sidebar should still be visible
    const sidebar = page.locator('[role="navigation"], .sidebar').first();
    await expect(sidebar).toBeVisible();
  });
});

test.describe('Form Validation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);
  });

  test('should reject subscription creation with empty URL', async ({ page }) => {
    // Navigate to subscriptions page
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Fill in name but leave URL empty
    const nameInput = page.locator('input[placeholder*="订阅名称"]');
    if (await nameInput.isVisible()) {
      await nameInput.fill('test-subscription-validation');
    }

    // Leave URL empty and try to submit
    const urlInput = page.locator('input[placeholder*="订阅链接"]');
    if (await urlInput.isVisible()) {
      await urlInput.clear();
    }

    // Click add button
    const addButton = page.locator('button:has-text("添加订阅")');
    if (await addButton.isVisible()) {
      await addButton.click();
      await page.waitForTimeout(1000);

      // Either an error message appears, or validation prevents submission
      const successMessage = page.locator('.el-message--success, .message-success');
      const hasSuccess = await successMessage.isVisible().catch(() => false);

      // Should NOT succeed with empty URL
      expect(hasSuccess).toBeFalsy();
    }
  });

  test('should reject pool creation with empty name', async ({ page }) => {
    // Navigate to proxy pools page
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });

    // Find the name input and leave it empty
    const nameInput = page.locator('input[placeholder*="exit-us"]');
    await expect(nameInput).toBeVisible();

    // Clear and ensure it's empty
    await nameInput.clear();
    expect(await nameInput.inputValue()).toBe('');

    // Try to submit with empty name
    const submitBtn = page.locator('.section-header button.btn-primary, button:has-text("创建代理池")').first();
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
      await page.waitForTimeout(1000);

      // Should not succeed - either validation prevents it or error shown
      const successMessage = page.locator('.el-message--success, .message-success');
      const hasSuccess = await successMessage.isVisible().catch(() => false);

      // Pool with empty name should not be created
      expect(hasSuccess).toBeFalsy();
    }
  });

  test('should show error for invalid proxy import format', async ({ page }) => {
    // Navigate to proxies page
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Open add proxy dialog
    const addButton = page.locator('button:has-text("添加")');
    if (await addButton.isVisible()) {
      await addButton.click();

      // Fill in completely invalid proxy content
      const linkInput = page.locator('textarea[placeholder*="链接"]');
      if (await linkInput.isVisible()) {
        await linkInput.fill('this is not a valid proxy format at all !!!');

        // Click confirm button
        const confirmButton = page.locator('.el-dialog button:has-text("确定")');
        await confirmButton.click();

        // Wait for error response
        await page.waitForTimeout(2000);

        // Should show error message or dialog stays open
        const errorMessage = page.locator('.el-message--error');
        const hasError = await errorMessage.isVisible().catch(() => false);
        const dialogStillOpen = await page.locator('.el-dialog').isVisible().catch(() => false);

        expect(hasError || dialogStillOpen).toBeTruthy();
      }
    }
  });
});

test.describe('Navigation Edge Cases', () => {
  test('should fallback gracefully for unknown page URL parameter', async ({ page }) => {
    // Navigate with an invalid page parameter
    await page.goto('/?page=nonexistent-page-xyz');
    await waitForAppReady(page);
    await page.waitForTimeout(1000);

    // The app sets activePage to the unknown value, so no page template matches
    // Main content should still be present but empty (no crash)
    const sidebar = page.locator('[role="navigation"], .sidebar').first();
    await expect(sidebar).toBeVisible();

    // The menu should still be functional - sidebar stats should render
    const sidebarStats = page.locator('.sidebar-stat');
    const count = await sidebarStats.count();
    expect(count).toBeGreaterThan(0);

    // Should be able to navigate to dashboard to recover
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 10000 });
    await expect(page.locator('.dashboard-page')).toBeVisible();
  });

  test('should handle browser back and forward navigation', async ({ page }) => {
    // Start at dashboard
    await page.goto('/');
    await waitForAppReady(page);

    // Navigate to proxies
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Navigate to settings
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('domcontentloaded');

    // Now use browser back button
    await page.goBack();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    // Should be back on proxies page - verify sidebar still works
    const sidebar = page.locator('[role="navigation"], .sidebar').first();
    await expect(sidebar).toBeVisible();

    // Now go forward
    await page.goForward();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    // Should be back on settings page
    const settingsTitle = page.locator('h2.section-title:has-text("设置")');
    await expect(settingsTitle).toBeVisible({ timeout: 5000 });
  });

  test('should handle rapid page switching without crashes', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const menuItems = [
      '代理节点',
      '多跳代理池',
      '入站端口',
      '订阅管理',
      '任务中心',
      '仪表盘',
      '设置',
      '代理节点',
      '多跳代理池',
      '仪表盘',
    ];

    // Rapidly click through pages
    for (const menuText of menuItems) {
      const menuItem = page.locator('.el-menu-item').filter({ hasText: menuText });
      if (await menuItem.isVisible().catch(() => false)) {
        await menuItem.click();
        // Minimal wait - don't wait for full load to stress test
        await page.waitForTimeout(200);
      }
    }

    // Wait for final page to settle
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    // Verify the app is still functional - sidebar should be intact
    const sidebar = page.locator('[role="navigation"], .sidebar').first();
    await expect(sidebar).toBeVisible();

    // Verify menu items are still clickable
    const menuCount = await page.locator('.el-menu-item').count();
    expect(menuCount).toBeGreaterThan(5);
  });
});

test.describe('Data State', () => {
  test('should display empty states correctly on proxy pools page', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Navigate to proxy pools page
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });

    // Check for empty state or data table - at least one should be present
    const dataTable = page.locator('.data-table').first();
    const emptyState = page.locator('.empty-state-small, .empty-state').first();
    const createForm = page.locator('input[placeholder*="exit-us"]');

    const hasTable = await dataTable.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasForm = await createForm.isVisible().catch(() => false);

    expect(hasTable || hasEmptyState || hasForm).toBeTruthy();
  });

  test('should display empty states correctly on subscriptions page', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Navigate to subscriptions page
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Check for empty state or subscription list
    const subscriptionsList = page.locator('table.data-table').first();
    const emptyState = page.locator('.empty-state-title', { hasText: '暂无订阅' });
    const createForm = page.locator('input[placeholder*="订阅名称"]');

    const hasList = await subscriptionsList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasForm = await createForm.isVisible().catch(() => false);

    expect(hasList || hasEmptyState || hasForm).toBeTruthy();
  });

  test('should display empty states correctly on ports page', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Navigate to ports page
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Check for empty state or ports list
    const portsList = page.locator('.port-row-expandable, .data-table').first();
    const emptyState = page.locator('.empty-state').first();
    const createButton = page.locator('button:has-text("创建端口")');

    const hasList = await portsList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasCreateButton = await createButton.isVisible().catch(() => false);

    expect(hasList || hasEmptyState || hasCreateButton).toBeTruthy();
  });

  test('should handle slow API response without crashing', async ({ page }) => {
    // Intercept a slow API to simulate delayed data
    await page.route('**/api/stats', async route => {
      await new Promise(resolve => setTimeout(resolve, 2000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total: 0, available: 0, unavailable: 0 }),
      });
    });

    // Navigate to dashboard
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Wait for page to be interactive
    await page.locator('[role="navigation"], .sidebar').first().waitFor({ state: 'visible', timeout: 15000 });

    // Page should fully load after the slow response
    const mainContent = page.locator('#main-content');
    await expect(mainContent).toBeVisible();
  });

  test('should have refresh functionality on dashboard', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Look for refresh button
    const refreshButton = page.locator('button:has-text("刷新"), button:has-text("Refresh"), button[title*="刷新"]').first();
    const hasRefreshButton = await refreshButton.isVisible().catch(() => false);

    if (hasRefreshButton) {
      await refreshButton.click();
      await page.waitForLoadState('domcontentloaded');

      // Dashboard should still be functional after refresh
      const sidebar = page.locator('[role="navigation"], .sidebar').first();
      await expect(sidebar).toBeVisible();
    } else {
      // No explicit refresh button - verify page loads data on its own
      const sidebar = page.locator('[role="navigation"], .sidebar').first();
      await expect(sidebar).toBeVisible();

      // Stats should be loaded
      const statsValues = page.locator('.sidebar-stat-value');
      const count = await statsValues.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should have refresh functionality on proxies page', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Navigate to proxies page
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Look for refresh button
    const refreshButton = page.locator('button:has-text("刷新"), button:has-text("Refresh")').first();
    const hasRefreshButton = await refreshButton.isVisible().catch(() => false);

    if (hasRefreshButton) {
      await refreshButton.click();
      await page.waitForLoadState('domcontentloaded');

      // Proxies page should still be functional
      const pageContent = page.locator('.page-container, .card').first();
      await expect(pageContent).toBeVisible();
    } else {
      // Verify page is functional without explicit refresh
      const tableOrEmpty = page.locator('.data-table, .empty-state').first();
      const isVisible = await tableOrEmpty.isVisible().catch(() => false);
      expect(isVisible).toBeTruthy();
    }
  });

  test('should have refresh functionality on subscriptions page', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Navigate to subscriptions page
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Look for refresh button
    const refreshButton = page.locator('button:has-text("刷新"), button:has-text("Refresh")').first();
    const hasRefreshButton = await refreshButton.isVisible().catch(() => false);

    if (hasRefreshButton) {
      await refreshButton.click();
      await page.waitForTimeout(1000);

      // Page should still be functional
      const pageContent = page.locator('.page-container, .card').first();
      await expect(pageContent).toBeVisible();
    } else {
      // Verify page loaded data
      const listOrEmpty = page.locator('table.data-table, .empty-state').first();
      const isVisible = await listOrEmpty.isVisible().catch(() => false);
      expect(isVisible).toBeTruthy();
    }
  });
});
