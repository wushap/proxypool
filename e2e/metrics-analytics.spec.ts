import { test, expect } from '@playwright/test';

test.describe('Metrics and Analytics', () => {
  // ============================================================
  // Dashboard Charts
  // ============================================================
  test.describe('Dashboard Charts', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      // Wait for the dashboard to finish loading
      await page.locator('.dashboard-page').waitFor();
    });

    test('should display protocol distribution section', async ({ page }) => {
      // The protocol distribution card should be present
      const protocolCard = page.locator('.card').filter({ hasText: '协议分布' }).first();
      await expect(protocolCard).toBeVisible();

      // It should contain either a donut chart or an empty state
      const hasDonut = await protocolCard.locator('.dashboard-donut-chart').isVisible().catch(() => false);
      const hasEmpty = await protocolCard.locator('.empty-state').isVisible().catch(() => false);
      const hasLegend = await protocolCard.locator('.dashboard-donut-legend').isVisible().catch(() => false);

      expect(hasDonut || hasLegend || hasEmpty).toBeTruthy();
    });

    test('should display latency distribution section', async ({ page }) => {
      // The latency distribution card should be present
      const latencyCard = page.locator('.card').filter({ hasText: '延迟分布' }).first();
      await expect(latencyCard).toBeVisible();

      // It should contain a histogram or an empty state
      const hasHistogram = await latencyCard.locator('.dashboard-histogram').isVisible().catch(() => false);
      const hasEmpty = await latencyCard.locator('.empty-state').isVisible().catch(() => false);

      expect(hasHistogram || hasEmpty).toBeTruthy();
    });

    test('should display proxy pool health overview section', async ({ page }) => {
      // The pool health overview card should be present
      const poolHealthCard = page.locator('.card').filter({ hasText: '代理池健康概览' }).first();
      await expect(poolHealthCard).toBeVisible();

      // It should contain pool health entries or an empty state
      const hasPoolEntries = await poolHealthCard.locator('.dashboard-pool-health').isVisible().catch(() => false);
      const hasEmpty = await poolHealthCard.locator('.empty-state').isVisible().catch(() => false);

      expect(hasPoolEntries || hasEmpty).toBeTruthy();
    });
  });

  // ============================================================
  // Subscription Analytics (via Subscriptions page)
  // ============================================================
  test.describe('Subscription Analytics', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      // Navigate to subscriptions page
      await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
      await page.waitForLoadState('networkidle');
      await page.locator('.page-container, .card').first().waitFor();
    });

    test('should display intelligence panel on subscriptions page', async ({ page }) => {
      // The intelligence panel should be visible when there are subscriptions
      const intelligencePanel = page.locator('.subscription-intelligence');
      const emptyState = page.locator('.empty-state-title', { hasText: '暂无订阅' });

      const hasIntelligence = await intelligencePanel.isVisible().catch(() => false);
      const hasEmpty = await emptyState.isVisible().catch(() => false);

      // Either the intelligence panel or the empty state should be visible
      expect(hasIntelligence || hasEmpty).toBeTruthy();

      // If the panel is present, verify the section header
      if (hasIntelligence) {
        await expect(intelligencePanel.locator('text=订阅智能分析')).toBeVisible();
      }
    });

    test('should show duplicate node analysis in intelligence panel', async ({ page }) => {
      const intelligencePanel = page.locator('.subscription-intelligence');

      if (await intelligencePanel.isVisible().catch(() => false)) {
        // Check for the duplicate analysis card
        const duplicateCard = intelligencePanel.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
        await expect(duplicateCard).toBeVisible();

        // Should show either duplicate count or "no duplicates" badge
        const hasDupBadge = await duplicateCard.locator('.badge-warning, .badge-success').first().isVisible().catch(() => false);
        expect(hasDupBadge).toBeTruthy();
      }
    });

    test('should show subscription quality scores in intelligence panel', async ({ page }) => {
      const intelligencePanel = page.locator('.subscription-intelligence');

      if (await intelligencePanel.isVisible().catch(() => false)) {
        // Check for the quality scores card
        const qualityCard = intelligencePanel.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
        await expect(qualityCard).toBeVisible();

        // Should have a quality-scores grid
        const qualityScoresGrid = qualityCard.locator('.quality-scores');
        await expect(qualityScoresGrid).toBeVisible();
      }
    });

    test('should show health monitoring section in intelligence panel', async ({ page }) => {
      const intelligencePanel = page.locator('.subscription-intelligence');

      if (await intelligencePanel.isVisible().catch(() => false)) {
        // Check for the health monitoring card
        const healthCard = intelligencePanel.locator('.intelligence-card').filter({ hasText: '健康监控' });
        await expect(healthCard).toBeVisible();

        // Should show healthy/warning/critical counts
        const healthMetrics = healthCard.locator('.health-metrics');
        await expect(healthMetrics).toBeVisible();
      }
    });
  });

  // ============================================================
  // System Resources (via Diagnostics page)
  // ============================================================
  test.describe('System Resources', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      // Navigate to diagnostics page
      await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
      await page.waitForLoadState('networkidle');
      await page.locator('.page-container, .card').first().waitFor();
    });

    test('should display health history section', async ({ page }) => {
      // Health history section should be visible (scroll down to reach it)
      const historyTitle = page.locator('.settings-title').filter({ hasText: '健康历史' });
      await historyTitle.scrollIntoViewIfNeeded();
      await expect(historyTitle).toBeVisible();

      // Either health history entries or an empty state message should be present
      const historyCard = historyTitle.locator('..').locator('..');
      const hasHistory = await historyCard.locator('.health-history .history-item').first().isVisible().catch(() => false);
      const hasEmpty = await page.getByText('暂无历史记录').isVisible().catch(() => false);

      expect(hasHistory || hasEmpty).toBeTruthy();
    });

    test('should display export button', async ({ page }) => {
      const exportButton = page.locator('button:has-text("导出报告")');
      await expect(exportButton).toBeVisible();

      // Button should initially be disabled (no report generated yet)
      await expect(exportButton).toBeDisabled();
    });
  });
});
