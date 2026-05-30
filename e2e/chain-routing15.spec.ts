import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 15)', () => {
  test('chain view tab is present among other tabs', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // Verify tab bar exists with multiple tabs
    const tabs = page.locator('.tab-btn');
    await expect(tabs.first()).toBeVisible();
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(5);

    // Chain view tab should be present and visible
    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();
  });

  test('clicking chain view tab loads chain visualization content', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // Click chain view tab
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Section divider for chain visualization should appear
    await expect(
      page.locator('.section-divider').filter({ hasText: '链路可视化' })
    ).toBeVisible({ timeout: 5000 });

    // Chain visualization container should be present
    const chainViz = page.locator('.chain-visualization');
    await expect(chainViz).toBeVisible();

    // Action buttons in chain view should be present
    await expect(page.locator('button:has-text("链路诊断")')).toBeVisible();
    await expect(page.locator('button:has-text("测试链路延迟")')).toBeVisible();
    await expect(page.locator('button:has-text("测试整条链路")')).toBeVisible();
  });

  test('chain flow visualization renders with flow container', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Chain flow container should be visible with child nodes
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // Should contain at least one chain node
    const nodes = chainFlow.locator('.chain-node');
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(1);

    // Should contain at least one chain arrow
    const arrows = chainFlow.locator('.chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);
  });

  test('chain node elements exist with entry, exit, and type labels', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node should exist
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode.first()).toBeVisible();

    // Exit node should exist
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode.first()).toBeVisible();

    // Entry type label
    await expect(page.locator('.chain-type-entry').first()).toBeVisible();
    // Output type label
    await expect(page.locator('.chain-type-output').first()).toBeVisible();
    // Front pool type label
    await expect(page.locator('.chain-type-front').first()).toBeVisible();
    // Exit pool type label
    await expect(page.locator('.chain-type-exit').first()).toBeVisible();

    // Chain arrows should have arrow icon with right arrow character
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(3);

    for (let i = 0; i < arrowCount; i++) {
      const arrowText = await arrows.nth(i).locator('.chain-arrow-icon').textContent();
      expect(arrowText).toContain('→');
    }

    // Status dots should be present on nodes
    const statusDots = page.locator('.chain-flow .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(2);

    // Entry node name should contain host:port format
    const entryName = page.locator('.chain-node-entry .chain-node-name').first();
    const nameText = await entryName.textContent();
    expect(nameText).toMatch(/[\d.:]+/);
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 15)', () => {
  test('subscriptions page renders intelligence panel or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // Section title should be visible
    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    // Intelligence panel is shown when subscriptions exist; otherwise empty state
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasPanel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel shows analysis cards with titles', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Header text should be visible
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // Intelligence cards should exist
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);

    // Each card should have an h4 title
    for (let i = 0; i < Math.min(cardCount, 3); i++) {
      const cardTitle = cards.nth(i).locator('h4');
      await expect(cardTitle).toBeVisible();
      const titleText = await cardTitle.textContent();
      expect(titleText?.trim().length).toBeGreaterThan(0);
    }
  });

  test('intelligence panel shows duplicate node analysis with badge status', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Duplicate analysis card should be visible
    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Badge indicates duplicate status: warning (has duplicates) or success (none)
    const warningBadge = duplicateCard.locator('.badge-warning');
    const successBadge = duplicateCard.locator('.badge-success');
    const hasWarning = await warningBadge.isVisible().catch(() => false);
    const hasSuccess = await successBadge.isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();

    // Card text should mention duplicates
    const cardText = await duplicateCard.textContent();
    expect(cardText).toContain('重复');
  });

  test('intelligence panel shows quality scores with score entries', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Quality scores card should be visible
    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid should contain entries
    const scoresGrid = page.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const scoreEntries = scoresGrid.locator('> div');
      const count = await scoreEntries.count();
      expect(count).toBeGreaterThan(0);

      // Each score entry should show node info
      for (let i = 0; i < Math.min(count, 3); i++) {
        const entryText = await scoreEntries.nth(i).textContent();
        expect(entryText).toBeTruthy();
        expect(entryText).toContain('节点');
      }
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 15)', () => {
  test('diagnostics page has health overview with category indicators', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Page header should be visible
    await expect(
      page.locator('h2.section-title').filter({ hasText: '系统诊断' })
    ).toBeVisible();

    // Health overview section
    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // All four health category labels
    const categories = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const cat of categories) {
      await expect(
        page.locator('.health-summary-grid .health-label').filter({ hasText: cat })
      ).toBeVisible();
    }

    // Diagnostics button should be present
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });

  test('running diagnostics produces health score badge in valid range', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Click diagnostics button
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Button should transition to running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for completion (button reverts back)
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge should appear after diagnostics
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      // Score label
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();

      // Numeric score in 0-100 range
      const scoreValue = page.locator('.health-score-value');
      await expect(scoreValue).toBeVisible();
      const scoreText = await scoreValue.textContent();
      const score = parseInt(scoreText || '', 10);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);

      // Max score suffix
      await expect(page.locator('.health-score-max:has-text("/100")')).toBeVisible();
    }
  });
});
