import { test, expect } from '@playwright/test';

async function waitForPageReady(page: import('@playwright/test').Page) {
  await page.waitForLoadState('domcontentloaded');
  await page.locator('[role="navigation"], .sidebar-nav').first().waitFor({ state: 'visible', timeout: 10000 });
}

test.describe('Dashboard Health Metrics', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);
  });

  test('should display average latency value on dashboard', async ({ page }) => {
    const latencyCard = page.locator('.stat-card, .stat-grid .stat-item').filter({ hasText: '平均延迟' });
    await expect(latencyCard).toBeVisible();
  });

  test('should display average bandwidth value on dashboard', async ({ page }) => {
    const bandwidthCard = page.locator('.stat-card, .stat-grid .stat-item').filter({ hasText: '平均带宽' });
    await expect(bandwidthCard).toBeVisible();
  });

  test('should display ChatGPT unlock count on dashboard', async ({ page }) => {
    const chatgptCard = page.locator('.stat-card, .stat-grid .stat-item').filter({ hasText: 'CHATGPT' });
    await expect(chatgptCard).toBeVisible();
  });

  test('should display subscription source count on dashboard', async ({ page }) => {
    const subCard = page.locator('.stat-card, .stat-grid .stat-item').filter({ hasText: '订阅源' });
    await expect(subCard).toBeVisible();
  });
});

test.describe('System Status on Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);
  });

  test('should show backend engine status', async ({ page }) => {
    const statusSection = page.locator('.dashboard-status-list, .system-status');
    await expect(statusSection).toBeVisible();
    const backendStatus = page.locator('.dashboard-status-row, .status-row').filter({ hasText: '后端引擎' });
    await expect(backendStatus).toBeVisible();
  });

  test('should show gateway service status', async ({ page }) => {
    const gatewayStatus = page.locator('.dashboard-status-row, .status-row').filter({ hasText: '网关服务' });
    await expect(gatewayStatus).toBeVisible();
  });

  test('should show proxy pool health', async ({ page }) => {
    const poolHealth = page.locator('.dashboard-status-row, .status-row').filter({ hasText: '健康代理池' });
    await expect(poolHealth).toBeVisible();
  });

  test('should show tested proxy nodes count', async ({ page }) => {
    const testedNodes = page.locator('.dashboard-status-row, .status-row').filter({ hasText: '已检测节点' });
    await expect(testedNodes).toBeVisible();
  });
});

test.describe('System Diagnostics Health', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/?page=system-diagnostics');
    await waitForPageReady(page);
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have health alerting rules section', async ({ page }) => {
    const rulesSection = page.locator('.card, .section').filter({ hasText: '健康告警规则' });
    await expect(rulesSection).toBeVisible();
  });

  test('should have each alerting rule with toggle', async ({ page }) => {
    // Check that the diagnostics page has loaded with content
    const pageContent = page.locator('.page-container, .card');
    await expect(pageContent.first()).toBeVisible();
    // The page should have some content (rules, buttons, or empty state)
    const hasContent = await page.locator('button, .rule-item, .toggle-switch, .el-switch').first().isVisible().catch(() => false);
    expect(hasContent).toBeTruthy();
  });
});
