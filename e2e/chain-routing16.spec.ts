import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 16)', () => {
  test('chain view tab exists alongside other proxy pool tabs', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // Tab bar should have multiple tabs
    const tabs = page.locator('.tab-btn');
    await expect(tabs.first()).toBeVisible();
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(3);

    // Chain view tab specifically
    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();
  });

  test('clicking chain view tab reveals visualization section and action buttons', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // Switch to chain view
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Section divider for chain visualization
    await expect(
      page.locator('.section-divider').filter({ hasText: '链路可视化' })
    ).toBeVisible({ timeout: 5000 });

    // Action buttons should be present
    await expect(page.locator('button:has-text("链路诊断")')).toBeVisible();
    await expect(page.locator('button:has-text("测试链路延迟")')).toBeVisible();
  });

  test('chain flow visualization contains typed nodes and arrow connectors', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Chain flow container should have multiple nodes
    const nodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);

    // Chain arrows connect the nodes
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);

    // Pool type legend should be visible
    const legendItems = page.locator('.pool-type-legend .legend-item');
    const legendCount = await legendItems.count();
    expect(legendCount).toBeGreaterThanOrEqual(2);
  });

  test('chain node elements display names and status indicators', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node with name containing host:port
    const entryName = page.locator('.chain-node-entry .chain-node-name').first();
    await expect(entryName).toBeVisible();
    const entryText = await entryName.textContent();
    expect(entryText).toMatch(/[\d.:]+/);

    // Exit node with name (may be host:port or label like "目标网站")
    const exitName = page.locator('.chain-node-exit .chain-node-name').first();
    await expect(exitName).toBeVisible();
    const exitText = await exitName.textContent();
    expect(exitText?.trim().length).toBeGreaterThan(0);

    // Status dots on nodes
    const statusDots = page.locator('.chain-flow .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(2);

    // Arrow icons contain right arrow character
    const arrowIcons = page.locator('.chain-flow .chain-arrow-icon');
    const arrowIconCount = await arrowIcons.count();
    expect(arrowIconCount).toBeGreaterThanOrEqual(1);
    for (let i = 0; i < arrowIconCount; i++) {
      const iconText = await arrowIcons.nth(i).textContent();
      expect(iconText).toContain('→');
    }
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 16)', () => {
  test('subscriptions page has intelligence panel or empty state fallback', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // Page title
    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    // Intelligence panel shown when subscriptions exist
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasPanel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel renders analysis cards with non-empty titles', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Intelligence header
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // Analysis cards
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);

    // Each card should have a title
    for (let i = 0; i < Math.min(cardCount, 4); i++) {
      const title = cards.nth(i).locator('h4');
      await expect(title).toBeVisible();
      const titleText = await title.textContent();
      expect(titleText?.trim().length).toBeGreaterThan(0);
    }
  });

  test('intelligence panel shows duplicate node analysis with status badge', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Duplicate analysis card
    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Must have either warning (duplicates found) or success (no duplicates) badge
    const warningBadge = duplicateCard.locator('.badge-warning');
    const successBadge = duplicateCard.locator('.badge-success');
    const hasWarning = await warningBadge.isVisible().catch(() => false);
    const hasSuccess = await successBadge.isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();

    // Text should mention duplicate-related content
    const cardText = await duplicateCard.textContent();
    expect(cardText).toContain('重复');
  });

  test('intelligence panel shows quality scores with score grid entries', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Quality scores card
    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid with entries
    const scoresGrid = page.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const scoreEntries = scoresGrid.locator('> div');
      const count = await scoreEntries.count();
      expect(count).toBeGreaterThan(0);

      // Each score entry should reference nodes
      for (let i = 0; i < Math.min(count, 3); i++) {
        const entryText = await scoreEntries.nth(i).textContent();
        expect(entryText).toBeTruthy();
        expect(entryText).toContain('节点');
      }
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 16)', () => {
  test('diagnostics page has health score section with category labels', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Page header
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

    // Diagnostics button present
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });

  test('running diagnostics produces health score in valid 0-100 range', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Run diagnostics
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for completion
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
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
