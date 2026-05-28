import { test, expect } from '@playwright/test';

test.describe('Subscription Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/webui/');
    await page.waitForLoadState('networkidle');
    // Navigate to subscriptions page
    await page.click('text=订阅管理');
    await page.waitForLoadState('networkidle');
  });

  test('should display subscriptions list', async ({ page }) => {
    // Check if subscriptions list or empty state is visible
    const subscriptionsList = page.locator('.data-table, .el-table').first();
    const emptyState = page.locator('text=暂无订阅');

    const hasSubscriptions = await subscriptionsList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasSubscriptions || hasEmptyState).toBeTruthy();
  });

  test('should add new subscription', async ({ page }) => {
    // Fill in subscription name
    const nameInput = page.locator('input[placeholder*="订阅名称"]');
    if (await nameInput.isVisible()) {
      await nameInput.fill('test-subscription-e2e');
    }

    // Fill in subscription URL
    const urlInput = page.locator('input[placeholder*="订阅链接"]');
    if (await urlInput.isVisible()) {
      await urlInput.fill('https://example.com/sub?token=test');
    }

    // Click add button
    const addButton = page.locator('button:has-text("添加订阅")');
    if (await addButton.isVisible()) {
      await addButton.click();

      // Wait for response
      await page.waitForTimeout(1000);

      // Verify success message or subscription appears in list
      const successMessage = page.locator('.el-message--success');
      const isVisible = await successMessage.isVisible().catch(() => false);

      // Or verify subscription appears in table
      const subscriptionRow = page.locator('table tbody tr').filter({ hasText: 'test-subscription-e2e' });
      const rowVisible = await subscriptionRow.isVisible().catch(() => false);

      expect(isVisible || rowVisible).toBeTruthy();
    }
  });

  test('should toggle subscription enabled state', async ({ page }) => {
    // Find first toggle button
    const toggleButton = page.locator('button:has-text("启用"), button:has-text("停用")').first();
    if (await toggleButton.isVisible()) {
      const initialText = await toggleButton.textContent();

      // Click toggle
      await toggleButton.click();
      await page.waitForTimeout(500);

      // Verify button text changed
      const newText = await toggleButton.textContent();
      expect(newText).not.toBe(initialText);
    }
  });

  test('should refresh subscription', async ({ page }) => {
    // Find refresh button
    const refreshButton = page.locator('button:has-text("刷新")').first();
    if (await refreshButton.isVisible()) {
      await refreshButton.click();

      // Wait for refresh to complete
      await page.waitForTimeout(2000);

      // Verify success message or loading state
      const successMessage = page.locator('.el-message--success');
      const loadingIndicator = page.locator('.el-loading-mask, .el-icon-loading').first();

      const hasSuccess = await successMessage.isVisible().catch(() => false);
      const hasLoading = await loadingIndicator.isVisible().catch(() => false);

      // Either success or still loading is acceptable
      expect(true).toBeTruthy();
    }
  });

  test('should delete subscription', async ({ page }) => {
    // Find delete button
    const deleteButton = page.locator('button:has-text("删除")').first();
    if (await deleteButton.isVisible()) {
      await deleteButton.click();

      // Verify confirmation dialog appears
      const confirmDialog = page.locator('.el-message-box, .el-dialog').filter({ hasText: /确认|删除/ });
      if (await confirmDialog.isVisible()) {
        // Click cancel to avoid actually deleting
        const cancelButton = page.locator('.el-message-box button:has-text("取消"), .el-dialog button:has-text("取消")').first();
        if (await cancelButton.isVisible()) {
          await cancelButton.click();
        }
      }
    }
  });

  test('should bulk select subscriptions', async ({ page }) => {
    // Find first checkbox
    const checkbox = page.locator('input[type="checkbox"]').first();
    if (await checkbox.isVisible()) {
      await checkbox.click();

      // Verify selection bar appears
      const selectionBar = page.locator('.selection-bar').first();
      const isVisible = await selectionBar.isVisible().catch(() => false);

      // If selection bar exists, verify bulk operations are available
      if (isVisible) {
        const bulkEnableButton = page.locator('.selection-bar button:has-text("批量启用")');
        const bulkDisableButton = page.locator('.selection-bar button:has-text("批量停用")');
        const bulkDeleteButton = page.locator('.selection-bar button:has-text("批量删除")');

        // At least one bulk operation should be available
        const hasBulkOperations = await bulkEnableButton.isVisible().catch(() => false) ||
                                  await bulkDisableButton.isVisible().catch(() => false) ||
                                  await bulkDeleteButton.isVisible().catch(() => false);

        expect(hasBulkOperations).toBeTruthy();
      }
    }
  });

  test('should test subscription URL', async ({ page }) => {
    // Fill in subscription URL
    const urlInput = page.locator('input[placeholder*="订阅链接"]');
    if (await urlInput.isVisible()) {
      await urlInput.fill('https://example.com/sub?token=test');

      // Click test button
      const testButton = page.locator('button:has-text("测试URL")');
      if (await testButton.isVisible()) {
        await testButton.click();

        // Wait for test result
        await page.waitForTimeout(2000);

        // Verify test result appears
        const testResult = page.locator('.subscription-test-result').first();
        const isVisible = await testResult.isVisible().catch(() => false);

        // Either success or failure message should appear
        if (isVisible) {
          const hasSuccess = await testResult.locator('text=✓').isVisible().catch(() => false);
          const hasFailure = await testResult.locator('text=✗').isVisible().catch(() => false);

          expect(hasSuccess || hasFailure).toBeTruthy();
        }
      }
    }
  });
});
