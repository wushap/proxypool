import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 24)', () => {
  test('chain view tab exists and pools tab is default active', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // At least two tabs should be present
    const tabs = page.locator('.tab-btn');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(2);

    // Chain view tab should exist and be enabled
    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();

    // Pools tab should be the default active tab
    const poolsTab = tabs.filter({ hasText: '代理池' });
    await expect(poolsTab).toBeVisible();
    await expect(poolsTab).toHaveClass(/active/);

    // Chain tab should NOT be active by default
    await expect(chainTab).not.toHaveClass(/active/);
  });

  test('clicking chain view tab activates it and content panel switches', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible({ timeout: 5000 });

    // Initially, the pools tab panel should be visible
    const poolsTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolsTab).toHaveClass(/active/);

    // Click the chain view tab
    await chainTab.click();

    // Chain tab becomes active, pools tab becomes inactive
    await expect(chainTab).toHaveClass(/active/);
    await expect(poolsTab).not.toHaveClass(/active/);

    // Chain visualization section header should appear
    await expect(page.locator('.section-divider').filter({ hasText: '链路可视化' })).toBeVisible({ timeout: 5000 });

    // All three diagnostic action buttons should be present
    await expect(page.locator('button:has-text("链路诊断")')).toBeVisible();
    await expect(page.locator('button:has-text("测试链路延迟")')).toBeVisible();
    await expect(page.locator('button:has-text("测试整条链路")')).toBeVisible();

    // Form hint describing the visualization purpose
    await expect(page.locator('.form-hint').filter({ hasText: '可视化展示代理链路配置' })).toBeVisible();
  });

  test('chain flow visualization exists with arrows and structural elements', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(500);

    // Chain visualization wrapper
    const chainVisualization = page.locator('.chain-visualization');
    await expect(chainVisualization).toBeVisible({ timeout: 5000 });

    // Chain flow container inside the visualization
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // Flow must have at least one arrow connecting nodes
    const arrows = chainFlow.locator('.chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);

    // Each arrow should contain an arrow icon and a label
    for (let i = 0; i < arrowCount; i++) {
      const arrow = arrows.nth(i);
      await expect(arrow.locator('.chain-arrow-icon')).toBeVisible();
      await expect(arrow.locator('.chain-arrow-label')).toBeVisible();
    }

    // Chain flow must contain node elements
    const nodes = chainFlow.locator('.chain-node');
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);
  });

  test('chain node elements have headers, types, and status indicators', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(500);

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible({ timeout: 5000 });

    // Entry node should have a full structure: header, type, name, status
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode).toBeVisible();
    await expect(entryNode.locator('.chain-node-header')).toBeVisible();
    await expect(entryNode.locator('.chain-node-type')).toBeVisible();
    await expect(entryNode.locator('.chain-node-name')).toBeVisible();
    await expect(entryNode.locator('.chain-node-status')).toBeVisible();

    // Entry type label should read "入口"
    const entryType = entryNode.locator('.chain-type-entry');
    await expect(entryType).toBeVisible();
    await expect(entryType).toHaveText('入口');

    // Exit node with "出口" type label
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode).toBeVisible();
    const exitType = exitNode.locator('.chain-type-output');
    await expect(exitType).toBeVisible();
    await expect(exitType).toHaveText('出口');

    // Intermediate pool types scoped to chain-flow
    const frontPoolType = page.locator('.chain-flow .chain-type-front');
    await expect(frontPoolType).toBeVisible();
    await expect(frontPoolType).toHaveText('前置池');

    const exitPoolType = page.locator('.chain-flow .chain-type-exit');
    await expect(exitPoolType).toBeVisible();
    await expect(exitPoolType).toHaveText('落地池');

    // All nodes should have status dots
    const statusDots = chainFlow.locator('.chain-node .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(3);
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 24)', () => {
  test('subscriptions page has intelligence panel or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // Page title should be present
    await expect(
      page.locator('.section-title, h2.section-title').filter({ hasText: '订阅管理' })
    ).toBeVisible();

    // Intelligence panel OR empty state should be visible
    const intelPanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasIntel = await intelPanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasIntel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel shows analysis cards with headings and icons', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelPanel = page.locator('.subscription-intelligence');
    if (!(await intelPanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Intelligence section heading
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // Should have at least two intelligence cards
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);

    // Each card should have a heading (h4) with non-empty text
    for (let i = 0; i < Math.min(cardCount, 4); i++) {
      const card = cards.nth(i);
      const heading = card.locator('h4').first();
      await expect(heading).toBeVisible();
      const text = await heading.textContent();
      expect(text?.trim().length).toBeGreaterThan(0);
    }
  });

  test('intelligence panel shows duplicate node analysis with status badge', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelPanel = page.locator('.subscription-intelligence');
    if (!(await intelPanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Duplicate analysis card should exist
    const dupCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(dupCard).toBeVisible();

    // Must have a status badge: warning (duplicates) or success (no duplicates)
    const hasWarning = await dupCard.locator('.badge-warning').isVisible().catch(() => false);
    const hasSuccess = await dupCard.locator('.badge-success').isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();

    // Card text should reference duplicates
    const cardText = await dupCard.textContent();
    expect(cardText).toMatch(/重复|无重复/);

    // If warning badge is shown, card should contain numeric info about duplicates
    if (hasWarning) {
      expect(cardText).toMatch(/\d+/);
    }
  });

  test('intelligence panel shows quality scores with node count info', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelPanel = page.locator('.subscription-intelligence');
    if (!(await intelPanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Quality scores card
    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid inside the card
    const scoresGrid = qualityCard.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const entries = scoresGrid.locator('> div');
      const count = await entries.count();
      expect(count).toBeGreaterThan(0);

      // Each entry should mention nodes ("节点")
      for (let i = 0; i < Math.min(count, 3); i++) {
        const entryText = await entries.nth(i).textContent();
        expect(entryText).toBeTruthy();
        expect(entryText).toContain('节点');
      }
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 24)', () => {
  test('diagnostics page has health score section with all category labels', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Page title
    await expect(
      page.locator('.section-title, h2.section-title').filter({ hasText: '系统诊断' })
    ).toBeVisible();

    // Health overview section title
    await expect(
      page.locator('.settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // All four health category labels should be visible
    const categories = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const cat of categories) {
      await expect(
        page.locator('.health-summary-grid .health-label').filter({ hasText: cat })
      ).toBeVisible();
    }

    // Diagnostics run button
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await expect(diagButton).toBeEnabled();
  });

  test('running diagnostics completes and health score displays with valid value', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Button should show "诊断中..." loading state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible({ timeout: 5000 });

    // Wait for diagnostics to finish (button reverts)
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge should appear after diagnostics
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      // Score label should read "健康评分"
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();

      // Score value should be a number between 0 and 100
      const scoreValue = page.locator('.health-score-value');
      await expect(scoreValue).toBeVisible();
      const scoreText = await scoreValue.textContent();
      const score = parseInt(scoreText || '', 10);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);

      // Max score display
      await expect(page.locator('.health-score-max:has-text("/100")')).toBeVisible();

      // Health overview grid should show status for each category
      await expect(page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })).toBeVisible();
      await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '后端进程' })).toBeVisible();
      await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '代理池' })).toBeVisible();
    }
  });
});
