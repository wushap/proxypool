import { test, expect } from '@playwright/test';

test.describe('Chain Health Check (Round 26)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    // Wait for data to finish loading (loading spinner disappears, stat grid appears)
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard page loads with overview title visible', async ({ page }) => {
    const headerTitle = page.locator('.header-title');
    await expect(headerTitle).toBeVisible();
    await expect(headerTitle).toHaveText('仪表盘');

    const headerSubtitle = page.locator('.header-subtitle');
    await expect(headerSubtitle).toBeVisible();
    await expect(headerSubtitle).toHaveText('代理池运行状态概览');

    const headerKicker = page.locator('.header-kicker');
    await expect(headerKicker).toBeVisible();
    await expect(headerKicker).toHaveText('OVERVIEW');
  });

  test('dashboard has stat cards showing node count and availability', async ({ page }) => {
    // Dashboard has stat cards in a grid layout
    const statCards = page.locator('.stat-card');
    const cardCount = await statCards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);

    // Check that key stat labels are present
    const labels = ['节点总数', '可用节点', '可用率', '平均延迟'];
    for (const label of labels) {
      const card = statCards.filter({ hasText: label });
      await expect(card.first()).toBeVisible();
    }
  });

  test('dashboard has protocol distribution section', async ({ page }) => {
    // The protocol distribution card should exist
    const protocolCard = page.locator('.card').filter({ hasText: '协议分布' });
    await expect(protocolCard).toBeVisible();

    const cardBody = protocolCard.locator('.card-body');
    await expect(cardBody).toBeVisible();

    // Should either have a donut chart or an empty state
    const hasData = await page.locator('.dashboard-donut-wrapper').isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await protocolCard.locator('.empty-state').isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasData || hasEmpty).toBeTruthy();
  });

  test('dashboard has system status section with backend status', async ({ page }) => {
    const statusCard = page.locator('.card').filter({ hasText: '系统状态' });
    await expect(statusCard).toBeVisible();

    const statusList = statusCard.locator('.dashboard-status-list');
    await expect(statusList).toBeVisible();

    // Backend engine status row
    const backendRow = statusCard.locator('.dashboard-status-row').filter({ hasText: '后端引擎' });
    await expect(backendRow).toBeVisible();

    // Should have a badge showing running or stopped
    const backendBadge = backendRow.locator('.badge');
    await expect(backendBadge).toBeVisible();
    const badgeText = await backendBadge.textContent();
    expect(badgeText).toMatch(/运行中|已停止/);

    // Gateway service row should also exist
    const gatewayRow = statusCard.locator('.dashboard-status-row').filter({ hasText: '网关服务' });
    await expect(gatewayRow).toBeVisible();
  });

  test('dashboard has real-time monitoring section', async ({ page }) => {
    // Check for the auto-refresh select (real-time monitoring control)
    const refreshSelect = page.locator('select[aria-label="自动刷新间隔"]');
    await expect(refreshSelect).toBeVisible();

    // Verify options exist
    const options = refreshSelect.locator('option');
    const optionCount = await options.count();
    expect(optionCount).toBeGreaterThanOrEqual(4);

    // Check for the refresh button
    const refreshBtn = page.locator('button[aria-label="刷新仪表盘数据"]');
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();

    // Verify recent tasks section exists as part of monitoring
    const recentTasksCard = page.locator('.card').filter({ hasText: '最近任务' });
    await expect(recentTasksCard).toBeVisible();
  });
});

test.describe('Batch Operations (Round 26)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '任务中心' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '任务中心' }).click();
    await page.locator('.task-dashboard').waitFor({ state: 'visible', timeout: 15000 });
  });

  test('task center page loads with page title', async ({ page }) => {
    // Task operations section
    const taskOpsTitle = page.locator('.section-title').filter({ hasText: '任务操作' });
    await expect(taskOpsTitle).toBeVisible();

    // Form hint text
    const formHint = page.locator('.form-hint').filter({ hasText: '常用任务集中启动' });
    await expect(formHint).toBeVisible();

    // Status badge (idle or running)
    const statusBadge = page.locator('.task-quick-card .badge');
    await expect(statusBadge).toBeVisible();
    const badgeText = await statusBadge.textContent();
    expect(badgeText).toMatch(/空闲|有任务运行/);
  });

  test('task history table or empty state is visible', async ({ page }) => {
    const taskListCard = page.locator('.task-list-card');
    await expect(taskListCard).toBeVisible();

    const taskListTitle = taskListCard.locator('.section-title').filter({ hasText: '任务列表' });
    await expect(taskListTitle).toBeVisible();

    // Either tasks exist or empty state is shown
    const hasTasks = await page.locator('.task-item').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await page.locator('.empty-state:has-text("暂无任务")').isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasTasks || hasEmpty).toBeTruthy();

    // Refresh button should be present
    const refreshBtn = taskListCard.locator('button').filter({ hasText: '刷新' });
    await expect(refreshBtn).toBeVisible();
  });

  test('task execution button or form is accessible', async ({ page }) => {
    // Common action buttons should be present
    const importBtn = page.locator('button[aria-label="导入本地代理节点文件"]');
    await expect(importBtn).toBeVisible();
    await expect(importBtn).toBeEnabled();

    const testBtn = page.locator('button[aria-label="立即测试所有节点"]');
    await expect(testBtn).toBeVisible();
    await expect(testBtn).toBeEnabled();

    // Health check button
    const healthBtn = page.locator('button[aria-label="检查所有代理池的健康状态"]');
    await expect(healthBtn).toBeVisible();
    await expect(healthBtn).toBeEnabled();

    // Action groups should be present
    const actionGroups = page.locator('.action-group');
    const groupCount = await actionGroups.count();
    expect(groupCount).toBeGreaterThanOrEqual(3);
  });
});

test.describe('System Diagnostics Export (Round 26)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).click();
    await page.locator('.page-container').waitFor({ state: 'visible', timeout: 15000 });
  });

  test('docs page loads with documentation content', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '使用指南' });
    await expect(sectionTitle).toBeVisible();

    // Quick start section
    const quickStartTitle = page.locator('.settings-title').filter({ hasText: '快速开始' });
    await expect(quickStartTitle).toBeVisible();

    // Quick start steps
    const steps = page.locator('.quick-start-step');
    const stepCount = await steps.count();
    expect(stepCount).toBe(5);

    // Feature overview section
    const featureTitle = page.locator('.settings-title').filter({ hasText: '功能概览' });
    await expect(featureTitle).toBeVisible();
  });

  test('docs page has navigation or table of contents', async ({ page }) => {
    // Feature grid acts as navigation to other sections
    const featureGrid = page.locator('.feature-grid');
    await expect(featureGrid).toBeVisible();

    const featureItems = featureGrid.locator('.feature-item');
    const itemCount = await featureItems.count();
    expect(itemCount).toBeGreaterThanOrEqual(5);

    // Each feature item should have a name
    const featureNames = page.locator('.feature-name');
    const nameCount = await featureNames.count();
    expect(nameCount).toBeGreaterThanOrEqual(5);

    // API documentation link should exist (use first() because "API 文档" and "打开 API 文档" both match)
    const apiLink = page.locator('a:has-text("API 文档")').first();
    await expect(apiLink).toBeVisible();
    await expect(apiLink).toHaveAttribute('target', '_blank');

    // FAQ section as part of navigation
    const faqTitle = page.locator('.settings-title').filter({ hasText: '常见问题' });
    await expect(faqTitle).toBeVisible();

    const faqItems = page.locator('.faq-item');
    const faqCount = await faqItems.count();
    expect(faqCount).toBeGreaterThanOrEqual(3);
  });
});
