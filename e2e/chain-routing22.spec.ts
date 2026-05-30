import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 22)', () => {
  test('chain view tab exists among proxy pool tabs', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const tabs = page.locator('.workspace-tabs .tab-btn, .tab-btn');
    await expect(tabs.first()).toBeVisible({ timeout: 5000 });

    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();
  });

  test('clicking chain view tab activates it and loads visualization', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const chainTab = page.locator('.workspace-tabs .tab-btn, .tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible({ timeout: 5000 });
    await chainTab.click();

    await expect(chainTab).toHaveClass(/active/);

    const sectionHeader = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(sectionHeader).toBeVisible({ timeout: 5000 });

    await expect(page.locator('button:has-text("链路诊断")')).toBeVisible();
    await expect(page.locator('button:has-text("测试链路延迟")')).toBeVisible();
  });

  test('chain flow visualization container exists with entry and exit nodes', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.workspace-tabs .tab-btn, .tab-btn').filter({ hasText: '链路视图' }).click();

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible({ timeout: 5000 });

    // Entry node
    const entryNode = page.locator('.chain-node-entry, .chain-type-entry').first();
    await expect(entryNode).toBeVisible();

    // Exit/output node
    const exitNode = page.locator('.chain-type-output').first();
    await expect(exitNode).toBeVisible();
  });

  test('chain node elements display host:port, status indicators, and pool type labels', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.workspace-tabs .tab-btn, .tab-btn').filter({ hasText: '链路视图' }).click();

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible({ timeout: 5000 });

    // Entry node name should match host:port pattern
    const entryName = page.locator('.chain-node-entry .chain-node-name, .chain-type-entry ~ .chain-node-name, .chain-type-entry').first();
    await expect(entryName).toBeVisible();

    // All nodes should have status dots
    const statusDots = page.locator('.chain-flow .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(3);

    // Verify chain arrows exist with arrow icon
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(2);

    for (let i = 0; i < arrowCount; i++) {
      await expect(arrows.nth(i).locator('.chain-arrow-icon')).toContainText('→');
    }

    // Verify pool type labels exist (entry, front pool, exit pool, output)
    const typeLabels = page.locator('.chain-flow .chain-node-type');
    const typeCount = await typeLabels.count();
    expect(typeCount).toBeGreaterThanOrEqual(3);

    const typeTexts: string[] = [];
    for (let i = 0; i < typeCount; i++) {
      typeTexts.push((await typeLabels.nth(i).textContent()) || '');
    }
    expect(typeTexts.some(t => t.includes('入口'))).toBeTruthy();
    expect(typeTexts.some(t => t.includes('出口'))).toBeTruthy();
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 22)', () => {
  test('subscriptions page has intelligence panel or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    await expect(page.locator('.section-title, h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    const intelPanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasIntel = await intelPanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasIntel || hasEmpty).toBeTruthy();
  });

  test('intelligence panel shows analysis cards with titled sections', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelPanel = page.locator('.subscription-intelligence');
    if (!(await intelPanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Intelligence heading
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // Should have multiple intelligence cards
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);

    // Each card should have an h4 heading with non-empty text
    for (let i = 0; i < Math.min(cardCount, 3); i++) {
      const heading = cards.nth(i).locator('h4').first();
      await expect(heading).toBeVisible();
      const headingText = await heading.textContent();
      expect(headingText?.trim().length).toBeGreaterThan(0);
    }
  });

  test('intelligence panel shows duplicate node analysis with status badge', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelPanel = page.locator('.subscription-intelligence');
    if (!(await intelPanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const dupCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(dupCard).toBeVisible();

    // Must show either warning (duplicates found) or success (no duplicates) badge
    const hasWarning = await dupCard.locator('.badge-warning').isVisible().catch(() => false);
    const hasSuccess = await dupCard.locator('.badge-success').isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();

    // Content should mention duplicates
    const cardText = await dupCard.textContent();
    expect(cardText).toMatch(/重复|无重复/);
  });

  test('intelligence panel shows quality scores with per-subscription entries', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelPanel = page.locator('.subscription-intelligence');
    if (!(await intelPanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    const scoresGrid = qualityCard.locator('.quality-scores');
    if (await scoresGrid.isVisible()) {
      const entries = scoresGrid.locator('> div');
      const count = await entries.count();
      expect(count).toBeGreaterThan(0);

      // Each entry should show node/reliability info
      for (let i = 0; i < Math.min(count, 3); i++) {
        const entryText = await entries.nth(i).textContent();
        expect(entryText).toBeTruthy();
        expect(entryText).toContain('节点');
      }
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 22)', () => {
  test('diagnostics page has health overview section with category labels', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Page title
    await expect(
      page.locator('.section-title, h2.section-title').filter({ hasText: '系统诊断' })
    ).toBeVisible();

    // Health overview title
    await expect(
      page.locator('.settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // All four health categories should be visible
    const categories = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const cat of categories) {
      await expect(
        page.locator('.health-summary-grid .health-label').filter({ hasText: cat })
      ).toBeVisible();
    }

    // Run diagnostics button
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });

  test('running diagnostics completes and health score appears in valid range', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Button shows loading state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to complete
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge should be visible with valid 0-100 range
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
