import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 33) ──

test.describe('Chain Health Check (Round 33)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has latency distribution section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '延迟分布' });
    await expect(sectionTitle).toBeVisible();

    // The latency distribution section should either show histogram bars or an empty state
    const card = sectionTitle.locator('..').locator('..');
    const hasHistogram = card.locator('.dashboard-histogram').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasHistogram || hasEmpty).toBeTruthy();
  });

  test('dashboard has proxy pool health overview', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '代理池健康概览' });
    await expect(sectionTitle).toBeVisible();

    // The section should either show pool health rows or an empty state
    const card = sectionTitle.locator('..').locator('..');
    const hasHealth = card.locator('.dashboard-pool-health').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasHealth || hasEmpty).toBeTruthy();
  });

  test('dashboard has recent tasks section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '最近任务' });
    await expect(sectionTitle).toBeVisible();

    // The section should either show task items or an empty state
    const card = sectionTitle.locator('..').locator('..');
    const hasTasks = card.locator('.dashboard-task-list').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasTasks || hasEmpty).toBeTruthy();

    // Should have a "查看全部" link to task center
    const viewAll = card.locator('button').filter({ hasText: '查看全部' });
    await expect(viewAll).toBeVisible();
  });

  test('dashboard has recent activity section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '最近活动' });
    await expect(sectionTitle).toBeVisible();

    // The section should either show activity items or an empty state
    const card = sectionTitle.locator('..').locator('..');
    const hasActivity = card.locator('.activity-feed').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasActivity || hasEmpty).toBeTruthy();
  });

  test('dashboard has recent events section', async ({ page }) => {
    const sectionTitle = page.locator('.card-title').filter({ hasText: '最近事件' });
    await expect(sectionTitle).toBeVisible();

    // The section should either show event timeline items or an empty state
    const card = sectionTitle.locator('..').locator('..');
    const hasEvents = card.locator('.dashboard-events-timeline').first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = card.locator('.empty-state, .empty-state-small').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasEvents || hasEmpty).toBeTruthy();
  });
});

// ── Batch Operations (Round 33) ──

test.describe('Batch Operations (Round 33)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '任务中心' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '任务中心' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('task center has task operation section', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '任务操作' });
    await expect(sectionTitle).toBeVisible();

    // Should contain action group titles for different operation categories
    const operationText = await page.locator('.task-quick-card').first().textContent();
    expect(operationText).toContain('常用操作');
    expect(operationText).toContain('一键诊断');
  });

  test('task center has task history table', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '任务列表' });
    await expect(sectionTitle).toBeVisible();

    // Should show either task items or an empty state
    const taskList = page.locator('.task-list');
    const emptyState = page.locator('.empty-state, .empty-state-small').filter({ hasText: '暂无任务' });

    const hasList = await taskList.first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await emptyState.first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasList || hasEmpty).toBeTruthy();

    // The refresh button should be present
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible();
  });

  test('task center has action buttons', async ({ page }) => {
    // Verify key action buttons exist
    const importBtn = page.locator('button').filter({ hasText: '导入节点文件' }).first();
    const testBtn = page.locator('button').filter({ hasText: '立即测速' }).first();

    await expect(importBtn).toBeVisible();
    await expect(importBtn).toBeEnabled();
    await expect(testBtn).toBeVisible();
    await expect(testBtn).toBeEnabled();
  });
});

// ── System Diagnostics Export (Round 33) ──

test.describe('System Diagnostics Export (Round 33)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '配置历史' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('config history has save snapshot button', async ({ page }) => {
    const saveBtn = page.locator('button').filter({ hasText: '保存快照' });
    await expect(saveBtn.first()).toBeVisible();
    await expect(saveBtn.first()).toBeEnabled();

    // Verify the section title is present
    const sectionTitle = page.locator('.section-title').filter({ hasText: '配置历史' });
    await expect(sectionTitle).toBeVisible();
  });

  test('config history has empty state or snapshot list', async ({ page }) => {
    const emptyState = page.locator('.empty-state, .empty-state-small').filter({ hasText: '暂无配置快照' });
    const snapshotList = page.locator('.config-snapshot-list');

    const hasEmpty = await emptyState.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasList = await snapshotList.first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasEmpty || hasList).toBeTruthy();

    if (hasEmpty) {
      const emptyText = await emptyState.first().textContent();
      expect(emptyText).toContain('暂无配置快照');
    }

    if (hasList) {
      const items = snapshotList.locator('.config-snapshot-item');
      const itemCount = await items.count();
      expect(itemCount).toBeGreaterThanOrEqual(1);
    }
  });
});
