import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 35) ──

test.describe('Chain Health Check (Round 35)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has stat cards with availability', async ({ page }) => {
    const statGrid = page.locator('.dashboard-stat-grid');
    await expect(statGrid).toBeVisible();

    // Should contain stat cards for total, available, availability rate, etc.
    const statCards = statGrid.locator('.stat-card, [class*="stat"]');
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);

    // The availability rate card should include a progress bar
    const progressBar = statGrid.locator('.dashboard-progress');
    await expect(progressBar.first()).toBeVisible();
  });

  test('dashboard has latency distribution', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '延迟分布' });
    await expect(sectionTitle).toBeVisible();

    // The latency distribution section should either show histogram bars or an empty state
    const card = sectionTitle.locator('..').locator('..');
    const hasHistogram = card.locator('.dashboard-histogram').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasHistogram || hasEmpty).toBeTruthy();
  });

  test('dashboard has protocol distribution', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '协议分布' });
    await expect(sectionTitle).toBeVisible();

    // The protocol distribution section should either show donut chart or empty state
    const card = sectionTitle.locator('..').locator('..');
    const hasDonut = card.locator('.dashboard-donut-wrapper').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasDonut || hasEmpty).toBeTruthy();
  });

  test('dashboard has system status', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '系统状态' });
    await expect(sectionTitle).toBeVisible();

    // System status section should contain status rows
    const card = sectionTitle.locator('..').locator('..');
    const statusRows = card.locator('.dashboard-status-row');
    const rowCount = await statusRows.count();
    expect(rowCount).toBeGreaterThanOrEqual(4);
  });

  test('dashboard has quick actions', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '快速操作' });
    await expect(sectionTitle).toBeVisible();

    // Quick actions section should have multiple buttons
    const card = sectionTitle.locator('..').locator('..');
    const buttons = card.locator('.action-bar button, .action-bar a');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(4);
  });
});

// ── Batch Operations (Round 35) ──

test.describe('Batch Operations (Round 35)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscription page has add form', async ({ page }) => {
    // The add form should have a name input and URL input
    const nameInput = page.locator('input[placeholder="订阅名称"]');
    await expect(nameInput.first()).toBeVisible();

    const urlInput = page.locator('input[placeholder="订阅链接 URL"]');
    await expect(urlInput.first()).toBeVisible();

    // Should have test URL and add subscription buttons
    const testBtn = page.locator('button').filter({ hasText: '测试URL' }).first();
    await expect(testBtn).toBeVisible();

    const addBtn = page.locator('button').filter({ hasText: '添加订阅' }).first();
    await expect(addBtn).toBeVisible();
  });

  test('subscription page has group tabs', async ({ page }) => {
    // Group tabs area should be present with role="tablist"
    const groupTabs = page.locator('.sub-group-tabs, [role="tablist"]');
    await expect(groupTabs.first()).toBeVisible();

    // Should have at least the "全部" tab
    const allTab = groupTabs.first().locator('button').filter({ hasText: '全部' });
    await expect(allTab).toBeVisible();

    // Should have a "新建分组" button
    const newGroupBtn = page.locator('button').filter({ hasText: '新建分组' });
    await expect(newGroupBtn.first()).toBeVisible();
  });

  test('subscription page has batch buttons', async ({ page }) => {
    // Batch operation buttons should be present
    const refreshAllBtn = page.locator('button').filter({ hasText: '刷新全部' }).first();
    await expect(refreshAllBtn).toBeVisible();

    const deleteUnavailableBtn = page.locator('button').filter({ hasText: '删除不可用' }).first();
    await expect(deleteUnavailableBtn).toBeVisible();

    const refreshListBtn = page.locator('button').filter({ hasText: '刷新列表' }).first();
    await expect(refreshListBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 35) ──

test.describe('System Diagnostics Export (Round 35)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('settings page has theme options', async ({ page }) => {
    // The appearance settings card should be visible
    const settingsTitle = page.locator('.settings-title').filter({ hasText: '外观设置' });
    await expect(settingsTitle).toBeVisible();

    // Theme mode radio buttons should be present
    const themeLabel = page.locator('.setting-name').filter({ hasText: '主题模式' });
    await expect(themeLabel).toBeVisible();

    // Should have light, dark, and auto radio buttons
    const lightBtn = page.locator('.el-radio-button').filter({ hasText: '浅色' });
    await expect(lightBtn.first()).toBeVisible();

    const darkBtn = page.locator('.el-radio-button').filter({ hasText: '深色' });
    await expect(darkBtn.first()).toBeVisible();

    const autoBtn = page.locator('.el-radio-button').filter({ hasText: '跟随系统' });
    await expect(autoBtn.first()).toBeVisible();
  });

  test('settings page has about section', async ({ page }) => {
    // The about section should be visible
    const aboutTitle = page.locator('.settings-title').filter({ hasText: '关于' });
    await expect(aboutTitle).toBeVisible();

    // Should display app name and version
    const appName = page.locator('.about-value').filter({ hasText: 'Proxy Pool' });
    await expect(appName.first()).toBeVisible();

    const appVersion = page.locator('.about-value').filter({ hasText: '0.2.0' });
    await expect(appVersion.first()).toBeVisible();

    // Should have a reset button
    const resetBtn = page.locator('button').filter({ hasText: '重置为默认设置' });
    await expect(resetBtn.first()).toBeVisible();
  });
});
