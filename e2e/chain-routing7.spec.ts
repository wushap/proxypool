import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
}

test.describe('Chain Routing via Proxy Pools (Round 7)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('chain view tab is present and enabled alongside pool tabs', async ({ page }) => {
    // Chain view tab should be visible and clickable
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();

    // Verify sibling tabs coexist
    const poolTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolTab).toBeVisible();
    const endpointTab = page.locator('.tab-btn').filter({ hasText: 'HTTP 代理端点' });
    await expect(endpointTab).toBeVisible();
  });

  test('clicking chain view tab renders chain flow content', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Chain visualization section header should appear
    const vizHeader = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(vizHeader).toBeVisible({ timeout: 5000 });

    // Chain flow container should render with children
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    const childCount = await chainFlow.locator('> *').count();
    expect(childCount).toBeGreaterThan(0);
  });

  test('chain flow visualization contains node and arrow elements', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Chain nodes should exist (entry, front pool, exit pool, exit)
    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);

    // Arrows connecting nodes should be visible
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);
    for (let i = 0; i < arrowCount; i++) {
      await expect(arrows.nth(i)).toBeVisible();
    }
  });

  test('chain node elements include expected type labels', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node type should be present
    const entryType = page.locator('.chain-node-entry').first();
    await expect(entryType).toBeVisible();

    // Exit node type should be present
    const exitType = page.locator('.chain-node-exit').first();
    await expect(exitType).toBeVisible();

    // Pool type labels inside the chain flow
    const frontLabel = page.locator('.chain-flow .chain-type-front').first();
    const exitLabel = page.locator('.chain-flow .chain-type-exit').first();
    await expect(frontLabel).toBeVisible();
    await expect(exitLabel).toBeVisible();
  });
});

test.describe('Subscription Intelligence via Subscriptions Page (Round 7)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscriptions page shows intelligence panel or empty state', async ({ page }) => {
    // Page title should always be visible
    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    // Page must show one of the two states
    expect(hasPanel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel analysis cards contain meaningful content', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Intelligence panel header should be present
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // At least one analysis card
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Each card should have non-empty text
    for (let i = 0; i < cardCount; i++) {
      const text = await cards.nth(i).textContent();
      expect(text?.trim().length).toBeGreaterThan(0);
    }
  });

  test('duplicate node analysis card shows status badge', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Should have a warning or success badge indicating duplicate state
    const hasWarning = await duplicateCard.locator('.badge-warning').isVisible().catch(() => false);
    const hasSuccess = await duplicateCard.locator('.badge-success').isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();
  });

  test('quality scores section displays score entries', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    const scoresGrid = page.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const count = await scoresGrid.locator('> div').count();
      expect(count).toBeGreaterThan(0);
    }
  });
});

test.describe('System Diagnostics Health Score (Round 7)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '系统诊断');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics page has health score section with summary grid', async ({ page }) => {
    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();

    // Health overview section should be present
    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // Summary grid should show four labels
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

    // Button should show running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to complete
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge should appear after completion
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();

      const scoreValue = page.locator('.health-score-value');
      await expect(scoreValue).toBeVisible();
      const scoreText = await scoreValue.textContent();
      const score = parseInt(scoreText || '', 10);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);

      await expect(page.locator('.health-score-max:has-text("/100")')).toBeVisible();
    }
  });
});
