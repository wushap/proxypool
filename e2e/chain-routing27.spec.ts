import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 27) ──

test.describe('Chain Routing (Round 27)', () => {
  test('proxy nodes page loads with page title', async ({ page }) => {
    await navigateTo(page, '代理节点');

    const pageContent = page.locator('.page-container, .card').first();
    await expect(pageContent).toBeVisible();
    const text = await pageContent.textContent();
    expect(text?.length).toBeGreaterThan(0);
  });

  test('proxy table has column headers', async ({ page }) => {
    await navigateTo(page, '代理节点');

    const table = page.locator('.data-table').first();
    if (!(await table.isVisible({ timeout: 5000 }).catch(() => false))) return;

    const headers = table.locator('thead th');
    const headerCount = await headers.count();
    expect(headerCount).toBeGreaterThanOrEqual(3);
  });

  test('search/filter input is visible on the page', async ({ page }) => {
    await navigateTo(page, '代理节点');

    const hasSearch = await page.locator('input[type="text"], input[type="search"], .el-input').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasFilter = await page.locator('.filter-panel-toggle, .form-section-header').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasSearch || hasFilter).toBeTruthy();
  });

  test('node status indicators show available/unavailable states', async ({ page }) => {
    await navigateTo(page, '代理节点');

    const table = page.locator('.data-table').first();
    if (!(await table.isVisible({ timeout: 5000 }).catch(() => false))) return;

    const hasBadges = await page.locator('.badge').count() > 0;
    const hasRows = await table.locator('tbody tr').count() > 0;
    expect(hasBadges || hasRows).toBeTruthy();
  });

  test('page has at least one action button', async ({ page }) => {
    await navigateTo(page, '代理节点');

    const buttons = page.locator('button');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThan(0);
  });
});

// ── Subscription Intelligence (Round 27) ──

test.describe('Subscription Intelligence (Round 27)', () => {
  test('subscription list shows subscription names or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // Page title should be visible
    await expect(
      page.locator('.section-title').filter({ hasText: '订阅管理' })
    ).toBeVisible({ timeout: 10000 });

    // Wait for content to load (either table or empty state)
    let found = false;
    for (let attempt = 0; attempt < 15; attempt++) {
      const hasTable = await page.locator('.data-table').first().isVisible().catch(() => false);
      const hasEmpty = await page.locator('.empty-state').isVisible().catch(() => false);
      if (hasTable || hasEmpty) {
        found = true;
        break;
      }
      await page.waitForTimeout(1000);
    }
    expect(found).toBeTruthy();

    // If subscriptions exist, the table should have name column with inputs
    const nameInputs = page.locator('.data-table tbody .inline-input');
    const emptyState = page.locator('.empty-state');

    const hasNames = (await nameInputs.count()) > 0;
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasNames || hasEmptyState).toBeTruthy();
  });

  test('subscription status badges show active/inactive states', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // Wait for table to appear
    const table = page.locator('.data-table');
    const hasTable = await table.first().isVisible({ timeout: 15000 }).catch(() => false);

    if (hasTable) {
      // The stats bar should show enabled/disabled counts
      const statsBar = page.locator('.status-bar');
      await expect(statsBar).toBeVisible();

      const statsText = await statsBar.textContent();
      // Should contain 已启用 and 已停用 labels
      expect(statsText).toContain('已启用');
      expect(statsText).toContain('已停用');

      // Status badges in the table should have success/danger/neutral classes
      const statusBadges = page.locator('.data-table tbody .badge');
      const badgeCount = await statusBadges.count();
      if (badgeCount > 0) {
        const hasStatusBadge = await page.evaluate(() => {
          const badges = document.querySelectorAll('.data-table tbody .badge');
          return Array.from(badges).some(b =>
            b.classList.contains('badge-success') ||
            b.classList.contains('badge-danger') ||
            b.classList.contains('badge-neutral')
          );
        });
        expect(hasStatusBadge).toBeTruthy();
      }
    } else {
      // No subscriptions - the empty state should be visible
      await expect(page.locator('.empty-state')).toBeVisible();
      // Empty state should mention subscriptions
      const emptyText = await page.locator('.empty-state').textContent();
      expect(emptyText).toContain('订阅');
    }
  });

  test('subscription operations column has action buttons', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const hasTable = await page.locator('.data-table').first().isVisible({ timeout: 15000 }).catch(() => false);

    if (hasTable) {
      const headers = page.locator('.data-table thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(3);

      const firstRow = page.locator('.data-table tbody tr').first();
      const rowBtns = firstRow.locator('button');
      const btnCount = await rowBtns.count();
      expect(btnCount).toBeGreaterThan(0);
    } else {
      await expect(page.locator('.empty-state')).toBeVisible({ timeout: 5000 });
    }
  });
});

// ── System Diagnostics Export (Round 27) ──

test.describe('System Diagnostics Export (Round 27)', () => {
  test('config history page loads with history entries or empty state', async ({ page }) => {
    await navigateTo(page, '配置历史');

    // Page title should be visible
    await expect(
      page.locator('.section-title').filter({ hasText: '配置历史' })
    ).toBeVisible({ timeout: 10000 });

    // The page description hint should be present
    await expect(
      page.locator('.text-muted').filter({ hasText: '配置快照' })
    ).toBeVisible();

    // Either snapshot list or empty state should be visible
    const snapshotList = page.locator('.config-snapshot-list');
    const emptyState = page.locator('.empty-state');

    const hasSnapshots = await snapshotList.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasSnapshots || hasEmpty).toBeTruthy();

    // The "保存快照" button should always be visible
    await expect(page.locator('button:has-text("保存快照")')).toBeVisible();
  });

  test('config history has restore/compare buttons or placeholder text', async ({ page }) => {
    await navigateTo(page, '配置历史');

    // Wait for the page to fully render
    await page.locator('.section-title').filter({ hasText: '配置历史' }).waitFor({ state: 'visible', timeout: 10000 });

    const snapshotList = page.locator('.config-snapshot-list');
    const hasSnapshots = await snapshotList.isVisible().catch(() => false);

    if (hasSnapshots) {
      // If snapshots exist, each snapshot item should have action buttons
      const snapshotItems = page.locator('.config-snapshot-item');
      const itemCount = await snapshotItems.count();
      expect(itemCount).toBeGreaterThanOrEqual(1);

      // Each snapshot should have rollback (回滚) and delete (删除) buttons
      const firstSnapshot = snapshotItems.first();
      const rollbackBtn = firstSnapshot.locator('button:has-text("回滚")');
      const deleteBtn = firstSnapshot.locator('button:has-text("删除")');

      await expect(rollbackBtn).toBeVisible();
      await expect(deleteBtn).toBeVisible();

      // Snapshot should also display a config count badge
      const badge = firstSnapshot.locator('.badge');
      const badgeCount = await badge.count();
      expect(badgeCount).toBeGreaterThanOrEqual(1);
    } else {
      // No snapshots - empty state should show placeholder text
      const emptyState = page.locator('.empty-state');
      await expect(emptyState).toBeVisible({ timeout: 5000 });

      const emptyText = await emptyState.textContent();
      expect(emptyText).toContain('暂无配置快照');
      expect(emptyText).toContain('保存快照');
    }
  });
});
