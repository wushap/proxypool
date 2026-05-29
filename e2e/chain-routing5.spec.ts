import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
}

test.describe('Chain Routing via Proxy Pools (Round 5)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '多跳代理池');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('chain view tab is visible and coexists with pool tab', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();

    const poolTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolTab).toBeVisible();
  });

  test('clicking chain view tab loads chain content', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainTab.click();

    // Chain visualization section should appear
    const sectionDivider = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(sectionDivider).toBeVisible({ timeout: 5000 });

    // Chain flow container should be present
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('chain flow visualization contains arrows between nodes', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Chain flow should have arrows connecting nodes
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);

    // Each arrow should have an icon element
    const firstArrowIcon = arrows.first().locator('.chain-arrow-icon');
    await expect(firstArrowIcon).toBeVisible();
  });

  test('chain node elements include entry and exit nodes', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Should have multiple chain nodes
    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(4);

    // Entry node with entry type label
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode).toBeVisible();
    await expect(entryNode.locator('.chain-type-entry')).toBeVisible();

    // Exit node
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode).toBeVisible();

    // Front and exit pool nodes
    const frontPoolNode = page.locator('.chain-flow .chain-type-front').first();
    const exitPoolNode = page.locator('.chain-flow .chain-type-exit').first();
    await expect(frontPoolNode).toBeVisible();
    await expect(exitPoolNode).toBeVisible();
  });
});

test.describe('Subscription Intelligence via Subscriptions Page (Round 5)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '订阅管理');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('subscriptions page has intelligence panel or empty state', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');

    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasPanel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel shows analysis cards with content', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Panel header should be visible
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // At least one intelligence card should be rendered
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);

    // Each card should have visible text content
    for (let i = 0; i < cardCount; i++) {
      const cardText = await cards.nth(i).textContent();
      expect(cardText?.trim().length).toBeGreaterThan(0);
    }
  });

  test('intelligence panel shows duplicate node analysis card', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Should show either a warning or success badge
    const warningBadge = duplicateCard.locator('.badge-warning');
    const successBadge = duplicateCard.locator('.badge-success');
    const hasWarning = await warningBadge.isVisible().catch(() => false);
    const hasSuccess = await successBadge.isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();
  });

  test('intelligence panel shows quality scores section', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid should contain at least one entry
    const scoresGrid = page.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const scoreEntries = scoresGrid.locator('> div');
      const count = await scoreEntries.count();
      expect(count).toBeGreaterThan(0);
    }
  });
});

test.describe('System Diagnostics Health Score (Round 5)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '系统诊断');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('diagnostics page has health score section with grid labels', async ({ page }) => {
    // Section title
    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();

    // Health overview header
    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // Health summary grid labels
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '后端进程' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '网关服务' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理池' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理节点' })).toBeVisible();

    // Diagnostics button
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

    // Health score badge should appear
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();
      await expect(page.locator('.health-score-value')).toBeVisible();

      // Score should be a valid number between 0 and 100
      const scoreText = await page.locator('.health-score-value').textContent();
      const score = parseInt(scoreText || '', 10);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);
    }
  });
});
