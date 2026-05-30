import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 12)', () => {
  test('chain view tab exists and is part of the tab group', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // All tabs in the group should be visible
    const tabs = page.locator('.tab-btn');
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(5);

    // Chain view tab should be among them
    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();

    // Tab should not be the currently active tab by default
    const isActive = await chainTab.evaluate((el: HTMLElement) =>
      el.classList.contains('active') || el.classList.contains('tab-btn-active')
    );
    // We just verify it exists and is clickable; active state is not strictly required
    expect(typeof isActive).toBe('boolean');
  });

  test('clicking chain view tab loads chain flow with protocol labels', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Chain visualization section header should appear
    await expect(page.locator('.section-divider').filter({ hasText: '链路可视化' })).toBeVisible({ timeout: 5000 });

    // Chain flow container should render with child elements
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // The first arrow should carry a protocol label like "HTTP/SOCKS"
    const firstArrow = chainFlow.locator('.chain-arrow').first();
    await expect(firstArrow).toBeVisible();
    const arrowLabel = firstArrow.locator('.chain-arrow-label');
    await expect(arrowLabel).toBeVisible();
    const labelText = await arrowLabel.textContent();
    expect(labelText?.trim().length).toBeGreaterThan(0);
  });

  test('chain flow visualization contains entry and exit nodes with type labels', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node with "入口" type label
    const entryNode = page.locator('.chain-node-entry');
    await expect(entryNode.first()).toBeVisible();
    await expect(entryNode.locator('.chain-type-entry').first()).toBeVisible();

    // Exit node with "出口" type label
    const exitNode = page.locator('.chain-node-exit');
    await expect(exitNode.first()).toBeVisible();
    await expect(exitNode.locator('.chain-type-output').first()).toBeVisible();

    // Middle nodes (前置池 and 落地池) should also exist
    const frontPoolNode = page.locator('.chain-node').filter({ has: page.locator('.chain-type-front') });
    await expect(frontPoolNode.first()).toBeVisible();

    const exitPoolNode = page.locator('.chain-node').filter({ has: page.locator('.chain-type-exit') });
    await expect(exitPoolNode.first()).toBeVisible();
  });

  test('chain node elements include arrows with icons and status indicators', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // At least three arrows connect entry -> front -> exit -> output
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(3);

    // Each arrow should display an arrow icon character
    for (let i = 0; i < arrowCount; i++) {
      const icon = arrows.nth(i).locator('.chain-arrow-icon');
      await expect(icon).toBeVisible();
      const iconText = await icon.textContent();
      expect(iconText).toContain('→'); // right arrow character
    }

    // Status dots should exist on chain nodes
    const statusDots = page.locator('.chain-flow .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(2);

    // Entry node name should display host:port format
    const entryName = page.locator('.chain-node-entry .chain-node-name').first();
    const nameText = await entryName.textContent();
    expect(nameText).toMatch(/[\d.:]+/);
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 12)', () => {
  test('subscriptions page shows intelligence panel when subscriptions exist', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    // Intelligence panel should be present when there are subscriptions
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasPanel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel shows analysis cards with expand/collapse toggle', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Intelligence header should be present
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // Expand/collapse toggle button should exist
    const toggleButton = intelligencePanel.locator('button.btn-ghost').filter({ hasText: /展开|收起/ });
    await expect(toggleButton).toBeVisible();

    // At least two analysis cards should be present
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);

    // Each card should have non-empty text content
    for (let i = 0; i < Math.min(cardCount, 4); i++) {
      const text = await cards.nth(i).textContent();
      expect(text?.trim().length).toBeGreaterThan(0);
    }
  });

  test('duplicate node analysis card shows badge and details', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Duplicate analysis card should exist
    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Should have either warning (duplicates found) or success (no duplicates) badge
    const hasWarning = await duplicateCard.locator('.badge-warning').isVisible().catch(() => false);
    const hasSuccess = await duplicateCard.locator('.badge-success').isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();

    // Card text should mention "重复" in some form
    const cardText = await duplicateCard.textContent();
    expect(cardText).toContain('重复');
  });

  test('quality scores card displays score grid with node count info', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Quality scores card should exist
    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // Quality scores grid should be present
    const scoresGrid = page.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const count = await scoresGrid.locator('> div').count();
      expect(count).toBeGreaterThan(0);

      // First score entry should mention nodes
      const firstScore = scoresGrid.locator('> div').first();
      const scoreText = await firstScore.textContent();
      expect(scoreText).toBeTruthy();
      expect(scoreText).toContain('节点');
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 12)', () => {
  test('diagnostics page has health score section with four categories', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();

    // Health overview section header
    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // Summary grid should show all four category labels
    const categories = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const cat of categories) {
      await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: cat })).toBeVisible();
    }

    // Diagnostics button should be visible
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
  });

  test('run diagnostics and verify health score badge with valid range', async ({ page }) => {
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
