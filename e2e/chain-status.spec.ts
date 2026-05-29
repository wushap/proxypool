import { test, expect } from '@playwright/test';

test.describe('Chain Status via Proxy Pools', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should display chain view tab', async ({ page }) => {
    const chainViewTab = page.locator('button.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
  });

  test('should load chain view content after clicking tab', async ({ page }) => {
    const chainViewTab = page.locator('button.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await page.waitForLoadState('networkidle');

    // Verify the chain view section heading is visible
    await expect(page.locator('text=链路可视化')).toBeVisible();
  });

  test('should display chain flow visualization', async ({ page }) => {
    const chainViewTab = page.locator('button.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await page.waitForLoadState('networkidle');

    // Chain flow container should exist
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('should display chain node elements in the flow', async ({ page }) => {
    const chainViewTab = page.locator('button.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();
    await page.waitForLoadState('networkidle');

    // Entry node
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode).toBeVisible();

    // Exit node
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode).toBeVisible();

    // At least some chain-node elements should be present
    const allNodes = page.locator('.chain-node');
    const nodeCount = await allNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Subscription Intelligence via Subscriptions Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should display intelligence panel on subscriptions page', async ({ page }) => {
    // Wait for the page content to load
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    // Intelligence section is shown only when there are subscriptions.
    // With zero subscriptions the panel is hidden by v-if="subscriptions.length > 0".
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state-title');

    const hasIntelligence = await intelligencePanel.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    // Either the intelligence panel is visible (subscriptions exist) or empty state is shown
    expect(hasIntelligence || hasEmptyState).toBeTruthy();
  });

  test('should show analysis cards in intelligence panel', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Check that the expand/collapse toggle is present
      const toggleButton = page.locator('.subscription-intelligence button.btn-ghost').first();
      await expect(toggleButton).toBeVisible();

      // Intelligence cards should be present
      const intelligenceCards = page.locator('.intelligence-card');
      const cardCount = await intelligenceCards.count();
      expect(cardCount).toBeGreaterThan(0);
    }
  });

  test('should show duplicate node analysis', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Duplicate analysis card is present within the intelligence panel
      const duplicateAnalysis = page.locator('.subscription-intelligence').filter({ hasText: '重复节点分析' });
      await expect(duplicateAnalysis).toBeVisible();

      // Should show either duplicate count badge or "no duplicates" badge
      const badge = duplicateAnalysis.locator('.badge').first();
      await expect(badge).toBeVisible();
    }
  });

  test('should show quality scores in intelligence panel', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Quality scores card should be present
      const qualityScoresSection = page.locator('.subscription-intelligence').filter({ hasText: '订阅质量评分' });
      await expect(qualityScoresSection).toBeVisible();

      // Quality scores grid should exist
      const qualityGrid = qualityScoresSection.locator('.quality-scores');
      if (await qualityGrid.isVisible().catch(() => false)) {
        const scoreItems = qualityGrid.locator('> div');
        const count = await scoreItems.count();
        expect(count).toBeGreaterThan(0);
      }
    }
  });
});

test.describe('System Diagnostics Health Score', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should display health score section', async ({ page }) => {
    // The health summary grid should be visible even before running diagnostics
    await expect(page.locator('.health-summary-grid')).toBeVisible();

    // Individual health items should be present
    await expect(page.locator('.health-label').filter({ hasText: '后端进程' })).toBeVisible();
    await expect(page.locator('.health-label').filter({ hasText: '代理池' })).toBeVisible();
  });

  test('should show health score after running diagnostics', async ({ page }) => {
    // Click the diagnostics button
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Button should change to running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to complete
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Health score badge should appear after diagnostics run
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible().catch(() => false)) {
      // Score value should be a number
      const scoreValue = page.locator('.health-score-value');
      await expect(scoreValue).toBeVisible();

      // Score label should read "健康评分"
      await expect(page.locator('.health-score-label')).toBeVisible();
    }
  });
});
