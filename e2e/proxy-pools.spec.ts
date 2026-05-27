import { test, expect } from '@playwright/test';

test.describe('Proxy Pools Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/webui/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxy pools page
    await page.click('text=多跳代理池');
    await page.waitForLoadState('networkidle');
  });

  test('should display proxy pools list', async ({ page }) => {
    // Check if pools list or empty state is visible
    const poolsList = page.locator('.pool-item, .el-card').first();
    const emptyState = page.locator('text=暂无代理池');

    const hasPools = await poolsList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasPools || hasEmptyState).toBeTruthy();
  });

  test('should open create pool dialog', async ({ page }) => {
    // Click create pool button
    const createButton = page.locator('button:has-text("创建")');
    if (await createButton.isVisible()) {
      await createButton.click();

      // Verify dialog is opened
      const dialog = page.locator('.el-dialog').filter({ hasText: /创建|新建/ });
      await expect(dialog).toBeVisible();
    }
  });

  test('should create new proxy pool', async ({ page }) => {
    // Open create pool dialog
    const createButton = page.locator('button:has-text("创建")');
    if (await createButton.isVisible()) {
      await createButton.click();

      // Fill in pool name
      const nameInput = page.locator('input[placeholder*="名称"]');
      if (await nameInput.isVisible()) {
        await nameInput.fill('test-pool-e2e');

        // Fill in description if available
        const descInput = page.locator('textarea[placeholder*="描述"]');
        if (await descInput.isVisible()) {
          await descInput.fill('E2E test pool');
        }

        // Click confirm button
        const confirmButton = page.locator('.el-dialog button:has-text("确定")');
        await confirmButton.click();

        // Wait for creation
        await page.waitForTimeout(1000);

        // Verify success message or dialog closed
        const successMessage = page.locator('.el-message--success');
        const dialogClosed = !(await page.locator('.el-dialog').isVisible().catch(() => false));

        expect(
          (await successMessage.isVisible().catch(() => false)) || dialogClosed
        ).toBeTruthy();
      }
    }
  });

  test('should show error for duplicate pool name', async ({ page }) => {
    // Create a pool first
    const createButton = page.locator('button:has-text("创建")');
    if (await createButton.isVisible()) {
      await createButton.click();

      const nameInput = page.locator('input[placeholder*="名称"]');
      if (await nameInput.isVisible()) {
        await nameInput.fill('duplicate-pool');

        const confirmButton = page.locator('.el-dialog button:has-text("确定")');
        await confirmButton.click();
        await page.waitForTimeout(1000);

        // Try to create another pool with same name
        if (await createButton.isVisible()) {
          await createButton.click();

          const nameInput2 = page.locator('input[placeholder*="名称"]');
          await nameInput2.fill('duplicate-pool');

          const confirmButton2 = page.locator('.el-dialog button:has-text("确定")');
          await confirmButton2.click();

          await page.waitForTimeout(1000);

          // Verify error message
          const errorMessage = page.locator('.el-message--error');
          const isVisible = await errorMessage.isVisible().catch(() => false);
          expect(isVisible).toBeTruthy();
        }
      }
    }
  });

  test('should view pool details', async ({ page }) => {
    // Find and click first pool item
    const poolItem = page.locator('.pool-item, .el-card').first();
    if (await poolItem.isVisible()) {
      await poolItem.click();

      // Verify pool details are shown
      const detailsSection = page.locator('.pool-details, .el-drawer');
      await expect(detailsSection).toBeVisible();
    }
  });

  test('should delete proxy pool', async ({ page }) => {
    // Find delete button for a pool
    const deleteButton = page.locator('button:has-text("删除")').first();
    if (await deleteButton.isVisible()) {
      await deleteButton.click();

      // Confirm deletion in dialog
      const confirmDialog = page.locator('.el-message-box, .el-dialog').filter({ hasText: '确认' });
      if (await confirmDialog.isVisible()) {
        const confirmButton = confirmDialog.locator('button:has-text("确定")');
        await confirmButton.click();

        await page.waitForTimeout(1000);

        // Verify success message
        const successMessage = page.locator('.el-message--success');
        expect(await successMessage.isVisible().catch(() => false)).toBeTruthy();
      }
    }
  });

  test('should cancel pool creation', async ({ page }) => {
    // Open create pool dialog
    const createButton = page.locator('button:has-text("创建")');
    if (await createButton.isVisible()) {
      await createButton.click();

      // Verify dialog is open
      const dialog = page.locator('.el-dialog').filter({ hasText: /创建|新建/ });
      await expect(dialog).toBeVisible();

      // Fill in name
      const nameInput = page.locator('input[placeholder*="名称"]');
      if (await nameInput.isVisible()) {
        await nameInput.fill('cancelled-pool');
      }

      // Click cancel button
      const cancelButton = page.locator('.el-dialog button:has-text("取消")');
      await cancelButton.click();

      // Verify dialog is closed
      await expect(dialog).not.toBeVisible();
    }
  });
});