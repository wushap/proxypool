import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 29) ──

test.describe('Chain Routing (Round 29)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
  });

  test('pool management tab shows pool creation form with name input', async ({ page }) => {
    // The default tab is "代理池" which shows the creation form
    const createCard = page.locator('.card').filter({ hasText: '创建代理池' }).first();
    await expect(createCard).toBeVisible({ timeout: 10000 });

    const nameInput = createCard.locator('input[placeholder*="exit-us-01"]');
    await expect(nameInput).toBeVisible();

    const nameLabel = createCard.locator('.form-label').filter({ hasText: '名称' }).first();
    await expect(nameLabel).toBeVisible();
  });

  test('pool table has at least 3 column headers', async ({ page }) => {
    const table = page.locator('.data-table').first();
    await expect(table).toBeVisible({ timeout: 10000 });

    const headers = table.locator('thead th');
    const headerCount = await headers.count();
    expect(headerCount).toBeGreaterThanOrEqual(3);
  });

  test('chain view tab switch works and shows content', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await chainViewTab.click();
    await page.waitForLoadState('domcontentloaded');

    // Chain view tab panel should be visible with its section divider
    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    const chainFlow = page.locator('.chain-flow');

    const hasSection = await chainSection.isVisible({ timeout: 5000 }).catch(() => false);
    const hasFlow = await chainFlow.isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasSection || hasFlow).toBeTruthy();
  });

  test('pool page has filter section with dropdowns', async ({ page }) => {
    // Open the filter section by clicking the header
    const filterHeader = page.locator('.form-section-header').filter({ hasText: '过滤条件' });
    await filterHeader.click();
    await page.waitForTimeout(300);

    // Verify filter dropdowns exist (ChatGPT, 家宽 selects)
    const chatgptSelect = page.locator('select').filter({ has: page.locator('option[value="unlocked"]') }).first();
    await expect(chatgptSelect).toBeVisible({ timeout: 5000 });

    const ipPuritySelect = page.locator('select').filter({ has: page.locator('option[value="residential"]') }).first();
    await expect(ipPuritySelect).toBeVisible();
  });

  test('pool page has refresh button', async ({ page }) => {
    const refreshButton = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshButton).toBeVisible();
    await expect(refreshButton).toBeEnabled();
  });
});

// ── Subscription Intelligence (Round 29) ──

test.describe('Subscription Intelligence (Round 29)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
  });

  test('subscription page has add form with name and URL inputs', async ({ page }) => {
    const nameInput = page.locator('input[placeholder="订阅名称"]');
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    const urlInput = page.locator('input[placeholder="订阅链接 URL"]');
    await expect(urlInput).toBeVisible();

    // Verify add button exists (use aria-label to disambiguate)
    const addButton = page.locator('button[aria-label="添加新订阅"]');
    await expect(addButton).toBeVisible();
  });

  test('subscription table has column headers or empty state', async ({ page }) => {
    // Either the table with headers is visible, or the empty state is shown
    const table = page.locator('.data-table').first();
    const hasTable = await table.isVisible({ timeout: 10000 }).catch(() => false);

    if (hasTable) {
      const headers = table.locator('thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(3);
    } else {
      const emptyState = page.locator('.empty-state-title').filter({ hasText: '暂无订阅' });
      await expect(emptyState).toBeVisible({ timeout: 5000 });
    }
  });

  test('subscription page has refresh all button', async ({ page }) => {
    const refreshAllButton = page.locator('button').filter({ hasText: '刷新全部' });
    await expect(refreshAllButton).toBeVisible({ timeout: 10000 });
    await expect(refreshAllButton).toBeEnabled();
  });
});

// ── System Diagnostics Export (Round 29) ──

test.describe('System Diagnostics Export (Round 29)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '设置');
  });

  test('settings page has theme radio buttons', async ({ page }) => {
    await expect(page.locator('text=外观设置')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=主题模式')).toBeVisible();

    const lightRadio = page.locator('.el-radio-button').filter({ hasText: '浅色' });
    await expect(lightRadio).toBeVisible();

    const darkRadio = page.locator('.el-radio-button').filter({ hasText: '深色' });
    await expect(darkRadio).toBeVisible();

    const autoRadio = page.locator('.el-radio-button').filter({ hasText: '跟随系统' });
    await expect(autoRadio).toBeVisible();
  });

  test('settings page has about section with version info', async ({ page }) => {
    const aboutCard = page.locator('.settings-card').filter({ hasText: '关于' }).first();
    await expect(aboutCard).toBeVisible({ timeout: 10000 });

    await expect(aboutCard.locator('.about-label').filter({ hasText: '应用名称' })).toBeVisible();
    await expect(aboutCard.locator('.about-value').filter({ hasText: 'Proxy Pool' })).toBeVisible();
    await expect(aboutCard.locator('.about-label').filter({ hasText: '版本' })).toBeVisible();
    await expect(aboutCard.locator('.about-value').filter({ hasText: '0.2.0' })).toBeVisible();
  });
});
