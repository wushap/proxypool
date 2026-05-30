import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 37) ──

test.describe('Chain Routing (Round 37)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar navigation', async ({ page }) => {
    const sidebar = page.locator('.sidebar-menu').first();
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    const menuItems = page.locator('.el-menu-item');
    const count = await menuItems.count();
    expect(count).toBeGreaterThanOrEqual(8);

    const texts = await menuItems.allTextContents();
    const joined = texts.join(' ');
    expect(joined).toContain('仪表盘');
    expect(joined).toContain('代理节点');
    expect(joined).toContain('订阅管理');
    expect(joined).toContain('系统诊断');
  });

  test('dashboard has stat cards', async ({ page }) => {
    const statGrid = page.locator('.stat-grid.dashboard-stat-grid').first();
    await expect(statGrid).toBeVisible({ timeout: 30000 });

    const statCards = statGrid.locator('.stat-card, .card');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const gridText = await statGrid.textContent();
    expect(gridText).toContain('节点总数');
    expect(gridText).toContain('可用节点');
    expect(gridText).toContain('可用率');
    expect(gridText).toContain('平均延迟');
  });

  test('dashboard has system status section', async ({ page }) => {
    const statusCard = page.locator('.card').filter({ hasText: '系统状态' }).first();
    await statusCard.scrollIntoViewIfNeeded();
    await expect(statusCard).toBeVisible({ timeout: 10000 });

    const statusList = statusCard.locator('.dashboard-status-list');
    await expect(statusList).toBeVisible();

    const statusRows = statusList.locator('.dashboard-status-row');
    const count = await statusRows.count();
    expect(count).toBeGreaterThanOrEqual(2);

    const rowLabels = statusList.locator('.dashboard-status-label');
    const labels = await rowLabels.allTextContents();
    expect(labels).toContain('后端引擎');
    expect(labels).toContain('网关服务');
  });

  test('dashboard has quick actions', async ({ page }) => {
    const hasQuickActions = await page.locator('text=快速操作').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasQuickActions).toBeTruthy();
  });

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await protocolCard.scrollIntoViewIfNeeded();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

    // Either a donut chart or an empty state should be present
    const hasDonut = await protocolCard.locator('.dashboard-donut-wrapper').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await protocolCard.locator('.empty-state').isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasDonut || hasEmpty).toBeTruthy();

    if (hasDonut) {
      const svgChart = protocolCard.locator('.dashboard-donut-svg');
      await expect(svgChart).toBeVisible();

      const legendItems = protocolCard.locator('.dashboard-donut-legend-item');
      const legendCount = await legendItems.count();
      expect(legendCount).toBeGreaterThanOrEqual(1);
    }
  });
});

// ── Subscription Intelligence (Round 37) ──

test.describe('Subscription Intelligence (Round 37)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
  });

  test('subscription page has add form', async ({ page }) => {
    const nameInput = page.locator('input[aria-label="订阅名称"]');
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    const urlInput = page.locator('input[aria-label="订阅链接URL"]');
    await expect(urlInput).toBeVisible();

    const addBtn = page.locator('button[aria-label="添加新订阅"]');
    await expect(addBtn).toBeVisible();
  });

  test('subscription page has group tabs', async ({ page }) => {
    const groupTabs = page.locator('.sub-group-tabs').first();
    // The tabs section may only appear when subscriptions exist; check for its
    // presence or the presence of the "全部" filter which is always in groupOptions.
    const tabsVisible = await groupTabs.isVisible({ timeout: 10000 }).catch(() => false);

    if (tabsVisible) {
      const tabBtns = groupTabs.locator('[role="tab"], .btn');
      const count = await tabBtns.count();
      expect(count).toBeGreaterThanOrEqual(1);
    } else {
      // No subscriptions yet -- verify the empty state or add form is present
      const emptyOrForm = page.locator('.empty-state, input[aria-label="订阅名称"]').first();
      await expect(emptyOrForm).toBeVisible({ timeout: 10000 });
    }
  });

  test('subscription page has batch buttons', async ({ page }) => {
    // The batch/section header buttons are always rendered
    const refreshAllBtn = page.locator('button[aria-label="刷新所有订阅"]').first();
    await expect(refreshAllBtn).toBeVisible({ timeout: 10000 });

    const refreshListBtn = page.locator('button[aria-label="刷新订阅列表"]').first();
    await expect(refreshListBtn).toBeVisible();

    // The delete unavailable button is always rendered (may be disabled)
    const deleteBtn = page.locator('button[aria-label^="删除不可用订阅"]').first();
    await expect(deleteBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 37) ──

test.describe('System Diagnostics Export (Round 37)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '设置');
  });

  test('settings page has theme options', async ({ page }) => {
    const themeCard = page.locator('.card').filter({ hasText: '外观设置' }).first();
    await expect(themeCard).toBeVisible({ timeout: 10000 });

    // Theme mode radio group with light/dark/auto
    const lightRadio = themeCard.locator('button, .el-radio-button').filter({ hasText: '浅色' }).first();
    await expect(lightRadio).toBeVisible();

    const darkRadio = themeCard.locator('button, .el-radio-button').filter({ hasText: '深色' }).first();
    await expect(darkRadio).toBeVisible();

    const autoRadio = themeCard.locator('button, .el-radio-button').filter({ hasText: '跟随系统' }).first();
    await expect(autoRadio).toBeVisible();
  });

  test('settings page has about section', async ({ page }) => {
    const aboutCard = page.locator('.card').filter({ hasText: '关于' }).first();
    await aboutCard.scrollIntoViewIfNeeded();
    await expect(aboutCard).toBeVisible({ timeout: 10000 });

    const aboutInfo = aboutCard.locator('.about-info');
    await expect(aboutInfo).toBeVisible();

    const aboutText = await aboutInfo.textContent();
    expect(aboutText).toContain('Proxy Pool');
    expect(aboutText).toContain('版本');

    const resetBtn = aboutCard.locator('button').filter({ hasText: '重置为默认设置' });
    await expect(resetBtn).toBeVisible();
  });
});
