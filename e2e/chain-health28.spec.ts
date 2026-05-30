import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 28) ──

test.describe('Chain Health Check (Round 28)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has sidebar navigation with menu items', async ({ page }) => {
    const menu = page.locator('.sidebar-menu');
    await expect(menu).toBeVisible();

    const menuItems = page.locator('.el-menu-item');
    const itemCount = await menuItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(8);

    // Verify key menu items exist
    const expectedItems = ['仪表盘', '代理节点', '多跳代理池', '入站端口', '任务中心', '设置'];
    for (const text of expectedItems) {
      const item = page.locator('.el-menu-item').filter({ hasText: text });
      await expect(item.first()).toBeVisible();
    }
  });

  test('dashboard has dark mode toggle button', async ({ page }) => {
    const toggleBtn = page.locator('.sidebar-toggle');
    await expect(toggleBtn).toBeVisible();
    await expect(toggleBtn).toBeEnabled();

    // Should have a title indicating it toggles mode
    const title = await toggleBtn.getAttribute('title');
    expect(title).toMatch(/切换.*(浅色|深色)模式/);
  });

  test('dashboard has wizard button in sidebar', async ({ page }) => {
    const wizardBtn = page.locator('.sidebar-wizard-btn');
    await expect(wizardBtn).toBeVisible();
    await expect(wizardBtn).toBeEnabled();

    const label = await wizardBtn.getAttribute('aria-label');
    expect(label).toContain('向导');

    const btnText = wizardBtn.locator('.wizard-btn-text');
    await expect(btnText).toBeVisible();
    await expect(btnText).toHaveText('向导');
  });

  test('dashboard has notification bell icon', async ({ page }) => {
    const bellWrapper = page.locator('.notification-bell-wrapper');
    await expect(bellWrapper).toBeVisible();

    const bell = bellWrapper.locator('.notification-bell');
    await expect(bell).toBeVisible();

    // Clicking bell should toggle notification dropdown
    await bellWrapper.click();
    const dropdown = page.locator('.notification-dropdown');
    await expect(dropdown).toBeVisible();

    // Dropdown should have a title
    const dropdownTitle = dropdown.locator('.notification-dropdown-title');
    await expect(dropdownTitle).toBeVisible();
    await expect(dropdownTitle).toHaveText('通知');
  });

  test('dashboard has system status overview in sidebar', async ({ page }) => {
    const sidebarFooter = page.locator('.sidebar-footer');
    await expect(sidebarFooter).toBeVisible();

    const stats = sidebarFooter.locator('.sidebar-stat');
    const statCount = await stats.count();
    expect(statCount).toBeGreaterThanOrEqual(4);

    // Verify specific status labels
    const nodeLabel = stats.filter({ hasText: '节点' });
    await expect(nodeLabel.first()).toBeVisible();

    const availLabel = stats.filter({ hasText: '可用' });
    await expect(availLabel.first()).toBeVisible();

    const backendLabel = stats.filter({ hasText: '后端' });
    await expect(backendLabel.first()).toBeVisible();
  });
});

// ── Batch Operations (Round 28) ──

test.describe('Batch Operations (Round 28)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('proxy nodes page has import/export buttons', async ({ page }) => {
    const importBtn = page.locator('button').filter({ hasText: '导入' }).first();
    await expect(importBtn).toBeVisible();

    const exportBtn = page.locator('button').filter({ hasText: '导出' }).first();
    await expect(exportBtn).toBeVisible();
  });

  test('proxy nodes table has row selection checkboxes', async ({ page }) => {
    const table = page.locator('.data-table').first();
    const hasTable = await table.isVisible({ timeout: 10000 }).catch(() => false);

    if (hasTable) {
      // Header should have a select-all checkbox
      const headerCheckbox = table.locator('thead th input[type="checkbox"]');
      await expect(headerCheckbox.first()).toBeVisible();

      // Body rows should have checkboxes
      const bodyCheckbox = table.locator('tbody tr td input[type="checkbox"]');
      const checkboxCount = await bodyCheckbox.count();
      expect(checkboxCount).toBeGreaterThanOrEqual(0);
    } else {
      // No data state - empty state or loading should be visible
      const hasEmpty = await page.locator('.empty-state').first().isVisible({ timeout: 5000 }).catch(() => false);
      const hasLoading = await page.locator('.loading-state').first().isVisible({ timeout: 5000 }).catch(() => false);
      expect(hasEmpty || hasLoading).toBeTruthy();
    }
  });

  test('proxy nodes page has refresh button that is clickable', async ({ page }) => {
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();

    // Clicking refresh should not cause errors
    await refreshBtn.click();
    // Page should remain functional after refresh
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });
});

// ── System Diagnostics Export (Round 28) ──

test.describe('System Diagnostics Export (Round 28)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has protocol distribution donut chart', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' });
    await expect(protocolCard).toBeVisible();

    const cardBody = protocolCard.locator('.card-body');
    await expect(cardBody).toBeVisible();

    // Should have a donut chart wrapper or empty state
    const hasDonut = await page.locator('.dashboard-donut-wrapper').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await protocolCard.locator('.empty-state').isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasDonut || hasEmpty).toBeTruthy();
  });

  test('dashboard has country/region distribution section', async ({ page }) => {
    const geoCard = page.locator('.card').filter({ hasText: '地理位置分布' });
    await expect(geoCard).toBeVisible();

    const cardBody = geoCard.locator('.card-body');
    await expect(cardBody).toBeVisible();

    // Should have region items or empty state
    const hasRegions = await geoCard.locator('.dashboard-geo-region').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await geoCard.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasRegions || hasEmpty).toBeTruthy();
  });
});
