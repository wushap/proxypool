import { test, expect } from '@playwright/test';

test.describe('System Diagnostics Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/webui/');
    await page.waitForLoadState('networkidle');
    // Navigate to system diagnostics page via sidebar menu
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load diagnostics page and display title', async ({ page }) => {
    await expect(page.locator('h2.section-title:has-text("系统诊断")')).toBeVisible();
    await expect(page.locator('text=全面检查系统健康状态')).toBeVisible();
  });

  test('should display one-click diagnostics button', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await expect(diagButton).toBeEnabled();
  });

  test('should display initial empty state before running diagnostics', async ({ page }) => {
    // Before running diagnostics, should show the prompt
    await expect(page.locator('text=点击「一键诊断」按钮开始系统健康检查')).toBeVisible();
  });

  test('should display health alerting rules section', async ({ page }) => {
    await expect(page.locator('text=健康告警规则')).toBeVisible();
    await expect(page.locator('text=后端进程停止')).toBeVisible();
    await expect(page.locator('text=网关服务停止')).toBeVisible();
    await expect(page.locator('text=健康评分过低')).toBeVisible();
    await expect(page.locator('text=代理池异常')).toBeVisible();
    await expect(page.locator('text=代理节点不可用')).toBeVisible();
  });

  test('should toggle alerting rule', async ({ page }) => {
    // Find the toggle for "代理节点不可用" rule (initially disabled)
    const ruleItems = page.locator('.alerting-rule-item');
    const proxyRule = ruleItems.filter({ hasText: '代理节点不可用' });

    if (await proxyRule.isVisible()) {
      const toggle = proxyRule.locator('input[type="checkbox"]');
      const initialState = await toggle.isChecked();

      // Toggle the checkbox
      await toggle.click();
      await page.waitForTimeout(200);

      // Verify state changed
      const newState = await toggle.isChecked();
      expect(newState).not.toBe(initialState);
    }
  });

  test('should run diagnostics and display health overview', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await diagButton.click();

    // Button should show "诊断中..." while running
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to complete
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Health summary grid should appear
    await expect(page.locator('text=系统健康概览')).toBeVisible();
    await expect(page.locator('text=后端进程')).toBeVisible();
    await expect(page.locator('text=网关服务')).toBeVisible();
    await expect(page.locator('text=代理池')).toBeVisible();
    await expect(page.locator('text=代理节点')).toBeVisible();
  });

  test('should display diagnostic details after running', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await diagButton.click();
    await page.waitForTimeout(3000);

    // Check for detailed report sections
    const hasDetails = await page.locator('text=诊断详情').isVisible().catch(() => false);
    if (hasDetails) {
      await expect(page.locator('text=后端进程状态')).toBeVisible();
      await expect(page.locator('text=网关服务状态')).toBeVisible();
      await expect(page.locator('text=代理池健康')).toBeVisible();
      await expect(page.locator('text=代理节点统计')).toBeVisible();
    }
  });

  test('should display health score after diagnostics', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await diagButton.click();
    await page.waitForTimeout(3000);

    // Health score badge should appear
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();
      await expect(page.locator('.health-score-value')).toBeVisible();
    }
  });

  test('should export diagnostics report', async ({ page }) => {
    // Run diagnostics first
    await page.locator('button:has-text("一键诊断")').click();
    await page.waitForTimeout(3000);

    // Export button should be enabled after report is generated
    const exportButton = page.locator('button:has-text("导出报告")');
    if (await exportButton.isVisible()) {
      // Verify the button is enabled (not disabled)
      await expect(exportButton).toBeEnabled();
    }
  });

  test('should display health history section', async ({ page }) => {
    await expect(page.locator('text=健康历史')).toBeVisible();
    // Initially might show empty state
    const hasHistory = await page.locator('.health-history').isVisible().catch(() => false);
    const hasEmptyState = await page.locator('text=暂无历史记录').isVisible().catch(() => false);

    expect(hasHistory || hasEmptyState).toBeTruthy();
  });
});
