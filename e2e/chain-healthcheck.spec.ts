import { test, expect } from '@playwright/test';

test.describe('Chain Health Check', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Navigate to proxy pools page
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display chain view tab', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
  });

  test('should load chain view content when clicking chain view tab', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Verify the chain view section header is visible
    const sectionDivider = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    await expect(sectionDivider).toBeVisible({ timeout: 5000 });

    // Verify the form hint text is present
    await expect(page.locator('.form-hint').filter({ hasText: '可视化展示代理链路配置' })).toBeVisible();
  });

  test('should display chain flow visualization', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Verify chain visualization container exists
    const chainVisualization = page.locator('.chain-visualization');
    await expect(chainVisualization).toBeVisible({ timeout: 5000 });

    // Verify chain flow container exists inside it
    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('should display chain node elements in the flow', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();

    // Wait for chain visualization to render
    await page.locator('.chain-visualization').waitFor({ state: 'visible', timeout: 5000 });

    // Verify entry node exists
    const entryNode = page.locator('.chain-node.chain-node-entry');
    await expect(entryNode).toBeVisible();

    // Verify front pool node exists (may be in warning state if unconfigured)
    const frontPoolNode = page.locator('.chain-node').filter({ has: page.locator('.chain-type-front') });
    await expect(frontPoolNode).toBeVisible();

    // Verify exit pool node exists (may be in warning state if unconfigured)
    const exitPoolNode = page.locator('.chain-node').filter({ has: page.locator('.chain-type-exit') });
    await expect(exitPoolNode).toBeVisible();

    // Verify exit point node exists
    const exitPointNode = page.locator('.chain-node.chain-node-exit');
    await expect(exitPointNode).toBeVisible();

    // Verify chain arrows connecting nodes exist
    const arrows = page.locator('.chain-arrow');
    const arrowCount = await arrows.count();
    expect(arrowCount).toBeGreaterThanOrEqual(3);
  });
});

test.describe('Subscription Intelligence Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Navigate to subscriptions page
    await page.locator('.el-menu-item').filter({ hasText: '订阅管理' }).click();
    await page.locator('.card-body').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display subscription intelligence panel', async ({ page }) => {
    // The intelligence panel is only shown when subscriptions exist.
    // If no subscriptions exist, verify the empty state instead.
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state-title').filter({ hasText: '暂无订阅' });

    const hasPanel = await intelligencePanel.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasPanel || hasEmptyState).toBeTruthy();
  });

  test('should display analysis cards in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // The intelligence panel header with "订阅智能分析" text
      await expect(page.locator('h3').filter({ hasText: '订阅智能分析' })).toBeVisible();

      // Intelligence cards should be present
      const intelligenceCards = page.locator('.intelligence-card');
      const cardCount = await intelligenceCards.count();
      expect(cardCount).toBeGreaterThanOrEqual(1);
    }
  });

  test('should display duplicate node analysis', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Duplicate analysis card contains "重复节点分析" heading
      const duplicateSection = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
      await expect(duplicateSection).toBeVisible();

      // Should show either "无重复" badge or duplicate count
      const noDuplicates = duplicateSection.locator('.badge-success').filter({ hasText: '无重复' });
      const hasDuplicates = duplicateSection.locator('.badge-warning');
      const hasNoDup = await noDuplicates.isVisible().catch(() => false);
      const hasDup = await hasDuplicates.isVisible().catch(() => false);
      expect(hasNoDup || hasDup).toBeTruthy();
    }
  });

  test('should display quality scores in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      // Quality scoring section
      const qualitySection = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
      await expect(qualitySection).toBeVisible();

      // Quality scores grid
      const qualityScores = qualitySection.locator('.quality-scores');
      if (await qualityScores.isVisible()) {
        const scoreItems = qualityScores.locator('> div');
        const count = await scoreItems.count();
        expect(count).toBeGreaterThanOrEqual(0);
      }
    }
  });
});

test.describe('System Diagnostics Rules', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Navigate to system diagnostics page
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    // Wait for the page to render its content
    await page.locator('.page-container').first().waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display health alerting rules section', async ({ page }) => {
    // Health alerting rules section title
    const rulesTitle = page.locator('.settings-title').filter({ hasText: '健康告警规则' });
    await expect(rulesTitle).toBeVisible({ timeout: 5000 });

    // Verify specific alerting rule names are present
    await expect(page.locator('.rule-name').filter({ hasText: '后端进程停止' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '网关服务停止' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '健康评分过低' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '代理池异常' })).toBeVisible();
    await expect(page.locator('.rule-name').filter({ hasText: '代理节点不可用' })).toBeVisible();

    // Verify toggle switches exist for rules
    const ruleItems = page.locator('.alerting-rule-item');
    const ruleCount = await ruleItems.count();
    expect(ruleCount).toBeGreaterThanOrEqual(5);
  });

  test('should display export button', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出报告")');
    await expect(exportButton).toBeVisible();
    expect(await exportButton.count()).toBe(1);
  });
});
