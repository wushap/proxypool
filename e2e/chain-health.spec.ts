import { test, expect } from '@playwright/test';

test.describe('Chain Health (Proxy Pools Page)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should have chain view tab visible', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainViewTab).toBeVisible();
  });

  test('should load content after clicking chain view tab', async ({ page }) => {
    const chainViewTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await chainViewTab.click();

    await page.waitForLoadState('networkidle');

    // Chain view section or chain flow should become visible
    const chainSection = page.locator('.section-divider').filter({ hasText: '链路可视化' });
    const chainFlow = page.locator('.chain-flow');

    const hasSection = await chainSection.isVisible().catch(() => false);
    const hasFlow = await chainFlow.isVisible().catch(() => false);
    expect(hasSection || hasFlow).toBeTruthy();
  });

  test('should display chain flow visualization', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainFlow = page.locator('.chain-flow');
    await expect(chainFlow).toBeVisible();
  });

  test('should have chain node elements', async ({ page }) => {
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.locator('.section-divider').filter({ hasText: '链路可视化' }).waitFor({ state: 'visible', timeout: 5000 });

    const chainNodes = page.locator('.chain-flow .chain-node');
    const nodeCount = await chainNodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2);
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

  test('should have intelligence panel on subscriptions page', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    const emptyState = page.locator('.empty-state-title').filter({ hasText: '暂无订阅' });

    const hasIntelligence = await intelligencePanel.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);

    // Either intelligence panel is shown (subscriptions exist) or empty state
    expect(hasIntelligence || hasEmpty).toBeTruthy();
  });

  test('should show analysis cards in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      const intelligenceCards = page.locator('.intelligence-card');
      const cardCount = await intelligenceCards.count();
      expect(cardCount).toBeGreaterThan(0);
    }
  });

  test('should show duplicate node analysis in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      const duplicateCard = page.locator('.intelligence-card').filter({ hasText: '重复节点分析' });
      await expect(duplicateCard).toBeVisible();

      // Should show a badge indicating duplicate status
      const warningBadge = duplicateCard.locator('.badge-warning');
      const successBadge = duplicateCard.locator('.badge-success').filter({ hasText: '无重复' });
      const hasWarning = await warningBadge.isVisible().catch(() => false);
      const hasSuccess = await successBadge.isVisible().catch(() => false);
      expect(hasWarning || hasSuccess).toBeTruthy();
    }
  });

  test('should show quality scores in intelligence panel', async ({ page }) => {
    const intelligencePanel = page.locator('.subscription-intelligence');
    if (await intelligencePanel.isVisible().catch(() => false)) {
      const qualityCard = page.locator('.intelligence-card').filter({ hasText: '订阅质量评分' });
      await expect(qualityCard).toBeVisible();
    }
  });
});

test.describe('System Diagnostics Export', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '系统诊断' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should have export button on diagnostics page', async ({ page }) => {
    const exportButton = page.locator('button:has-text("导出"), button:has-text("导出报告")').first();
    await expect(exportButton).toBeVisible();
  });

  test('should enable export button after running diagnostics', async ({ page }) => {
    const diagButton = page.locator('button:has-text("一键诊断")');
    await expect(diagButton).toBeVisible();
    await diagButton.click();

    // Wait for diagnostics to complete
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    const exportButton = page.locator('button:has-text("导出报告")');
    if (await exportButton.isVisible()) {
      await expect(exportButton).toBeEnabled();
    }
  });
});
