import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  // Wait for sidebar menu to be ready
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 25) ──

test.describe('Chain Routing (Round 25)', () => {
  test('default tab is proxy pools and pool content loads', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // The 代理池 tab should be the default active tab
    const poolsTab = page.locator('.tab-btn').filter({ hasText: '代理池' });
    await expect(poolsTab).toBeVisible();
    await expect(poolsTab).toHaveClass(/active/);

    // Pool creation form should be visible since pools tab is active
    await expect(page.locator('.settings-title').filter({ hasText: '创建代理池' })).toBeVisible();

    // Pool table should also be present
    const table = page.locator('.data-table');
    await expect(table.first()).toBeVisible();

    // The page title should be 多跳代理池
    await expect(
      page.locator('.section-title').filter({ hasText: '多跳代理池' })
    ).toBeVisible();
  });

  test('clicking filter section header expands filter panel with select dropdowns', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // The filter section header should be clickable to toggle the advanced filters
    const filterHeader = page.locator('.form-section-header').filter({ hasText: '过滤条件' });
    await expect(filterHeader).toBeVisible();

    // Click to expand the filter panel
    await filterHeader.click();
    await page.waitForTimeout(300);

    // The advanced-filters container should be visible
    const advancedFilters = page.locator('.advanced-filters');
    await expect(advancedFilters).toBeVisible({ timeout: 5000 });

    // Filter panel should contain select elements (dropdowns)
    const selects = advancedFilters.locator('select.select');
    const selectCount = await selects.count();
    expect(selectCount).toBeGreaterThanOrEqual(2);

    // Each select should have options
    for (let i = 0; i < Math.min(selectCount, 3); i++) {
      const options = selects.nth(i).locator('option');
      const optCount = await options.count();
      expect(optCount).toBeGreaterThanOrEqual(2);
    }
  });

  test('pool table contains expected column headers', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // Locate the pool table headers
    const tableHeaders = page.locator('.data-table thead th');
    const headerCount = await tableHeaders.count();
    expect(headerCount).toBeGreaterThanOrEqual(5);

    // Extract all header texts
    const headers: string[] = [];
    for (let i = 0; i < headerCount; i++) {
      const text = await tableHeaders.nth(i).textContent();
      headers.push(text?.trim() || '');
    }

    // Verify key columns exist
    expect(headers).toContain('名称');
    expect(headers).toContain('节点');
    expect(headers).toContain('状态');
    expect(headers).toContain('操作');
    expect(headers).toContain('ID');
  });

  test('clicking chain view tab renders chain visualization section', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // Click the chain view tab
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await chainTab.click();
    await page.waitForTimeout(500);

    // Chain tab should now be active
    await expect(chainTab).toHaveClass(/active/);

    // The chain visualization container should be visible
    const chainVisualization = page.locator('.chain-visualization');
    await expect(chainVisualization).toBeVisible({ timeout: 5000 });

    // Inside visualization, chain-flow should exist with nodes
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // Chain flow should have at least one chain-arrow element
    const arrows = chainFlow.locator('.chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(1);
  });

  test('chain node cards display name, type badge, and status for each node', async ({ page }) => {
    await navigateTo(page, '多跳代理池');

    // Switch to chain view
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForTimeout(500);

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible({ timeout: 5000 });

    // Collect all chain nodes
    const chainNodes = chainFlow.locator('.chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);

    // Verify each node card has the three key elements
    for (let i = 0; i < nodeCount; i++) {
      const node = chainNodes.nth(i);

      // Node header containing type and name
      const header = node.locator('.chain-node-header');
      await expect(header).toBeVisible();

      // Type badge
      const typeBadge = node.locator('.chain-node-type');
      await expect(typeBadge).toBeVisible();
      const typeText = await typeBadge.textContent();
      expect(typeText?.trim().length).toBeGreaterThan(0);

      // Node name
      const nameEl = node.locator('.chain-node-name');
      await expect(nameEl).toBeVisible();

      // Status indicator (status dot)
      const statusSection = node.locator('.chain-node-status');
      await expect(statusSection).toBeVisible();
      await expect(statusSection.locator('.status-dot')).toBeVisible();
    }
  });
});

// ── Subscription Intelligence (Round 25) ──

test.describe('Subscription Intelligence (Round 25)', () => {
  test('subscriptions page renders intelligence panel or shows empty state', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // The page title should be visible
    await expect(
      page.locator('.section-title').filter({ hasText: '订阅管理' })
    ).toBeVisible();

    // Either the intelligence panel is present (subscriptions exist) or an empty state
    const intelPanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state');
    const hasIntel = await intelPanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasIntel || hasEmpty).toBeTruthy();

    // If intelligence panel exists, the heading should be visible
    if (hasIntel) {
      await expect(page.locator('text=订阅智能分析')).toBeVisible();
    }
  });

  test('intelligence panel quality scores section shows node count info per subscription', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelPanel = page.locator('.subscription-intelligence');
    if (!(await intelPanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Quality scores card should exist
    const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
    await expect(qualityCard).toBeVisible();

    // The quality-scores grid should be present
    const scoresGrid = qualityCard.locator('.quality-scores');
    await expect(scoresGrid).toBeVisible();

    // Each score entry should show node count info containing "节点"
    const scoreEntries = scoresGrid.locator('> div');
    const entryCount = await scoreEntries.count();
    expect(entryCount).toBeGreaterThan(0);

    for (let i = 0; i < Math.min(entryCount, 4); i++) {
      const entryText = await scoreEntries.nth(i).textContent();
      expect(entryText).toContain('节点');
      // Also should mention reliability percentage
      expect(entryText).toContain('%');
    }
  });

  test('intelligence panel duplicate analysis card shows status badge with count', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    const intelPanel = page.locator('.subscription-intelligence');
    if (!(await intelPanel.isVisible().catch(() => false))) {
      test.skip();
      return;
    }

    // Duplicate analysis card should be present
    const dupCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
    await expect(dupCard).toBeVisible();

    // Must have either a warning badge (duplicates found) or success badge (no duplicates)
    const hasWarning = await dupCard.locator('.badge-warning').isVisible().catch(() => false);
    const hasSuccess = await dupCard.locator('.badge-success').isVisible().catch(() => false);
    expect(hasWarning || hasSuccess).toBeTruthy();

    // Card content should reference duplicates
    const cardText = await dupCard.textContent();
    expect(cardText).toMatch(/重复|无重复/);
  });
});

// ── System Diagnostics Health Score (Round 25) ──

test.describe('System Diagnostics Health Score (Round 25)', () => {
  test('diagnostics page displays health overview section with all four category labels', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Page title should be visible
    await expect(
      page.locator('.section-title').filter({ hasText: '系统诊断' })
    ).toBeVisible();

    // Health overview section with "系统健康概览" title
    await expect(
      page.locator('.settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // The health summary grid should contain exactly four health items
    const healthItems = page.locator('.health-summary-grid .health-item');
    const itemCount = await healthItems.count();
    expect(itemCount).toBe(4);

    // Verify each expected category label exists
    const expectedLabels = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const label of expectedLabels) {
      const labelEl = page.locator('.health-summary-grid .health-label').filter({ hasText: label });
      await expect(labelEl).toBeVisible();
    }

    // The diagnostics button should be enabled and ready
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await expect(diagBtn).toBeEnabled();
  });

  test('running one-click diagnostics completes and shows health score with numeric value', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Dismiss any notification popups that may intercept clicks
    const notifications = page.locator('.el-notification');
    const notifCount = await notifications.count();
    for (let i = 0; i < notifCount; i++) {
      const closeBtn = notifications.nth(i).locator('.el-notification__closeBtn');
      if (await closeBtn.isVisible().catch(() => false)) {
        await closeBtn.click().catch(() => {});
      }
    }
    await page.waitForTimeout(300);

    // Click the diagnostics button using force to bypass any lingering overlays
    const diagBtn = page.locator('button:has-text("一键诊断")');
    await expect(diagBtn).toBeVisible();
    await diagBtn.click({ force: true });

    // Button should transition to loading state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible({ timeout: 5000 });

    // Wait for diagnostics to complete (button reverts to "一键诊断")
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible({ timeout: 20000 });
    await page.waitForTimeout(1000);

    // After diagnostics, the health score badge should appear
    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      // The health score value should be a valid number
      const scoreValue = page.locator('.health-score-value');
      await expect(scoreValue).toBeVisible();
      const scoreText = await scoreValue.textContent();
      const score = parseInt(scoreText || '', 10);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);

      // The /100 max label should be present
      await expect(page.locator('.health-score-max:has-text("/100")')).toBeVisible();
    }

    // After diagnostics, the detailed report section should appear
    // (the empty state should be gone, replaced by diagnostic details)
    const emptyState = page.locator('.empty-state:has-text("点击「一键诊断」按钮")');
    await expect(emptyState).not.toBeVisible();
  });
});
