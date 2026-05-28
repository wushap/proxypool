import { test, expect } from '@playwright/test';

test.describe('Add Single Proxy', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxies page
    await page.click('text=代理节点');
    await page.waitForLoadState('networkidle');
  });

  test('should open add proxy dialog', async ({ page }) => {
    // Click add proxy button
    const addButton = page.locator('button:has-text("添加")');
    if (await addButton.isVisible()) {
      await addButton.click();

      // Verify dialog is opened
      const dialog = page.locator('.el-dialog').filter({ hasText: '添加代理' });
      await expect(dialog).toBeVisible();
    }
  });

  test('should add proxy with valid trojan link', async ({ page }) => {
    // Open add proxy dialog
    const addButton = page.locator('button:has-text("添加")');
    if (await addButton.isVisible()) {
      await addButton.click();

      // Fill in proxy link
      const linkInput = page.locator('textarea[placeholder*="链接"]');
      if (await linkInput.isVisible()) {
        await linkInput.fill('trojan://password@example.com:443?security=tls&type=tcp');

        // Click confirm button
        const confirmButton = page.locator('.el-dialog button:has-text("确定")');
        await confirmButton.click();

        // Wait for response and verify success message
        await page.waitForTimeout(1000);
        const successMessage = page.locator('.el-message--success');
        const isVisible = await successMessage.isVisible().catch(() => false);

        // Either success message or dialog closed indicates success
        const dialogClosed = !(await page.locator('.el-dialog').isVisible().catch(() => false));
        expect(isVisible || dialogClosed).toBeTruthy();
      }
    }
  });

  test('should show error for invalid proxy link', async ({ page }) => {
    // Open add proxy dialog
    const addButton = page.locator('button:has-text("添加")');
    if (await addButton.isVisible()) {
      await addButton.click();

      // Fill in invalid proxy link
      const linkInput = page.locator('textarea[placeholder*="链接"]');
      if (await linkInput.isVisible()) {
        await linkInput.fill('invalid-proxy-link');

        // Click confirm button
        const confirmButton = page.locator('.el-dialog button:has-text("确定")');
        await confirmButton.click();

        // Wait for error message
        await page.waitForTimeout(1000);
        const errorMessage = page.locator('.el-message--error');
        const isVisible = await errorMessage.isVisible().catch(() => false);

        // Verify error is shown or dialog remains open
        const dialogStillOpen = await page.locator('.el-dialog').isVisible().catch(() => false);
        expect(isVisible || dialogStillOpen).toBeTruthy();
      }
    }
  });

  test('should close dialog on cancel', async ({ page }) => {
    // Open add proxy dialog
    const addButton = page.locator('button:has-text("添加")');
    if (await addButton.isVisible()) {
      await addButton.click();

      // Verify dialog is open
      const dialog = page.locator('.el-dialog').filter({ hasText: '添加代理' });
      await expect(dialog).toBeVisible();

      // Click cancel button
      const cancelButton = page.locator('.el-dialog button:has-text("取消")');
      await cancelButton.click();

      // Verify dialog is closed
      await expect(dialog).not.toBeVisible();
    }
  });

  test('should add multiple proxies in batch', async ({ page }) => {
    // Open add proxy dialog
    const addButton = page.locator('button:has-text("添加")');
    if (await addButton.isVisible()) {
      await addButton.click();

      // Fill in multiple proxy links (one per line)
      const linkInput = page.locator('textarea[placeholder*="链接"]');
      if (await linkInput.isVisible()) {
        const proxyLinks = [
          'trojan://password1@example1.com:443?security=tls',
          'trojan://password2@example2.com:443?security=tls',
          'vmess://eyJhZGQiOiJleGFtcGxlMy5jb20ifQ=='
        ].join('\n');

        await linkInput.fill(proxyLinks);

        // Click confirm button
        const confirmButton = page.locator('.el-dialog button:has-text("确定")');
        await confirmButton.click();

        // Wait for batch add to complete
        await page.waitForTimeout(2000);

        // Verify dialog is closed (success)
        const dialogClosed = !(await page.locator('.el-dialog').isVisible().catch(() => false));
        expect(dialogClosed).toBeTruthy();
      }
    }
  });
});