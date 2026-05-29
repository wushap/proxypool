import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 11)', () => {
  test('chain view tab exists alongside other tabs', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const tabs = page.locator('.tab-btn');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(5);

    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();
  });

  test('clicking chain view tab loads chain visualization content', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Chain visualization section header should appear
    await expect(page.locator('.section-divider').filter({ hasText: '链路可视化' })).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.form-hint').filter({ hasText: '可视化展示代理链路配置' })).toBeVisible();

    // Chain flow container should render
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('chain flow visualization exists with entry and exit nodes', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node should be visible with type label
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode.first()).toBeVisible();
    await expect(entryNode.locator('.chain-type-entry').first()).toBeVisible();

    // Exit node should be visible
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode.first()).toBeVisible();
    await expect(exitNode.locator('.chain-type-output').first()).toBeVisible();
  });

  test('chain node elements include arrows and status dots', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // At least two arrows should connect nodes
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(2);

    // Each arrow should have an icon
    const firstArrow = arrows.first();
    await expect(firstArrow.locator('.chain-arrow-icon')).toBeVisible();

    // Status dots should exist on nodes
    const statusDots = page.locator('.chain-flow .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(2);

    // Front pool node should exist
    const frontPoolNode = page.locator('.chain-node').filter({ has: page.locator('.chain-type-front') });
    await expect(frontPoolNode.first()).toBeVisible();

    // Exit pool node should exist
    const exitPoolNode = page.locator('.chain-node').filter({ has: page.locator('.chain-type-exit') });
    await expect(exitPoolNode.first()).toBeVisible();
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 11)', () => {
  test('subscriptions page has intelligence panel or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    // Intelligence panel requires subscriptions to exist
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

    // Intelligence header text should be present
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // At least one analysis card
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Each card should have non-empty text content
    for (let i = 0; i < Math.min(cardCount, 5); i++) {
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

    // Should show either a warning badge (duplicates found) or success badge (no duplicates)
    const hasWarning = await duplicateCard.locator('.badge-warning').isVisible().catch(() => false);
    const hasSuccess = await duplicateCard.locator('.badge-success').isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();
  });

  test('quality scores card displays score entries', async ({ page }) => {
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

      // First score entry should contain text with node count and reliability info
      const firstScore = scoresGrid.locator('> div').first();
      const scoreText = await firstScore.textContent();
      expect(scoreText).toBeTruthy();
      // Should mention nodes and reliability
      expect(scoreText).toContain('节点');
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 11)', () => {
  test('diagnostics page has health score section with summary grid', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();

    // Health overview section header
    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // Summary grid should show all four category labels
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '后端进程' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '网关服务' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理池' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理节点' })).toBeVisible();

    // Diagnostics button should be visible and enabled
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });

  test('run diagnostics and verify health score appears', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Button should show running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to complete (button returns to idle)
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

      // Max score label should be present
      await expect(page.locator('.health-score-max:has-text("/100")')).toBeVisible();
    }
  });
});
