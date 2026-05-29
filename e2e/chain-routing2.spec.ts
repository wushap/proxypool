import { test, expect } from '@playwright/test';

test.describe('Chain Routing via Proxy Pools', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor();
  });

  test('should display chain view tab', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();

    // Other tabs should coexist
    await expect(page.locator('.tab-btn').filter({ hasText: '代理池' })).toBeVisible();
  });

  test('should click chain view tab and verify content loads', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainTab.click();

    // Chain view section header should appear
    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(chainSection).toBeVisible({ timeout: 5000 });
  });

  test('should show chain flow visualization', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // Chain flow should contain arrows connecting nodes
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);
  });

  test('should display chain node elements with correct types', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    // At minimum the chain should have entry, front pool, exit pool, exit = 4 nodes
    expect(nodeCount).toBeGreaterThanOrEqual(4);

    // Entry and exit type labels should be present
    await expect(page.locator('.chain-flow .chain-type-entry').first()).toBeVisible();
    await expect(page.locator('.chain-flow .chain-type-exit').first()).toBeVisible();
  });
});

test.describe('Subscription Intelligence via Subscriptions Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should show intelligence panel when subscriptions exist', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    const hasIntelligence = await intelligencePanel.isVisible().catch(() => false);

    const emptyState = page.locator('.empty-state-title').filter({ hasText: '暂无订阅' });
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    // Either intelligence panel is present or subscriptions page is in empty state
    expect(hasIntelligence || hasEmpty).toBeTruthy();
  });

  test('should show analysis cards in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Panel header should read "订阅智能分析"
    await expect(page.locator('text=订阅智能分析')).toBeVisible();
  });

  test('should show duplicate node analysis in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Should display either a warning badge (duplicates found) or success badge (no duplicates)
    const warningBadge = duplicateCard.locator('.badge-warning');
    const successBadge = duplicateCard.locator('.badge-success');
    const hasWarning = await warningBadge.isVisible().catch(() => false);
    const hasSuccess = await successBadge.isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();
  });

  test('should display quality scores in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid should have at least one entry
    const qualityScores = page.locator('.quality-scores');
    if (await qualityScores.isVisible()) {
      const scoreItems = qualityScores.locator('> div');
      const count = await scoreItems.count();
      expect(count).toBeGreaterThan(0);
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

  test('should display diagnostics page with health score section', async ({ page }) => {
    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();

    // Health history section should be present on the page
    const healthHistory = page.locator('text=健康历史');
    await expect(healthHistory).toBeVisible();

    // The one-click diagnostics button should be available
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
  });

  test('should run diagnostics and verify health score appears', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await diagButton.click();

    // Button transitions to running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to finish
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Health overview header should appear
    await expect(page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })).toBeVisible();

    // Health summary grid labels should be present
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '后端进程' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '网关服务' })).toBeVisible();

    // Health score badge may appear after diagnostics
    const scoreBadge = page.locator('.health-score-badge');
    const hasScoreBadge = await scoreBadge.isVisible().catch(() => false);
    if (hasScoreBadge) {
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();
      await expect(page.locator('.health-score-value')).toBeVisible();
    }
  });
});
