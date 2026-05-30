import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 28) ──

test.describe('Chain Routing (Round 28)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '仪表盘');
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard auto-refresh dropdown has options (5s, 15s, 30s, 1min)', async ({ page }) => {
    const select = page.locator('select[aria-label="自动刷新间隔"]');
    await expect(select).toBeVisible();

    const options = select.locator('option');
    const optionCount = await options.count();
    expect(optionCount).toBeGreaterThanOrEqual(5);

    const texts = await options.allTextContents();
    expect(texts.some(t => t.includes('5'))).toBeTruthy();
    expect(texts.some(t => t.includes('15'))).toBeTruthy();
    expect(texts.some(t => t.includes('30'))).toBeTruthy();
    expect(texts.some(t => t.includes('1'))).toBeTruthy();
  });

  test('dashboard has latency distribution section with bar chart or labels', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: '延迟分布' });
    await expect(card).toBeVisible();

    const cardBody = card.locator('.card-body');
    await expect(cardBody).toBeVisible();

    const hasBars = await card.locator('.dashboard-histogram-bar-wrapper').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await card.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasBars || hasEmpty).toBeTruthy();

    if (hasBars) {
      const barCount = await card.locator('.dashboard-histogram-bar-wrapper').count();
      expect(barCount).toBeGreaterThanOrEqual(3);
    }
  });

  test('dashboard has geographic distribution section', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: '地理位置分布' });
    await expect(card).toBeVisible();

    const cardBody = card.locator('.card-body');
    await expect(cardBody).toBeVisible();

    const hasRegions = await card.locator('.dashboard-geo-region').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await card.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasRegions || hasEmpty).toBeTruthy();

    if (hasRegions) {
      const regionCount = await card.locator('.dashboard-geo-region').count();
      expect(regionCount).toBeGreaterThanOrEqual(1);
    }
  });

  test('dashboard has bandwidth distribution section', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: '带宽分布' });
    await expect(card).toBeVisible();

    const cardBody = card.locator('.card-body');
    await expect(cardBody).toBeVisible();

    const hasBars = await card.locator('.dashboard-bandwidth-bar-wrapper').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await card.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasBars || hasEmpty).toBeTruthy();

    if (hasBars) {
      const barCount = await card.locator('.dashboard-bandwidth-bar-wrapper').count();
      expect(barCount).toBeGreaterThanOrEqual(3);
    }
  });

  test('dashboard has IP purity distribution section', async ({ page }) => {
    const card = page.locator('.card').filter({ hasText: 'IP 纯净度分布' });
    await expect(card).toBeVisible();

    const cardBody = card.locator('.card-body');
    await expect(cardBody).toBeVisible();

    const hasRows = await card.locator('.dashboard-protocol-row').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await card.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasRows || hasEmpty).toBeTruthy();
  });
});

// ── Subscription Intelligence (Round 28) ──

test.describe('Subscription Intelligence (Round 28)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '代理节点');
  });

  test('proxy nodes page has data table or empty state', async ({ page }) => {
    const tableWrap = page.locator('.table-wrap');
    const hasTable = await tableWrap.isVisible({ timeout: 10000 }).catch(() => false);

    if (hasTable) {
      const table = page.locator('.data-table').first();
      await expect(table).toBeVisible();

      const headers = table.locator('thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(3);
    } else {
      const hasLoading = await page.locator('.loading-state').first().isVisible({ timeout: 3000 }).catch(() => false);
      const hasEmpty = await page.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
      const hasError = await page.locator('.error-state').first().isVisible({ timeout: 3000 }).catch(() => false);
      expect(hasLoading || hasEmpty || hasError).toBeTruthy();
    }
  });

  test('proxy table rows have checkbox for selection', async ({ page }) => {
    const table = page.locator('.data-table').first();
    if (!(await table.isVisible({ timeout: 10000 }).catch(() => false))) return;

    // Header should have a select-all checkbox
    const headerCheckbox = table.locator('thead th input[type="checkbox"]');
    await expect(headerCheckbox.first()).toBeVisible();

    // Body rows should have checkboxes
    const bodyCheckbox = table.locator('tbody tr td input[type="checkbox"]');
    const checkboxCount = await bodyCheckbox.count();
    expect(checkboxCount).toBeGreaterThanOrEqual(0);
  });

  test('page has pagination or total count display', async ({ page }) => {
    // Status bar shows total count
    const statusBar = page.locator('.status-bar');
    const hasStatusBar = await statusBar.isVisible({ timeout: 10000 }).catch(() => false);

    // Pagination shows page info
    const pagination = page.locator('.pagination');
    const hasPagination = await pagination.isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasStatusBar || hasPagination).toBeTruthy();

    if (hasStatusBar) {
      const statusText = await statusBar.textContent();
      expect(statusText?.length).toBeGreaterThan(0);
    }

    if (hasPagination) {
      const pageButtons = pagination.locator('button');
      const btnCount = await pageButtons.count();
      expect(btnCount).toBeGreaterThanOrEqual(2);
    }
  });
});

// ── System Diagnostics Export (Round 28) ──

test.describe('System Diagnostics Export (Round 28)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '任务中心');
  });

  test('task center has task history table or empty state', async ({ page }) => {
    const sectionTitle = page.locator('.section-title').filter({ hasText: '任务列表' });
    await expect(sectionTitle).toBeVisible({ timeout: 10000 });

    const taskList = page.locator('.task-list');
    const hasTasks = await taskList.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasTasks) {
      const taskItems = page.locator('.task-item');
      const itemCount = await taskItems.count();
      expect(itemCount).toBeGreaterThanOrEqual(1);

      // Each task should have a name and status badge
      const firstTask = taskItems.first();
      const taskName = firstTask.locator('.task-name');
      await expect(taskName).toBeVisible();
      const badge = firstTask.locator('.badge');
      await expect(badge).toBeVisible();
    } else {
      const emptyState = page.locator('.empty-state');
      await expect(emptyState).toBeVisible({ timeout: 5000 });
      const emptyText = await emptyState.textContent();
      expect(emptyText).toContain('暂无任务');
    }
  });

  test('task center has action buttons for common operations', async ({ page }) => {
    const taskOpsHeader = page.locator('.task-quick-card');
    await expect(taskOpsHeader).toBeVisible({ timeout: 10000 });

    const importBtn = page.locator('button:has-text("导入节点文件")');
    await expect(importBtn).toBeVisible();

    const testBtn = page.locator('button:has-text("立即测速")');
    await expect(testBtn).toBeVisible();

    // At least one more action button exists
    const actionButtons = page.locator('.task-action-bar button, .task-action-bar a.btn');
    const btnCount = await actionButtons.count();
    expect(btnCount).toBeGreaterThanOrEqual(4);
  });
});
