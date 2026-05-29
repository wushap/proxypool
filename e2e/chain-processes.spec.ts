import { test, expect } from '@playwright/test';

test.describe('Chain Configuration via Proxy Pools', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should verify chain view tab exists', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
  });

  test('should click chain view tab and verify content loads', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    await chainViewTab.click();

    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(chainSection).toBeVisible({ timeout: 5000 });
  });

  test('should verify chain flow visualization exists', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('should verify chain node elements exist', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainNodes = page.locator('.chain-flow .chain-node');
    const count = await chainNodes.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe('System Processes via Diagnostics', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should verify diagnostics page has health history section', async ({ page }) => {
    const healthHistory = page.locator('text=健康历史');
    await expect(healthHistory).toBeVisible();

    const hasHistory = await page.locator('.health-history').isVisible().catch(() => false);
    const hasEmptyState = await page.locator('text=暂无历史记录').isVisible().catch(() => false);
    expect(hasHistory || hasEmptyState).toBeTruthy();
  });

  test('should verify diagnostics page has health alerting rules section', async ({ page }) => {
    await expect(page.locator('.settings-title').filter({ hasText: '健康告警规则' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '后端进程停止' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '网关服务停止' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '健康评分过低' })).toBeVisible();
  });

  test('should verify diagnostics page has export button', async ({ page }) => {
    await page.locator('button:has-text("一键诊断")').click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();
  });
});

test.describe('Subscription Refresh Operations', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should verify subscription page has refresh all button', async ({ page }) => {
    const refreshAllButton = page.locator('button:has-text("刷新全部")');
    const hasButton = await refreshAllButton.isVisible().catch(() => false);
    expect(hasButton).toBeTruthy();
  });

  test('should verify subscription page has delete unavailable button', async ({ page }) => {
    const deleteUnavailableButton = page.locator('button:has-text("删除不可用")');
    const hasButton = await deleteUnavailableButton.isVisible().catch(() => false);
    expect(hasButton).toBeTruthy();
  });

  test('should verify subscription page has refresh list button', async ({ page }) => {
    const refreshListButton = page.locator('button:has-text("刷新列表")');
    const hasButton = await refreshListButton.isVisible().catch(() => false);
    expect(hasButton).toBeTruthy();
  });
});
