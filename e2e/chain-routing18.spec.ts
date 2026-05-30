import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 18)', () => {
  test('chain view tab exists among proxy pool tabs', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const tabs = page.locator('.tab-btn');
    await expect(tabs.first()).toBeVisible({ timeout: 5000 });
    const tabCount = await tabs.count();
    expect(tabCount).toBeGreaterThanOrEqual(3);

    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();
  });

  test('clicking chain view tab loads content with section and actions', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    await expect(
      page.locator('.section-divider').filter({ hasText: '链路可视化' })
    ).toBeVisible({ timeout: 5000 });

    await expect(page.locator('button:has-text("链路诊断")')).toBeVisible();
    await expect(page.locator('button:has-text("测试链路延迟")')).toBeVisible();
  });

  test('chain flow visualization has nodes connected by arrows', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    const nodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);

    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);
  });

  test('chain node elements show names and status indicators', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node has host:port pattern
    const entryName = page.locator('.chain-node-entry .chain-node-name').first();
    await expect(entryName).toBeVisible();
    const entryText = await entryName.textContent();
    expect(entryText).toMatch(/[\d.:]+/);

    // Exit node has non-empty name
    const exitName = page.locator('.chain-node-exit .chain-node-name').first();
    await expect(exitName).toBeVisible();
    const exitText = await exitName.textContent();
    expect(exitText?.trim().length).toBeGreaterThan(0);

    // Status dots on nodes
    const statusDots = page.locator('.chain-flow .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(2);

    // Arrow icons between nodes
    const arrowIcons = page.locator('.chain-flow .chain-arrow-icon');
    const arrowIconCount = await arrowIcons.count();
    expect(arrowIconCount).toBeGreaterThanOrEqual(1);
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 18)', () => {
  test('subscriptions page has intelligence panel or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    await expect(page.locator('h2.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

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

    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);

    for (let i = 0; i < Math.min(cardCount, 4); i++) {
      const title = cards.nth(i).locator('h4');
      await expect(title).toBeVisible();
      const titleText = await title.textContent();
      expect(titleText?.trim().length).toBeGreaterThan(0);
    }
  });

  test('intelligence panel has duplicate node analysis card', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelligencePanel = page.locator('.subscription-intelligence');
    if (!(await intelligencePanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(duplicateCard).toBeVisible();

    // Must have either warning or success badge
    const warningBadge = duplicateCard.locator('.badge-warning');
    const successBadge = duplicateCard.locator('.badge-success');
    const hasWarning = await warningBadge.isVisible().catch(() => false);
    const hasSuccess = await successBadge.isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();

    const cardText = await duplicateCard.textContent();
    expect(cardText).toContain('重复');
  });

  test('intelligence panel shows quality scores with entries', async ({ page }) => {
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
      const scoreEntries = scoresGrid.locator('> div');
      const count = await scoreEntries.count();
      expect(count).toBeGreaterThan(0);

      for (let i = 0; i < Math.min(count, 3); i++) {
        const entryText = await scoreEntries.nth(i).textContent();
        expect(entryText).toBeTruthy();
        expect(entryText).toContain('节点');
      }
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 18)', () => {
  test('diagnostics page has health score section with category labels', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    await expect(
      page.locator('h2.section-title').filter({ hasText: '系统诊断' })
    ).toBeVisible();

    await expect(
      page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    const categories = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const cat of categories) {
      await expect(
        page.locator('.health-summary-grid .health-label').filter({ hasText: cat })
      ).toBeVisible();
    }

    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });

  test('running diagnostics produces health score in 0-100 range', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for diagnostics to finish
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(1000);

    // Health score badge with valid range
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
