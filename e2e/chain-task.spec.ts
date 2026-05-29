import { test, expect } from '@playwright/test';

test.describe('Chain Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxy pools page
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display chain view tab and be clickable', async ({ page }) => {
    const chainTab = page.locator('.tab-btn').filter({ hasText: '链路视图' });
    await expect(chainTab).toBeVisible();
    await chainTab.click();

    // Verify the chain view panel becomes active
    const chainPanel = page.locator('.tab-panel').filter({ has: page.locator('.section-divider:has-text("链路可视化")') });
    await expect(chainPanel).toBeVisible({ timeout: 5000 });
  });

  test('should load chain status section', async ({ page }) => {
    // Switch to chain view tab
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-divider:has-text("链路可视化")').waitFor({ state: 'visible', timeout: 10000 });

    // Verify chain visualization elements exist (entry, front pool, exit pool nodes)
    const chainNodes = page.locator('.chain-node');
    const count = await chainNodes.count();
    // At minimum, the entry node should exist
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('should display chain health information', async ({ page }) => {
    // Switch to chain view tab
    await page.locator('.tab-btn').filter({ hasText: '链路视图' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-divider:has-text("链路可视化")').waitFor({ state: 'visible', timeout: 10000 });

    // Chain health score card may or may not be visible (depends on chain configuration)
    const healthScoreCard = page.locator('.chain-health-score-card');
    const hasHealthScore = await healthScoreCard.isVisible().catch(() => false);

    // Chain flow visualization should always be present
    const chainFlow = page.locator('.chain-flow');
    const hasChainFlow = await chainFlow.isVisible().catch(() => false);

    // At least the chain flow or health score should be visible
    expect(hasHealthScore || hasChainFlow).toBeTruthy();
  });
});

test.describe('Task Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to tasks page
    await page.locator('.el-menu-item').filter({ hasText: '任务中心' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load task page with task operations section', async ({ page }) => {
    // Wait for page content to load
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    // Verify task operations header exists
    const taskOpsHeader = page.locator('.section-title:has-text("任务操作")');
    await expect(taskOpsHeader).toBeVisible({ timeout: 10000 });
  });

  test('should show task list with empty state or existing tasks', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    // Task list card should exist
    const taskListCard = page.locator('.task-list-card');
    const hasTaskListCard = await taskListCard.isVisible().catch(() => false);

    // Empty state or task items should be visible
    const emptyState = page.locator('.empty-state-title:has-text("暂无任务")');
    const taskItem = page.locator('.task-item').first();
    const taskList = page.locator('.task-list');

    const hasEmpty = await emptyState.isVisible().catch(() => false);
    const hasTasks = await taskItem.isVisible().catch(() => false);

    expect(hasTaskListCard || hasEmpty || hasTasks).toBeTruthy();
  });

  test('should display import node file button', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    const importBtn = page.locator('button:has-text("导入节点文件")');
    await expect(importBtn).toBeVisible({ timeout: 10000 });
  });

  test('should display immediate test button', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    const testBtn = page.locator('button:has-text("立即测速")');
    await expect(testBtn).toBeVisible({ timeout: 10000 });
  });

  test('should display task configuration section', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    // Look for the auto task configuration card
    const autoTaskCard = page.locator('.card').filter({ hasText: '自动任务' });
    const hasAutoTask = await autoTaskCard.isVisible().catch(() => false);

    // Or the test fallback / test filter settings
    const testFallbackCard = page.locator('.card').filter({ hasText: '测速回退配置' });
    const hasTestFallback = await testFallbackCard.isVisible().catch(() => false);

    expect(hasAutoTask || hasTestFallback).toBeTruthy();
  });

  test('should display detection strategy section', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    const detectionStrategy = page.locator('.card').filter({ hasText: '检测策略' });
    await expect(detectionStrategy).toBeVisible({ timeout: 10000 });

    // Verify preset strategy select exists
    const presetSelect = detectionStrategy.locator('.el-select');
    const hasPresetSelect = await presetSelect.isVisible().catch(() => false);

    // Verify timeout input exists
    const timeoutInput = detectionStrategy.locator('input[type="number"]');
    const hasTimeoutInput = await timeoutInput.isVisible().catch(() => false);

    expect(hasPresetSelect || hasTimeoutInput).toBeTruthy();
  });
});

test.describe('Published Subscriptions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to published subscriptions page
    await page.locator('.el-menu-item').filter({ hasText: '订阅发布' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load published subscriptions page', async ({ page }) => {
    // Wait for page content to load
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    const title = page.locator('h2.section-title:has-text("订阅发布管理")');
    await expect(title).toBeVisible({ timeout: 10000 });
  });

  test('should display create form with all required fields', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    // Name input
    const nameInput = page.locator('input[placeholder="发布订阅名称"]');
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    // Format selector
    const formatSelect = page.locator('select.select').filter({ hasText: '原始链接' });
    await expect(formatSelect).toBeVisible();

    // Create button
    const createBtn = page.locator('button:has-text("创建")');
    const hasCreateBtn = await createBtn.isVisible().catch(() => false);
    expect(hasCreateBtn).toBeTruthy();
  });

  test('should display filter options for availability, type, ChatGPT, and IP purity', async ({ page }) => {
    await page.locator('.page-container, .card').first().waitFor({ timeout: 10000 });

    // Connectivity filter section
    const availabilityFilter = page.locator('.filter-group-title:has-text("连通性筛选")');
    await expect(availabilityFilter).toBeVisible({ timeout: 10000 });

    // Direct connect status filter
    const directStatus = page.locator('label.form-label:has-text("直连状态")');
    await expect(directStatus).toBeVisible();

    // Link type filter
    const linkType = page.locator('label.form-label:has-text("链路类型")');
    await expect(linkType).toBeVisible();

    // Service unlock filter section
    const unlockFilter = page.locator('.filter-group-title:has-text("服务解锁筛选")');
    await expect(unlockFilter).toBeVisible();

    // ChatGPT unlock filter
    const chatgptFilter = page.locator('label.form-label:has-text("ChatGPT 解锁")');
    await expect(chatgptFilter).toBeVisible();

    // IP purity filter
    const ipPurityFilter = page.locator('label.form-label:has-text("IP 纯净度")');
    await expect(ipPurityFilter).toBeVisible();
  });
});
