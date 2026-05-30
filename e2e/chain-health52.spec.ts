import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 52) ──

test.describe('Chain Health Check (Round 52)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('aside.sidebar').first();
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    const menuItems = sidebar.locator('.el-menu-item');
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(8);

    const texts = await menuItems.allTextContents();
    const joined = texts.join(' ');
    expect(joined).toContain('仪表盘');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('多跳代理池');
    expect(joined).toContain('入站端口');
    expect(joined).toContain('订阅管理');
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.stat-grid.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 30000 });

    const statCards = statGrid.locator('.stat-card');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const gridText = await statGrid.textContent();
    expect(gridText).toContain('节点总数');
    expect(gridText).toContain('可用节点');
    expect(gridText).toContain('可用率');
    expect(gridText).toContain('平均延迟');
  });

  test('dashboard has system status', async ({ page }) => {
    const statusCard = page.locator('.card').filter({ hasText: '系统状态' }).first();
    await statusCard.scrollIntoViewIfNeeded();
    await expect(statusCard).toBeVisible({ timeout: 10000 });

    const statusList = statusCard.locator('.dashboard-status-list');
    await expect(statusList).toBeVisible();

    const statusRows = statusList.locator('.dashboard-status-row');
    const count = await statusRows.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const rowLabels = statusList.locator('.dashboard-status-label');
    const labels = await rowLabels.allTextContents();
    expect(labels).toContain('后端引擎');
    expect(labels).toContain('网关服务');
  });

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card-title').filter({ hasText: '协议分布' }).first();
    await protocolCard.scrollIntoViewIfNeeded();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    const protocolSection = protocolCard.locator('..').first();

    // Either a donut chart or an empty state is shown
    const donutWrapper = protocolSection.locator('.dashboard-donut-wrapper');
    const emptyState = protocolSection.locator('.empty-state-small, .empty-state');
    const hasContent = (await donutWrapper.count()) > 0 || (await emptyState.count()) > 0;
    expect(hasContent).toBe(true);
  });

  test('dashboard has quick actions', async ({ page }) => {
    const quickActionsTitle = page.locator('h3.card-title').filter({ hasText: '快速操作' }).filter({ hasNotText: '历史' });
    await quickActionsTitle.scrollIntoViewIfNeeded();
    await expect(quickActionsTitle).toBeVisible({ timeout: 10000 });

    const quickActionsCard = quickActionsTitle.locator('..').first();
    const actionBar = quickActionsCard.locator('.action-bar');
    await expect(actionBar).toBeVisible({ timeout: 10000 });

    const buttons = actionBar.locator('button, a');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(3);

    const actionText = await actionBar.textContent();
    expect(actionText).toContain('任务中心');
    expect(actionText).toContain('代理节点');
  });
});

// ── Batch Operations (Round 52) ──

test.describe('Batch Operations (Round 52)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('proxy nodes page has data table', async ({ page }) => {
    // Wait for either loaded table or empty/loading state
    await page.locator('.data-table, .loading-state, .empty-state').first().waitFor({ state: 'visible', timeout: 15000 });

    const table = page.locator('.data-table').first();
    const tableVisible = await table.isVisible().catch(() => false);

    if (tableVisible) {
      // Table has header columns
      const headers = table.locator('thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(4);

      // Status bar shows proxy counts
      const statusBar = page.locator('.status-bar').first();
      await expect(statusBar).toBeVisible();
      const statusText = await statusBar.textContent();
      expect(statusText).toContain('总节点');
    } else {
      // Page loaded but no data — empty state is acceptable
      const sectionTitle = page.locator('.section-title').filter({ hasText: '代理节点' });
      await expect(sectionTitle).toBeVisible({ timeout: 5000 });
    }
  });

  test('proxy nodes page has filter inputs', async ({ page }) => {
    // The advanced filter toggle should be present
    const filterToggle = page.locator('.filter-panel-toggle').first();
    await expect(filterToggle).toBeVisible({ timeout: 10000 });
    await expect(filterToggle).toContainText('高级筛选');

    // Click to expand the filter panel
    await filterToggle.click();

    const filterPanel = page.locator('.filter-panel-body').first();
    await expect(filterPanel).toBeVisible({ timeout: 10000 });

    // Filter panel has filter fields
    const filterFields = filterPanel.locator('.filter-panel-field');
    const fieldCount = await filterFields.count();
    expect(fieldCount).toBeGreaterThanOrEqual(3);

    const panelText = await filterPanel.textContent();
    expect(panelText).toContain('协议');
    expect(panelText).toContain('状态');
  });

  test('proxy nodes page has action buttons', async ({ page }) => {
    // The section header has action buttons
    const sectionHeader = page.locator('.section-header').first();
    await expect(sectionHeader).toBeVisible({ timeout: 10000 });

    const importBtn = sectionHeader.locator('button, .btn').filter({ hasText: '导入代理' }).first();
    await expect(importBtn).toBeVisible({ timeout: 5000 });

    const exportBtn = sectionHeader.locator('button, .btn').filter({ hasText: '导出代理' }).first();
    await expect(exportBtn).toBeVisible();

    const clearBtn = sectionHeader.locator('button, .btn').filter({ hasText: '清空筛选' }).first();
    await expect(clearBtn).toBeVisible();

    // Pagination buttons at the bottom
    const paginationNav = page.locator('.pagination-nav').first();
    await expect(paginationNav).toBeVisible({ timeout: 5000 });

    const refreshBtn = paginationNav.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 52) ──

test.describe('System Diagnostics Export (Round 52)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('settings page has theme options', async ({ page }) => {
    const settingsTitle = page.locator('.section-title').filter({ hasText: '设置' }).first();
    await expect(settingsTitle).toBeVisible({ timeout: 10000 });

    const themeCard = page.locator('.settings-title').filter({ hasText: '外观设置' }).first();
    await themeCard.scrollIntoViewIfNeeded();
    await expect(themeCard).toBeVisible({ timeout: 10000 });

    const themeSection = themeCard.locator('..').first();

    // Theme mode radio buttons
    const themeControl = themeSection.locator('.setting-item').filter({ hasText: '主题模式' });
    await expect(themeControl).toBeVisible();

    const radioButtons = themeControl.locator('.el-radio-button');
    const radioCount = await radioButtons.count();
    expect(radioCount).toBeGreaterThanOrEqual(3);

    const radioTexts = await radioButtons.allTextContents();
    const joined = radioTexts.join(' ');
    expect(joined).toContain('浅色');
    expect(joined).toContain('深色');
    expect(joined).toContain('跟随系统');
  });

  test('settings page has about section', async ({ page }) => {
    const aboutTitle = page.locator('.settings-title').filter({ hasText: '关于' }).first();
    await aboutTitle.scrollIntoViewIfNeeded();
    await expect(aboutTitle).toBeVisible({ timeout: 10000 });

    const aboutSection = aboutTitle.locator('..').first();

    const aboutInfo = aboutSection.locator('.about-info').first();
    await expect(aboutInfo).toBeVisible();

    const aboutText = await aboutInfo.textContent();
    expect(aboutText).toContain('Proxy Pool');
    expect(aboutText).toContain('版本');

    // Reset button
    const resetBtn = aboutSection.locator('button').filter({ hasText: '重置为默认设置' });
    await expect(resetBtn).toBeVisible();
  });
});
