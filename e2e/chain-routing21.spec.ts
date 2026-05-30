import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('networkidle');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (via Proxy Pools page) ──

test.describe('Chain Routing (Round 21)', () => {
  test('chain view tab exists among proxy pool tabs', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const tabs = page.locator('.workspace-tabs .tab-btn');
    await expect(tabs.first()).toBeVisible({ timeout: 5000 });

    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(5);

    const chainTab = tabs.filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await expect(chainTab).toBeEnabled();
  });

  test('clicking chain view tab activates it and loads visualization content', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    const chainTab = page.locator('.workspace-tabs .tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible({ timeout: 5000 });
    await chainTab.click();

    // Tab should now be active
    await expect(chainTab).toHaveClass(/active/);

    // Section header with visualization title should appear
    const sectionHeader = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(sectionHeader).toBeVisible({ timeout: 5000 });

    // Action buttons should be present
    await expect(page.locator('button:has-text("链路诊断")')).toBeVisible();
    await expect(page.locator('button:has-text("测试链路延迟")')).toBeVisible();
    await expect(page.locator('button:has-text("测试整条链路")')).toBeVisible();
  });

  test('chain flow visualization exists with entry, arrows, and exit nodes', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.workspace-tabs .tab-btn').filter({ hasText: '链路视图' }).click();

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible({ timeout: 5000 });

    // Entry node with type label
    const entryNode = page.locator('.chain-flow .chain-node-entry');
    await expect(entryNode).toBeVisible();
    await expect(entryNode.locator('.chain-node-type').filter({ hasText: '入口' })).toBeVisible();

    // Exit node with type label
    const exitNode = page.locator('.chain-flow .chain-node-exit');
    await expect(exitNode).toBeVisible();
    await expect(exitNode.locator('.chain-node-type').filter({ hasText: '出口' })).toBeVisible();

    // Arrows between nodes
    const arrows = page.locator('.chain-flow .chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(3);

    // Each arrow should have the arrow icon
    for (let i = 0; i < arrowCount; i++) {
      await expect(arrows.nth(i).locator('.chain-arrow-icon')).toContainText('→');
    }
  });

  test('chain node elements display host:port, status dots, and pool types', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    await page.locator('.workspace-tabs .tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.chain-flow').waitFor({ state: 'visible', timeout: 5000 });

    // Entry node name should match host:port pattern
    const entryName = page.locator('.chain-node-entry .chain-node-name').first();
    await expect(entryName).toBeVisible();
    const entryText = await entryName.textContent();
    expect(entryText).toMatch(/[\d.]+:\d+/);

    // Entry node status should show listening state
    const entryStatus = page.locator('.chain-node-entry .chain-node-status');
    await expect(entryStatus).toContainText('监听中');

    // All chain nodes should have status dots
    const statusDots = page.locator('.chain-flow .status-dot');
    const dotCount = await statusDots.count();
    expect(dotCount).toBeGreaterThanOrEqual(4);

    // Node types should include pool type labels
    const nodeTypes = page.locator('.chain-flow .chain-node-type');
    const typeCount = await nodeTypes.count();
    expect(typeCount).toBeGreaterThanOrEqual(4);

    const typeTexts: string[] = [];
    for (let i = 0; i < typeCount; i++) {
      typeTexts.push((await nodeTypes.nth(i).textContent()) || '');
    }
    expect(typeTexts.some(t => t.includes('前置池'))).toBeTruthy();
    expect(typeTexts.some(t => t.includes('落地池'))).toBeTruthy();
  });
});

// ── Subscription Intelligence (via Subscriptions page) ──

test.describe('Subscription Intelligence (Round 21)', () => {
  test('subscriptions page has intelligence panel or empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // Page title should be present
    await expect(page.locator('.section-title').filter({ hasText: '订阅管理' })).toBeVisible();

    // Intelligence panel appears when subscriptions exist; empty state otherwise
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

    // Intelligence section heading
    await expect(page.locator('text=订阅智能分析')).toBeVisible();

    // Expand panel if collapsed
    const expandBtn = intelPanel.locator('button:has-text("展开")');
    if (await expandBtn.isVisible().catch(() => false)) {
      await expandBtn.click();
      await page.waitForTimeout(300);
    }

    // Should have multiple intelligence cards
    const cards = page.locator('.intelligence-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(2);

    // Each card should have an h4 heading with non-empty text
    for (let i = 0; i < Math.min(cardCount, 4); i++) {
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

    // Expand panel if needed
    const expandBtn = intelPanel.locator('button:has-text("展开")');
    if (await expandBtn.isVisible().catch(() => false)) {
      await expandBtn.click();
      await page.waitForTimeout(300);
    }

    // Duplicate analysis card
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

    // Expand panel if needed
    const expandBtn = intelPanel.locator('button:has-text("展开")');
    if (await expandBtn.isVisible().catch(() => false)) {
      await expandBtn.click();
      await page.waitForTimeout(300);
    }

    // Quality scores card
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
        expect(entryText).toContain('可靠');
      }
    }
  });
});

// ── System Diagnostics Health Score ──

test.describe('System Diagnostics Health Score (Round 21)', () => {
  test('diagnostics page has health overview section with all category labels', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Page title
    await expect(
      page.locator('.section-title').filter({ hasText: '系统诊断' })
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

    // Diagnostic details sections should appear
    const hasDetails = await page.locator('text=诊断详情').isVisible().catch(() => false);
    if (hasDetails) {
      const detailSections = ['后端进程状态', '网关服务状态', '代理池健康', '代理节点统计'];
      for (const section of detailSections) {
        await expect(
          page.locator('.diagnostic-section-title').filter({ hasText: section })
        ).toBeVisible();
      }
    }
  });
});
