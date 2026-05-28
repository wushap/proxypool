import { test, expect } from '@playwright/test';

test.describe('Navigation and Cross-Page Flows', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/webui/');
    await page.waitForLoadState('networkidle');
  });

  test('should navigate through all main pages via sidebar', async ({ page }) => {
    const pages = [
      { menuText: '代理节点', titleText: '代理节点' },
      { menuText: '多跳代理池', titleText: '代理池' },
      { menuText: '入站端口', titleText: '入站端口' },
      { menuText: '订阅管理', titleText: '订阅' },
      { menuText: '任务中心', titleText: '任务' },
    ];

    for (const pageInfo of pages) {
      const menuItem = page.locator('.el-menu-item').filter({ hasText: pageInfo.menuText });
      if (await menuItem.isVisible()) {
        await menuItem.click();
        await page.waitForLoadState('networkidle');

        // Verify page loaded - check for any section title
        const pageContent = page.locator('.section-title, .page-container, .card').first();
        await expect(pageContent).toBeVisible();
      }
    }
  });

  test('should navigate to settings and back to dashboard', async ({ page }) => {
    // Go to settings
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h2.section-title:has-text("设置")')).toBeVisible();

    // Go back to dashboard
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.waitForLoadState('networkidle');

    // Dashboard should be visible
    const dashboardContent = page.locator('[class*="dashboard"], .section-title, .page-container').first();
    await expect(dashboardContent).toBeVisible();
  });

  test('should navigate to diagnostics, run check, then switch page', async ({ page }) => {
    // Go to diagnostics
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');

    // Run diagnostics
    await page.locator('button:has-text("一键诊断")').click();
    await page.waitForTimeout(3000);

    // Navigate to proxies page
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('networkidle');

    // Verify proxies page loaded
    const proxyContent = page.locator('.section-title, .page-container, .card').first();
    await expect(proxyContent).toBeVisible();
  });

  test('should persist settings when navigating away and back', async ({ page }) => {
    // Go to settings
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');

    // Change theme to dark
    const darkRadio = page.locator('.el-radio-button').filter({ hasText: '深色' });
    if (await darkRadio.isVisible()) {
      await darkRadio.click();
      await page.waitForTimeout(300);
    }

    // Navigate away to proxies
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.waitForLoadState('networkidle');

    // Navigate back to settings
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');

    // Verify dark mode is still selected
    const darkRadioAfter = page.locator('.el-radio-button').filter({ hasText: '深色' });
    if (await darkRadioAfter.isVisible()) {
      await expect(darkRadioAfter).toHaveAttribute('aria-pressed', 'true');
    }
  });

  test('should handle API error gracefully on diagnostics page', async ({ page }) => {
    // Go to diagnostics page
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');

    // Intercept API calls and simulate errors
    await page.route('**/api/backend/status', route => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Internal Server Error' }),
    }));

    // Run diagnostics
    await page.locator('button:has-text("一键诊断")').click();
    await page.waitForTimeout(2000);

    // Page should not crash - verify it's still functional
    await expect(page.locator('h2.section-title:has-text("系统诊断")')).toBeVisible();

    // Button should return to normal state
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });
});
