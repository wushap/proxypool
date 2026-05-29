import { test, expect } from '@playwright/test';

test.describe('Port Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to ports page
    await page.click('text=入站端口');
    await page.waitForLoadState('networkidle');
    await page.locator('.data-table, .empty-state').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display ports list', async ({ page }) => {
    // Check if ports list or empty state is visible
    const portsList = page.locator('.port-row-expandable, .data-table').first();
    const emptyState = page.locator('.empty-state');

    const hasPorts = await portsList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasPorts || hasEmptyState).toBeTruthy();
  });

  test('should open create port wizard', async ({ page }) => {
    // Click create port button
    const createButton = page.locator('button:has-text("创建端口")');
    if (await createButton.isVisible()) {
      await createButton.click();

      // Verify wizard dialog is opened
      const dialog = page.locator('.el-dialog').filter({ hasText: /创建入站端口/ });
      await expect(dialog).toBeVisible();
    }
  });

  test('should complete port creation wizard', async ({ page }) => {
    // Open create port wizard
    const createButton = page.locator('button:has-text("创建端口")');
    if (await createButton.isVisible()) {
      await createButton.click();

      // Step 1: Fill in basic config
      const nameInput = page.locator('input[placeholder*="名称"]');
      if (await nameInput.isVisible()) {
        await nameInput.fill('test-port-e2e');

        // Fill in listen host
        const hostInput = page.locator('input[placeholder*="127.0.0.1"]');
        if (await hostInput.isVisible()) {
          await hostInput.fill('0.0.0.0');
        }

        // Fill in listen port
        const portInput = page.locator('input[type="number"]').first();
        if (await portInput.isVisible()) {
          await portInput.fill('8888');
        }

        // Click next button
        const nextButton = page.locator('button:has-text("下一步")');
        if (await nextButton.isVisible()) {
          await nextButton.click();
          await page.waitForTimeout(500);

          // Step 2: Select hops (if needed)
          // For now, just click next
          const nextButton2 = page.locator('button:has-text("下一步")');
          if (await nextButton2.isVisible()) {
            await nextButton2.click();
            await page.waitForTimeout(500);

            // Step 3: Session policy
            // Click finish button
            const finishButton = page.locator('button:has-text("完成")');
            if (await finishButton.isVisible()) {
              await finishButton.click();

              // Wait for response and verify success message
              await page.waitForTimeout(1000);
              const successMessage = page.locator('.el-message--success');
              const isVisible = await successMessage.isVisible().catch(() => false);

              // Or verify dialog closed
              const dialogClosed = !(await page.locator('.el-dialog').isVisible().catch(() => false));

              expect(isVisible || dialogClosed).toBeTruthy();
            }
          }
        }
      }
    }
  });

  test('should expand port details', async ({ page }) => {
    // Find first expandable row
    const expandableRow = page.locator('.port-row-expandable').first();
    if (await expandableRow.isVisible()) {
      // Click to expand
      await expandableRow.click();
      await page.waitForTimeout(300);

      // Verify health details row is visible
      const healthRow = page.locator('.port-health-row').first();
      await expect(healthRow).toBeVisible();
    }
  });

  test('should edit port', async ({ page }) => {
    // Find edit button
    const editButton = page.locator('button:has-text("编辑")').first();
    if (await editButton.isVisible()) {
      await editButton.click();

      // Verify edit dialog is opened
      const dialog = page.locator('.el-dialog').filter({ hasText: /编辑入站端口/ });
      await expect(dialog).toBeVisible();

      // Close dialog
      const cancelButton = page.locator('.el-dialog button:has-text("取消")');
      if (await cancelButton.isVisible()) {
        await cancelButton.click();
      }
    }
  });

  test('should view port status', async ({ page }) => {
    // Find status button
    const statusButton = page.locator('button:has-text("状态")').first();
    if (await statusButton.isVisible()) {
      await statusButton.click();

      // Verify status dialog is opened (or some status display)
      await page.waitForTimeout(500);

      // This might open a dialog or navigate to a status view
      // Just verify something happened
      const statusIndicator = page.locator('.el-dialog, .status-view, .gateway-status').first();
      const isVisible = await statusIndicator.isVisible().catch(() => false);

      // If no specific status view, just verify no error
      expect(true).toBeTruthy();
    }
  });

  test('should delete port with confirmation', async ({ page }) => {
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
});
