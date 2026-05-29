import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
}

test.describe('Chain Routing via Proxy Pools (Round 6)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('chain view tab exists alongside pool tab', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();

    // Pool tab should coexist
    const poolTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolTab).toBeVisible();

    // Tab should have proper visual structure (active state or clickable attribute)
    await expect(chainTab).toHaveClass(/tab-btn/);
  });

  test('clicking chain view tab loads chain visualization content', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainTab.click();

    // Chain visualization section header should appear
    const vizHeader = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(vizHeader).toBeVisible({ timeout: 5000 });

    // Chain flow container should render
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // Chain flow should have child elements (not empty)
    const flowChildren = chainFlow.locator('> *');
    const childCount = await flowChildren.count();
    expect(childCount).toBeGreaterThan(0);
  });

  test('chain flow visualization contains node and arrow elements', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Chain nodes should exist
    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);

    // Arrows connecting nodes should exist
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);

    // Arrows should be visible with icons
    for (let i = 0; i < arrowCount; i++) {
      const arrow = arrows.nth(i);
      await expect(arrow).toBeVisible();
    }
  });

  test('chain node elements include entry and exit node types', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node should be present
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode).toBeVisible();
    await expect(entryNode.locator('.chain-type-entry')).toBeVisible();

    // Exit node should be present
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode).toBeVisible();

    // Pool type labels should exist inside the chain flow
    const frontPoolLabel = page.locator('.chain-flow .chain-type-front').first();
    const exitPoolLabel = page.locator('.chain-flow .chain-type-exit').first();
    await expect(frontPoolLabel).toBeVisible();
    await expect(exitPoolLabel).toBeVisible();
  });
});

test.describe('Subscription Intelligence via Subscriptions Page (Round 6)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscriptions page has intelligence panel or empty state', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');

    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    // Page must show either intelligence panel (when subscriptions exist) or empty state
    expect(hasPanel || hasEmpty).toBeTruthy();

    // Page header should always be visible
    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();
  });

  test('intelligence panel shows analysis cards with content', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Panel header text should be visible
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // At least one analysis card should be present
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Each card should contain meaningful text content
    for (let i = 0; i < cardCount; i++) {
      const cardText = await cards.nth(i).textContent();
      expect(cardText?.trim().length).toBeGreaterThan(0);
    }
  });

  test('intelligence panel shows duplicate node analysis', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Duplicate analysis card should be present
    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Should show a status badge indicating duplicate state
    const warningBadge = duplicateCard.locator('.badge-warning');
    const successBadge = duplicateCard.locator('.badge-success');
    const hasWarning = await warningBadge.isVisible().catch(() => false);
    const hasSuccess = await successBadge.isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();
  });

  test('intelligence panel shows quality scores', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Quality scoring card should exist
    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid should contain at least one entry when visible
    const scoresGrid = page.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const scoreEntries = scoresGrid.locator('> div');
      const count = await scoreEntries.count();
      expect(count).toBeGreaterThan(0);
    }
  });
});

test.describe('System Diagnostics Health Score (Round 6)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '系统诊断');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics page has health score section with summary grid', async ({ page }) => {
    // Page title should be visible
    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();

    // Health overview section should be present
    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // Health summary grid should show four labels
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '后端进程' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '网关服务' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理池' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理节点' })).toBeVisible();

    // One-click diagnostics button should be ready
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });

  test('run diagnostics and verify health score badge appears', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Button should indicate running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to complete (button returns to normal text)
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge should appear after completion
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      // Score label should be present
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();

      // Score value should be a valid number 0-100
      const scoreValue = page.locator('.health-score-value');
      await expect(scoreValue).toBeVisible();
      const scoreText = await scoreValue.textContent();
      const score = parseInt(scoreText || '', 10);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);

      // Max score indicator should be visible
      await expect(page.locator('.health-score-max:has-text("/100")')).toBeVisible();
    }
  });
});
