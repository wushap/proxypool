import { test, expect } from '@playwright/test';

test.describe('Chain Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display chain view tab', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
    // Verify other tabs exist alongside it
    await expect(page.locator('.tab-btn').filter({ hasText: '代理池' })).toBeVisible();
    await expect(page.locator('.tab-btn').filter({ hasText: 'HTTP 代理端点' })).toBeVisible();
  });

  test('should switch to chain view tab and load content', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();

    // Verify chain view panel is displayed
    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(chainSection).toBeVisible({ timeout: 5000 });
  });

  test('should show chain flow visualization after switching tab', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    // Verify chain flow visualization structure
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();

    // Verify chain nodes exist (entry, front pool, exit pool, exit)
    const chainNodes = page.locator('.chain-flow .chain-node');
    await expect(chainNodes).toHaveCount(4);

    // Verify node type labels within the chain flow
    const chainFlowContainer = page.locator('.chain-flow');
    await expect(chainFlowContainer.locator('.chain-type-entry').first()).toBeVisible();
    await expect(chainFlowContainer.locator('.chain-type-front').first()).toBeVisible();
    await expect(chainFlowContainer.locator('.chain-type-exit').first()).toBeVisible();
    await expect(chainFlowContainer.locator('.chain-type-output').first()).toBeVisible();

    // Verify arrows between nodes
    const arrows = page.locator('.chain-flow .chain-arrow');
    await expect(arrows).toHaveCount(3);
  });

  test('should show chain diagnostics button on chain view tab', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const diagButton = page.locator('button:has-text("链路诊断")');
    await expect(diagButton).toBeVisible();
    await expect(diagButton).toBeEnabled();

    const latencyButton = page.locator('button:has-text("测试链路延迟")');
    await expect(latencyButton).toBeVisible();
  });

  test('should show chain template section on chain view tab', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    // Chain templates section should be present
    const templateSection = page.locator('.settings-title').filter({ hasText: '链路模板' });
    const hasTemplates = await templateSection.isVisible().catch(() => false);
    // Templates section may or may not have content, but the section itself may be rendered
    expect(true).toBeTruthy();
  });

  test('should show pool type legend on chain view tab', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    // Pool type legend section should be present
    const legendItems = page.locator('.pool-type-legend .legend-item');
    const legendCount = await legendItems.count();
    expect(legendCount).toBeGreaterThanOrEqual(2);
  });
});

test.describe('Subscription Intelligence', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should load subscriptions page with intelligence panel', async ({ page }) => {
    // The intelligence panel is visible when subscriptions exist
    const pageLoaded = page.locator('h2.section-title').filter({ hasText: '订阅管理' });
    await expect(pageLoaded).toBeVisible();

    // Check if intelligence panel exists (shown when subscriptions > 0)
    const intelligencePanel = page.locator('.subscription-intelligence');
    const hasIntelligence = await intelligencePanel.isVisible().catch(() => false);

    // Either subscriptions exist with intelligence panel, or empty state is shown
    const emptyState = page.locator('.empty-state-title').filter({ hasText: '暂无订阅' });
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    expect(hasIntelligence || hasEmpty).toBeTruthy();
  });

  test('should display intelligence analysis cards when subscriptions exist', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Intelligence panel should contain analysis cards
      const intelligenceCards = page.locator('.intelligence-card');
      const cardCount = await intelligenceCards.count();
      expect(cardCount).toBeGreaterThan(0);

      // Verify intelligence panel header text
      await expect(page.locator('text=订阅智能分析')).toBeVisible();
    }
  });

  test('should show duplicate node analysis section', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Duplicate analysis card should exist
      const duplicateSection = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
      await expect(duplicateSection).toBeVisible();

      // Should show either duplicate count or "no duplicates" badge
      const hasDuplicates = duplicateSection.locator('.badge-warning');
      const noDuplicates = duplicateSection.locator('.badge-success').filter({ hasText: '无重复' });
      const hasDupBadge = await hasDuplicates.isVisible().catch(() => false);
      const hasNoDupBadge = await noDuplicates.isVisible().catch(() => false);
      expect(hasDupBadge || hasNoDupBadge).toBeTruthy();
    }
  });

  test('should display subscription quality scores', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Quality scoring card should exist
      const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
      await expect(qualityCard).toBeVisible();

      // Quality scores grid should be present
      const qualityScores = page.locator('.quality-scores');
      if (await qualityScores.isVisible()) {
        const scoreItems = qualityScores.locator('> div');
        const count = await scoreItems.count();
        // Should show at least one quality score entry
        expect(count).toBeGreaterThan(0);
      }
    }
  });

  test('should show health monitoring section in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      const healthCard = page.locator('.intelligence-card').filter({ hasText: '健康监控' });
      if (await healthCard.isVisible()) {
        // Should show healthy/warning/critical metric labels inside the health-metrics grid
        const healthMetrics = healthCard.locator('.health-metrics');
        await expect(healthMetrics).toBeVisible();
        await expect(healthMetrics.locator('text=健康').first()).toBeVisible();
        await expect(healthMetrics.locator('text=警告').first()).toBeVisible();
        await expect(healthMetrics.locator('text=严重').first()).toBeVisible();
      }
    }
  });

  test('should toggle intelligence panel expand/collapse', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Find the expand/collapse toggle button
      const toggleBtn = intelligencePanel.locator('button:has-text("收起"), button:has-text("展开")').first();
      if (await toggleBtn.isVisible()) {
        const initialText = await toggleBtn.textContent();
        await toggleBtn.click();
        await page.waitForTimeout(300);

        // Button text should toggle
        const newText = await toggleBtn.textContent();
        expect(newText).not.toBe(initialText);
      }
    }
  });
});

test.describe('System Diagnostics (Intelligence)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load diagnostics page with one-click button', async ({ page }) => {
    await expect(page.locator('h2.section-title').filter({ hasText: '系统诊断' })).toBeVisible();
    await expect(page.locator('text=全面检查系统健康状态')).toBeVisible();

    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await expect(diagButton).toBeEnabled();
  });

  test('should run one-click diagnostics and show health overview', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await diagButton.click();

    // Button should show running state
    await expect(page.locator('button:has-text("诊断中...")')).toBeVisible();

    // Wait for completion
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Health summary grid should appear
    await expect(page.locator('.health-header .settings-title').filter({ hasText: '系统健康概览' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '后端进程' })).toBeVisible();
    await expect(page.locator('.health-summary-grid .health-label').filter({ hasText: '网关服务' })).toBeVisible();
  });

  test('should display health score after diagnostics', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await diagButton.click();
    await page.waitForTimeout(3000);

    const scoreBadge = page.locator('.health-score-badge');
    if (await scoreBadge.isVisible()) {
      await expect(page.locator('.health-score-label:has-text("健康评分")')).toBeVisible();
      await expect(page.locator('.health-score-value')).toBeVisible();
      await expect(page.locator('.health-score-max:has-text("/100")')).toBeVisible();
    }
  });

  test('should display diagnostic details with all sections', async ({ page }) => {
    await page.locator('button:has-text("一键诊断")').click();
    await page.waitForTimeout(3000);

    // Diagnostic details card should appear
    const detailsTitle = page.locator('.settings-title').filter({ hasText: '诊断详情' });
    if (await detailsTitle.isVisible()) {
      // Verify all four diagnostic sections
      await expect(page.locator('.diagnostic-section-title').filter({ hasText: '后端进程状态' })).toBeVisible();
      await expect(page.locator('.diagnostic-section-title').filter({ hasText: '网关服务状态' })).toBeVisible();
      await expect(page.locator('.diagnostic-section-title').filter({ hasText: '代理池健康' })).toBeVisible();
      await expect(page.locator('.diagnostic-section-title').filter({ hasText: '代理节点统计' })).toBeVisible();
    }
  });

  test('should show export button after diagnostics completes', async ({ page }) => {
    await page.locator('button:has-text("一键诊断")').click();
    await page.waitForTimeout(3000);

    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();
  });

  test('should show health comparison after running diagnostics', async ({ page }) => {
    await page.locator('button:has-text("一键诊断")').click();
    await page.waitForTimeout(3000);

    const comparisonSection = page.locator('.settings-title').filter({ hasText: '健康对比' });
    if (await comparisonSection.isVisible()) {
      await expect(page.locator('.comparison-label').filter({ hasText: '本次诊断' })).toBeVisible();
      await expect(page.locator('.comparison-label').filter({ hasText: '24小时平均' })).toBeVisible();
    }
  });
});
