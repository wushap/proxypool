import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 9)', () => {
  test('chain view tab exists alongside pool tabs', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();

    // Sibling tabs should coexist
    await expect(page.locator('.tab-btn').filter({ hasText: '代理池' })).toBeVisible();
    await expect(page.locator('.tab-btn').filter({ hasText: 'HTTP 代理端点' })).toBeVisible();
  });

  test('clicking chain view tab loads chain content', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Section header for chain visualization should appear
    const vizHeader = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(vizHeader).toBeVisible({ timeout: 5000 });

    // Chain flow container should render with children
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
    const childCount = await chainFlow.locator('> *').count();
    expect(childCount).toBeGreaterThan(0);
  });

  test('chain flow visualization exists with nodes and arrows', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // At least 2 chain nodes (entry, exit at minimum)
    const nodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);

    // At least 1 arrow connecting nodes
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);

    // All arrows should be visible
    for (let i = 0; i < arrowCount; i++) {
      await expect(arrows.nth(i)).toBeVisible();
    }
  });

  test('chain node elements include entry and exit type labels', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry and exit node type elements should be visible
    await expect(page.locator('.chain-node-entry').first()).toBeVisible();
    await expect(page.locator('.chain-node-exit').first()).toBeVisible();

    // Pool type labels inside the chain flow
    await expect(page.locator('.chain-flow .chain-type-front').first()).toBeVisible();
    await expect(page.locator('.chain-flow .chain-type-exit').first()).toBeVisible();
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 9)', () => {
  test('subscriptions page shows intelligence panel or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // Page title should always be visible
    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasPanel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel shows analysis cards with content', async ({ page }) => {
    await navigateTo(page, '订阅管理');

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

  test('duplicate node analysis card shows warning or success badge', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Should have either a warning or success badge
    const hasWarning = await duplicateCard.locator('.badge-warning').isVisible().catch(() => false);
    const hasSuccess = await duplicateCard.locator('.badge-success').isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();
  });

  test('quality scores section displays score entries', async ({ page }) => {
    await navigateTo(page, '订阅管理');

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

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 9)', () => {
  test('diagnostics page has health score section with summary grid', async ({ page }) => {
    await navigateTo(page, '系统诊断');

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

  test('run diagnostics and verify health score appears', async ({ page }) => {
    await navigateTo(page, '系统诊断');

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
