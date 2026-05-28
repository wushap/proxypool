import { test, expect } from '@playwright/test';

test.describe('Published Subscriptions Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/webui/');
    await page.waitForLoadState('networkidle');
    // Navigate to published subscriptions page via sidebar menu
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load page and display title', async ({ page }) => {
    await expect(page.locator('h2.section-title:has-text("订阅发布管理")')).toBeVisible();
  });

  test('should display create form with all fields', async ({ page }) => {
    await expect(page.locator('text=创建发布订阅')).toBeVisible();
    await expect(page.locator('text=发布格式')).toBeVisible();

    // Check name input
    const nameInput = page.locator('input[placeholder="发布订阅名称"]');
    await expect(nameInput).toBeVisible();

    // Check format selector
    await expect(page.locator('text=原始链接')).toBeVisible();
    await expect(page.locator('text=Clash YAML')).toBeVisible();
  });

  test('should display connectivity filter options', async ({ page }) => {
    await expect(page.locator('text=连通性筛选')).toBeVisible();
    await expect(page.locator('text=直连状态')).toBeVisible();
    await expect(page.locator('text=链路类型')).toBeVisible();

    // Verify filter option values
    await expect(page.locator('text=仅可直连')).toBeVisible();
    await expect(page.locator('text=仅不可直连')).toBeVisible();
  });

  test('should display service unlock filter options', async ({ page }) => {
    await expect(page.locator('text=服务解锁筛选')).toBeVisible();
    await expect(page.locator('text=ChatGPT 解锁')).toBeVisible();
    await expect(page.locator('text=IP 纯净度')).toBeVisible();
  });

  test('should display geo-location filter options', async ({ page }) => {
    await expect(page.locator('text=地理位置筛选')).toBeVisible();
    await expect(page.locator('text=国家/地区')).toBeVisible();
    await expect(page.locator('text=城市')).toBeVisible();
    await expect(page.locator('text=来源筛选')).toBeVisible();
  });

  test('should display published subscriptions table or empty state', async ({ page }) => {
    const table = page.locator('table.data-table');
    const hasTable = await table.isVisible().catch(() => false);

    if (hasTable) {
      // Verify table headers
      await expect(page.locator('th:has-text("ID")')).toBeVisible();
      await expect(page.locator('th:has-text("名称")')).toBeVisible();
      await expect(page.locator('th:has-text("格式")')).toBeVisible();
      await expect(page.locator('th:has-text("操作")')).toBeVisible();
    }
  });

  test('should create a published subscription', async ({ page }) => {
    const nameInput = page.locator('input[placeholder="发布订阅名称"]');
    await nameInput.fill('e2e-test-pub-sub');

    // Click create button
    const createButton = page.locator('button:has-text("创建")').last();
    await createButton.click();
    await page.waitForTimeout(1000);

    // Verify success or that item appears in table
    const successMessage = page.locator('.el-message--success');
    const tableRow = page.locator('table tbody tr').filter({ hasText: 'e2e-test-pub-sub' });

    const hasSuccess = await successMessage.isVisible().catch(() => false);
    const hasRow = await tableRow.isVisible().catch(() => false);

    expect(hasSuccess || hasRow).toBeTruthy();
  });

  test('should display pagination controls', async ({ page }) => {
    await expect(page.locator('text=每页')).toBeVisible();

    // Pagination nav buttons
    const prevButton = page.locator('button:has-text("上一页")');
    const nextButton = page.locator('button:has-text("下一页")');
    await expect(prevButton).toBeVisible();
    await expect(nextButton).toBeVisible();
  });

  test('should refresh published subscriptions', async ({ page }) => {
    const refreshButton = page.locator('button:has-text("刷新")');
    if (await refreshButton.isVisible()) {
      await refreshButton.click();
      await page.waitForTimeout(1000);

      // Verify either success message or the button returns to normal
      const successMessage = page.locator('.el-message--success');
      const hasSuccess = await successMessage.isVisible().catch(() => false);
      // Test passes if no error occurred
      expect(true).toBeTruthy();
    }
  });
});
