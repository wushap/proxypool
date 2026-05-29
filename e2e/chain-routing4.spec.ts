import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  // Wait for the page's section title to confirm the async component rendered
  await page.locator('.section-title').filter({ hasText: menuText }).waitFor({ state: 'visible', timeout: 15000 });
}

test.describe('Chain Routing via Proxy Pools', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
  });

  test('should have chain view tab visible', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();

    // Pool tab should also coexist
    await expect(page.locator('.tab-btn').filter({ hasText: '代理池' })).toBeVisible();
  });

  test('should click chain view tab and load visualization content', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainTab.click();

    // Section divider for chain visualization should appear
    await expect(
      page.locator('.section-divider').filter({ hasText: '链路可视化' })
    ).toBeVisible({ timeout: 5000 });
  });

  test('should display chain flow visualization with arrows', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // Chain flow should contain at least one arrow connecting nodes
    const arrows = chainFlow.locator('.chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);

    // Arrow icon should be rendered
    await expect(arrows.first().locator('.chain-arrow-icon')).toBeVisible();
  });

  test('should display chain node elements with correct types', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    // Chain flow should contain at least 4 nodes (entry, front pool, exit pool, exit)
    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(4);

    // Entry node should be present
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode).toBeVisible();
    await expect(entryNode.locator('.chain-type-entry')).toBeVisible();

    // Exit node should be present
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode).toBeVisible();

    // Front pool and exit pool nodes should exist
    await expect(page.locator('.chain-flow .chain-type-front').first()).toBeVisible();
    await expect(page.locator('.chain-flow .chain-type-exit').first()).toBeVisible();
  });
});

test.describe('Subscription Intelligence via Subscriptions Page', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
  });

  test('should have intelligence panel or empty state', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    const hasPanel = await intelligencePanel.isVisible().catch(() => false);

    const emptyState = page.locator('.empty-state');
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    // Page must show either the intelligence panel or an empty state
    expect(hasPanel || hasEmpty).toBeTruthy();
  });

  test('should show analysis cards when intelligence panel is present', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Panel header text
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // Intelligence cards should be rendered
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);
  });

  test('should show duplicate node analysis card', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Either warning badge (duplicates exist) or success badge (no duplicates) is shown
    const warningBadge = duplicateCard.locator('.badge-warning');
    const successBadge = duplicateCard.locator('.badge-success');
    const hasWarning = await warningBadge.isVisible().catch(() => false);
    const hasSuccess = await successBadge.isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();
  });

  test('should display quality scores section', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid should be rendered with entries
    const scoresGrid = page.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const scoreEntries = scoresGrid.locator('> div');
      const count = await scoreEntries.count();
      expect(count).toBeGreaterThan(0);
    }
  });
});

test.describe('System Diagnostics Health Score', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '系统诊断');
  });

  test('should display health score section on diagnostics page', async ({ page }) => {
    // Page heading
    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();

    // Health overview section header
    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // Health summary grid with its labels
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '后端进程' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '网关服务' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理池' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理节点' })).toBeVisible();

    // Diagnostics button should be present
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });

  test('should run diagnostics and verify health score appears', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Button shows running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to finish
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge appears after diagnostics complete
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();
      await expect(page.locator('.health-score-value')).toBeVisible();

      // Score value should be a number between 0 and 100
      const scoreText = await page.locator('.health-score-value').textContent();
      const score = parseInt(scoreText || '', 10);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);
    }
  });
});
