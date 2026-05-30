import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 20000 });
}

// ── Chain Routing (Round 44) ──

test.describe('Chain Routing (Round 44)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
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
    expect(joined).toContain('入站端口');
    expect(joined).toContain('订阅管理');
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

  test('dashboard has system status', async ({ page }) => {
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

  test('dashboard has protocol distribution', async ({ page }) => {
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
    await protocolCard.scrollIntoViewIfNeeded();
    await expect(protocolCard).toBeVisible({ timeout: 10000 });

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

  test('dashboard has quick actions', async ({ page }) => {
    const buttons = page.locator('button:has-text("任务中心"), button:has-text("创建代理池"), button:has-text("导入节点")');
    const btnCount = await buttons.count();
    expect(btnCount).toBeGreaterThanOrEqual(2);
  });
});

// ── Subscription Intelligence (Round 44) ──

test.describe('Subscription Intelligence (Round 44)', () => {
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
    const tabsVisible = await groupTabs.isVisible({ timeout: 10000 }).catch(() => false);

    if (tabsVisible) {
      const tabBtns = groupTabs.locator('[role="tab"], .btn');
      const count = await tabBtns.count();
      expect(count).toBeGreaterThanOrEqual(1);
    } else {
      const emptyOrForm = page.locator('.empty-state, input[aria-label="订阅名称"]').first();
      await expect(emptyOrForm).toBeVisible({ timeout: 10000 });
    }
  });

  test('subscription page has batch buttons', async ({ page }) => {
    const refreshAllBtn = page.locator('button[aria-label="刷新所有订阅"]').first();
    await expect(refreshAllBtn).toBeVisible({ timeout: 10000 });

    const refreshListBtn = page.locator('button[aria-label="刷新订阅列表"]').first();
    await expect(refreshListBtn).toBeVisible();

    const deleteBtn = page.locator('button[aria-label^="删除不可用订阅"]').first();
    await expect(deleteBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 44) ──

test.describe('System Diagnostics Export (Round 44)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '设置');
  });

  test('settings page has theme options', async ({ page }) => {
    const hasTheme = await page.locator('text=外观设置').first().isVisible({ timeout: 10000 }).catch(() => false);
    expect(hasTheme).toBeTruthy();
  });

  test('settings page has about section', async ({ page }) => {
    const aboutTitle = page.locator('.settings-title').filter({ hasText: '关于' });
    await aboutTitle.scrollIntoViewIfNeeded();
    await expect(aboutTitle).toBeVisible({ timeout: 10000 });

    const aboutSection = aboutTitle.locator('..').first();
    await expect(aboutSection).toBeVisible();

    const versionInfo = page.locator('.about-section, .version-info, [class*="about"]').first();
    const hasVersion = await versionInfo.isVisible({ timeout: 5000 }).catch(() => false);

    const aboutText = aboutSection.textContent();
    const hasAboutContent = aboutText && aboutText.length > 5;

    expect(hasVersion || hasAboutContent).toBeTruthy();
  });
});
