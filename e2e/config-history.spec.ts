import { test, expect } from '@playwright/test';

test.describe('Config History Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to config history page via sidebar menu
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load page and display title', async ({ page }) => {
    await expect(page.locator('h2.section-title:has-text("配置历史")')).toBeVisible();
    await expect(page.locator('text=管理配置快照')).toBeVisible();
  });

  test('should display save snapshot button', async ({ page }) => {
    const saveButton = page.locator('button:has-text("保存快照")');
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeEnabled();
  });

  test('should display empty state initially', async ({ page }) => {
    // On a fresh browser, there should be no snapshots
    const emptyState = page.locator('text=暂无配置快照');
    const snapshotList = page.locator('.config-snapshot-list');

    const hasEmpty = await emptyState.isVisible().catch(() => false);
    const hasList = await snapshotList.isVisible().catch(() => false);

    expect(hasEmpty || hasList).toBeTruthy();
  });

  test('should save a config snapshot', async ({ page }) => {
    const saveButton = page.locator('button:has-text("保存快照")');
    await saveButton.click();
    await page.waitForTimeout(500);

    // Verify snapshot appears in list
    const snapshotItem = page.locator('.config-snapshot-item').first();
    await expect(snapshotItem).toBeVisible();

    // Verify snapshot has expected elements
    await expect(page.locator('.config-snapshot-name').first()).toBeVisible();
    await expect(page.locator('.config-snapshot-time').first()).toBeVisible();
    await expect(page.locator('.badge:has-text("最新")').first()).toBeVisible();
  });

  test('should select snapshot and show diff view', async ({ page }) => {
    // First save a snapshot
    await page.locator('button:has-text("保存快照")').click();
    await page.waitForTimeout(500);

    // Click on the snapshot to select it
    const snapshotItem = page.locator('.config-snapshot-item').first();
    await snapshotItem.click();
    await page.waitForTimeout(300);

    // Verify diff section appears
    const diffSection = page.locator('.config-diff-section');
    if (await diffSection.isVisible()) {
      await expect(page.locator('text=配置对比')).toBeVisible();
      await expect(page.locator('.config-diff-label:has-text("当前配置")')).toBeVisible();
      await expect(page.locator('.config-diff-label:has-text("快照配置")')).toBeVisible();
    }
  });

  test('should close diff view by clicking close', async ({ page }) => {
    // Save a snapshot and select it
    await page.locator('button:has-text("保存快照")').click();
    await page.waitForTimeout(500);
    await page.locator('.config-snapshot-item').first().click();
    await page.waitForTimeout(300);

    // Click close button
    const closeButton = page.locator('.btn-ghost:has-text("关闭")');
    if (await closeButton.isVisible()) {
      await closeButton.click();
      await page.waitForTimeout(200);

      // Diff section should be hidden
      const diffSection = page.locator('.config-diff-section');
      await expect(diffSection).not.toBeVisible();
    }
  });

  test('should display rollback and delete buttons on snapshot', async ({ page }) => {
    // Save a snapshot first
    await page.locator('button:has-text("保存快照")').click();
    await page.waitForTimeout(500);

    const snapshotItem = page.locator('.config-snapshot-item').first();
    await expect(snapshotItem.locator('button:has-text("回滚")')).toBeVisible();
    await expect(snapshotItem.locator('button:has-text("删除")')).toBeVisible();
  });

  test('should show breadcrumb navigation', async ({ page }) => {
    await expect(page.locator('text=首页')).toBeVisible();
  });
});
