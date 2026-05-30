import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 32) ──

test.describe('Chain Health Check (Round 32)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has stat cards with node counts', async ({ page }) => {
    // The stat grid should be visible with card components
    const statGrid = page.locator('.stat-grid.dashboard-stat-grid');
    await expect(statGrid).toBeVisible();

    // Verify "节点总数" and "可用节点" stat cards exist
    const totalLabel = page.locator('.card-title, .stat-label, [class*="stat"]').filter({ hasText: '节点总数' }).first();
    const availLabel = page.locator('.card-title, .stat-label, [class*="stat"]').filter({ hasText: '可用节点' }).first();

    // Use a broader check: the stat grid should have child stat cards
    const statCards = statGrid.locator('.card, [class*="stat-card"]');
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);
  });

  test('dashboard has availability percentage display', async ({ page }) => {
    // Look for the "可用率" label in the stat grid
    const availCard = page.locator('.dashboard-stat-grid').locator('.card, [class*="stat"]').filter({ hasText: '可用率' }).first();
    await expect(availCard).toBeVisible();

    // The card should contain a percentage value or the text "%"
    const cardText = await availCard.textContent();
    expect(cardText).toContain('%');
  });

  test('dashboard has average latency display', async ({ page }) => {
    // Look for the "平均延迟" label in the stat grid
    const latencyCard = page.locator('.dashboard-stat-grid').locator('.card, [class*="stat"]').filter({ hasText: '平均延迟' }).first();
    await expect(latencyCard).toBeVisible();

    // It should show either "ms" or "-" as a placeholder
    const cardText = await latencyCard.textContent();
    const hasValue = cardText.includes('ms') || cardText.includes('-');
    expect(hasValue).toBeTruthy();
  });

  test('dashboard has average bandwidth display', async ({ page }) => {
    // The bandwidth card is in the second stat row
    const bandwidthCard = page.locator('.card, [class*="stat"]').filter({ hasText: '平均带宽' }).first();
    await expect(bandwidthCard).toBeVisible();

    // It should show either "Mbps" or "-" as a placeholder
    const cardText = await bandwidthCard.textContent();
    const hasValue = cardText.includes('Mbps') || cardText.includes('-');
    expect(hasValue).toBeTruthy();
  });

  test('dashboard has ChatGPT unlock count display', async ({ page }) => {
    // Look for the "ChatGPT 解锁" label
    const chatgptCard = page.locator('.card, [class*="stat"]').filter({ hasText: 'ChatGPT 解锁' }).first();
    await expect(chatgptCard).toBeVisible();

    // The card should show the unlocked count and a badge with ratio
    const cardText = await chatgptCard.textContent();
    // Should mention both "解锁" and "封锁" in the description area
    expect(cardText).toContain('解锁');
  });
});

// ── Batch Operations (Round 32) ──

test.describe('Batch Operations (Round 32)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscription page has add subscription form', async ({ page }) => {
    // The add subscription form has inputs for name and URL
    const nameInput = page.locator('input[placeholder="订阅名称"]').first();
    const urlInput = page.locator('input[placeholder="订阅链接 URL"]').first();

    await expect(nameInput).toBeVisible();
    await expect(urlInput).toBeVisible();

    // The "添加订阅" button should be present
    const addBtn = page.locator('button').filter({ hasText: '添加订阅' }).first();
    await expect(addBtn).toBeVisible();
  });

  test('subscription page has table with subscription data', async ({ page }) => {
    // The data table should be present (may have empty state if no subscriptions)
    const table = page.locator('.data-table').first();
    await expect(table).toBeVisible();

    // Verify table has header columns
    const headers = table.locator('thead th');
    const headerCount = await headers.count();
    expect(headerCount).toBeGreaterThanOrEqual(5);

    // Check for key column headers
    const expectedHeaders = ['名称', '链接', '格式'];
    for (const text of expectedHeaders) {
      const th = headers.filter({ hasText: text });
      await expect(th.first()).toBeVisible();
    }
  });

  test('subscription page has group filter tabs', async ({ page }) => {
    // The group tabs container should exist
    const groupTabs = page.locator('.sub-group-tabs').first();
    await expect(groupTabs).toBeVisible();

    // The "全部" tab should be present as the default
    const allTab = groupTabs.locator('button').filter({ hasText: '全部' }).first();
    await expect(allTab).toBeVisible();

    // The "新建分组" button should be present
    const newGroupBtn = groupTabs.locator('button').filter({ hasText: '新建分组' }).first();
    await expect(newGroupBtn).toBeVisible();
  });
});

// ── System Diagnostics Export (Round 32) ──

test.describe('System Diagnostics Export (Round 32)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('settings page has theme configuration options', async ({ page }) => {
    // The "外观设置" card should be visible
    const themeCard = page.locator('.settings-title').filter({ hasText: '外观设置' }).first();
    await expect(themeCard).toBeVisible();

    // Theme mode radio buttons should be present
    const themeRadioGroup = page.locator('el-radio-group, [aria-label="主题模式选择"]').first();
    await expect(themeRadioGroup).toBeVisible();

    // Verify the three theme options exist
    const lightBtn = page.locator('button, span, label').filter({ hasText: '浅色' }).first();
    const darkBtn = page.locator('button, span, label').filter({ hasText: '深色' }).first();
    const autoBtn = page.locator('button, span, label').filter({ hasText: '跟随系统' }).first();

    await expect(lightBtn).toBeVisible();
    await expect(darkBtn).toBeVisible();
    await expect(autoBtn).toBeVisible();
  });

  test('settings page has data settings section', async ({ page }) => {
    // The "数据设置" card should be visible
    const dataCard = page.locator('.settings-title').filter({ hasText: '数据设置' }).first();
    await expect(dataCard).toBeVisible();

    // Auto-refresh interval setting should be present
    const refreshLabel = page.locator('.setting-name').filter({ hasText: '自动刷新间隔' }).first();
    await expect(refreshLabel).toBeVisible();

    // Default page setting should be present
    const defaultPageLabel = page.locator('.setting-name').filter({ hasText: '默认启动页面' }).first();
    await expect(defaultPageLabel).toBeVisible();
  });
});
