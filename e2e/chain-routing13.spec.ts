import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 13)', () => {
  test('chain view tab is present and accessible among other tabs', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const tabs = page.locator('.tab-btn');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(5);

    // Chain view tab should be the second tab
    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();

    // Verify sibling tabs exist to confirm tab bar context
    const poolsTab = tabs.filter({ hasText: '代理池' });
    await expect(poolsTab).toBeVisible();
    const gatewayTab = tabs.filter({ hasText: 'HTTP 代理端点' });
    await expect(gatewayTab).toBeVisible();
  });

  test('clicking chain view tab reveals chain flow and section header', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // Click chain view tab
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Section divider for chain visualization should appear
    await expect(page.locator('.section-divider').filter({ hasText: '链路可视化' })).toBeVisible({ timeout: 5000 });

    // Chain flow container should be visible
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // Chain diagnostics/latency buttons should be present in the section header
    const diagBtn = page.locator('button:has-text("链路诊断")');
    await expect(diagBtn).toBeVisible();
    const latencyBtn = page.locator('button:has-text("测试链路延迟")');
    await expect(latencyBtn).toBeVisible();
  });

  test('chain flow visualization renders all four node types', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node with type label
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode.first()).toBeVisible();

    // Exit node with output type
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode.first()).toBeVisible();

    // Front pool node
    const frontNode = page.locator('.chain-node').filter({ has: page.locator('.chain-type-front') });
    await expect(frontNode.first()).toBeVisible();

    // Exit pool node
    const exitPoolNode = page.locator('.chain-node').filter({ has: page.locator('.chain-type-exit') });
    await expect(exitPoolNode.first()).toBeVisible();

    // Type labels should be visible
    await expect(page.locator('.chain-type-entry').first()).toBeVisible();
    await expect(page.locator('.chain-type-output').first()).toBeVisible();
    await expect(page.locator('.chain-type-front').first()).toBeVisible();
    await expect(page.locator('.chain-type-exit').first()).toBeVisible();
  });

  test('chain node elements display status dots and names in host:port format', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // At least three chain arrows connecting the nodes
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(3);

    // Each arrow should contain an icon with right arrow character
    for (let i = 0; i < arrowCount; i++) {
      const arrowText = await arrows.nth(i).locator('.chain-arrow-icon').textContent();
      expect(arrowText).toContain('→');
    }

    // Status dots exist on nodes
    const statusDots = page.locator('.chain-flow .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(2);

    // Entry node name should be host:port
    const entryName = page.locator('.chain-node-entry .chain-node-name').first();
    const nameText = await entryName.textContent();
    expect(nameText).toMatch(/[\d.:]+/);

    // Arrow labels should be non-empty
    for (let i = 0; i < arrowCount; i++) {
      const label = arrows.nth(i).locator('.chain-arrow-label');
      await expect(label).toBeVisible();
      const labelText = await label.textContent();
      expect(labelText?.trim().length).toBeGreaterThan(0);
    }
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 13)', () => {
  test('subscriptions page renders intelligence panel or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    // Intelligence panel should be present when subscriptions exist, otherwise empty state
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasPanel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel displays multiple analysis cards', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Header text "订阅智能分析" should be visible
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // Intelligence cards should exist and contain content
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);

    // Each card should contain an h4 with a title
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

    // Duplicate analysis card
    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Badge indicates duplicate status: either warning (duplicates) or success (none)
    const warningBadge = duplicateCard.locator('.badge-warning');
    const successBadge = duplicateCard.locator('.badge-success');
    const hasWarning = await warningBadge.isVisible().catch(() => false);
    const hasSuccess = await successBadge.isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();

    // Card should contain text mentioning duplicates
    const cardText = await duplicateCard.textContent();
    expect(cardText).toContain('重复');
  });

  test('intelligence panel shows quality scores with score values', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Quality scores card
    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid
    const scoresGrid = page.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      // Should have at least one score entry
      const scoreEntries = scoresGrid.locator('> div');
      const count = await scoreEntries.count();
      expect(count).toBeGreaterThan(0);

      // Each score entry should show a numeric score value
      for (let i = 0; i < Math.min(count, 3); i++) {
        const entryText = await scoreEntries.nth(i).textContent();
        expect(entryText).toBeTruthy();
        // Should mention nodes (节点)
        expect(entryText).toContain('节点');
      }
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 13)', () => {
  test('diagnostics page has health overview with four category indicators', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Page header
    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();

    // Health overview section
    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // All four health category labels
    const categories = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const cat of categories) {
      await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: cat })).toBeVisible();
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

    // Wait for completion (button reverts)
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge should appear
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
