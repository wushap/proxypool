import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 35) ──

test.describe('Chain Routing (Round 35)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
  });

  test('dashboard has sidebar with term explanations', async ({ page }) => {
    const sidebarHelp = page.locator('.sidebar-help').first();
    await expect(sidebarHelp).toBeVisible({ timeout: 10000 });

    // Verify the help title
    const helpTitle = sidebarHelp.locator('.sidebar-help-title');
    await expect(helpTitle).toBeVisible();
    const titleText = await helpTitle.textContent();
    expect(titleText).toContain('术语说明');

    // Verify key terminology items exist
    const helpItems = sidebarHelp.locator('.sidebar-help-item');
    const count = await helpItems.count();
    expect(count).toBeGreaterThanOrEqual(5);

    const itemTexts = await helpItems.allTextContents();
    expect(itemTexts).toContain('前置代理池');
    expect(itemTexts).toContain('落地代理池');
    expect(itemTexts).toContain('会话粘性');
    expect(itemTexts).toContain('熔断');
    expect(itemTexts).toContain('链式路由');
  });

  test('dashboard has system status overview', async ({ page }) => {
    const sidebarFooter = page.locator('.sidebar-footer').first();
    await expect(sidebarFooter).toBeVisible({ timeout: 10000 });

    // Verify it has the system status region label
    const regionLabel = await sidebarFooter.getAttribute('aria-label');
    expect(regionLabel).toBe('系统状态概览');

    // Verify sidebar stat items exist with key labels
    const statLabels = sidebarFooter.locator('.sidebar-stat-label');
    const labels = await statLabels.allTextContents();
    expect(labels).toContain('节点');
    expect(labels).toContain('可用');
    expect(labels).toContain('代理池');
    expect(labels).toContain('后端');
    expect(labels).toContain('连接');

    // Verify stat values are present
    const statValues = sidebarFooter.locator('.sidebar-stat-value');
    const valueCount = await statValues.count();
    expect(valueCount).toBeGreaterThanOrEqual(5);
  });

  test('dashboard has notification bell', async ({ page }) => {
    const bellWrapper = page.locator('.notification-bell-wrapper').first();
    await expect(bellWrapper).toBeVisible({ timeout: 10000 });

    // The bell icon itself should be present
    const bell = bellWrapper.locator('.notification-bell');
    await expect(bell).toBeVisible();
    const bellText = await bell.textContent();
    expect(bellText).toContain('🔔');

    // Click the bell to toggle notification dropdown
    await bellWrapper.click();
    await page.waitForLoadState('domcontentloaded');

    // The notification dropdown should appear
    const dropdown = page.locator('.notification-dropdown').first();
    await expect(dropdown).toBeVisible({ timeout: 5000 });

    // Verify dropdown header has "通知" title
    const dropdownTitle = dropdown.locator('.notification-dropdown-title');
    await expect(dropdownTitle).toBeVisible();
    const titleText = await dropdownTitle.textContent();
    expect(titleText).toContain('通知');
  });

  test('dashboard has dark mode toggle', async ({ page }) => {
    const toggleBtn = page.locator('.sidebar-toggle').first();
    await expect(toggleBtn).toBeVisible({ timeout: 10000 });

    // Verify it has a meaningful aria-label or title
    const ariaLabel = await toggleBtn.getAttribute('aria-label');
    const title = await toggleBtn.getAttribute('title');
    expect(ariaLabel || title).toBeTruthy();

    // It should contain a sun or moon icon character
    const btnText = await toggleBtn.textContent();
    const hasSunOrMoon = btnText.includes('☀') || btnText.includes('☾');
    expect(hasSunOrMoon).toBeTruthy();
  });

  test('dashboard has wizard button', async ({ page }) => {
    const wizardBtn = page.locator('.sidebar-wizard-btn').first();
    await expect(wizardBtn).toBeVisible({ timeout: 10000 });

    // Verify it has proper accessibility attributes
    const title = await wizardBtn.getAttribute('title');
    expect(title).toBe('配置向导');

    const ariaLabel = await wizardBtn.getAttribute('aria-label');
    expect(ariaLabel).toBe('打开配置向导');

    // Verify the button text shows "向导"
    const wizardText = wizardBtn.locator('.wizard-btn-text');
    await expect(wizardText).toBeVisible();
    const text = await wizardText.textContent();
    expect(text).toContain('向导');
  });
});

// ── Subscription Intelligence (Round 35) ──

test.describe('Subscription Intelligence (Round 35)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '入站端口');
  });

  test('inbound ports page has create button', async ({ page }) => {
    const createBtn = page.locator('button').filter({ hasText: '创建端口' }).first();
    await expect(createBtn).toBeVisible({ timeout: 10000 });

    // Verify it has the correct aria-label
    const ariaLabel = await createBtn.getAttribute('aria-label');
    expect(ariaLabel).toBe('创建新的入站端口');

    // Verify it has the primary button styling
    const hasPrimary = await createBtn.evaluate(el =>
      el.classList.contains('btn-primary')
    );
    expect(hasPrimary).toBeTruthy();
  });

  test('inbound ports page has table or empty state', async ({ page }) => {
    // Either a data table (when ports exist) or an empty state should be visible
    const dataTable = page.locator('.data-table').first();
    const tableVisible = await dataTable.isVisible({ timeout: 10000 }).catch(() => false);

    if (tableVisible) {
      // Verify table has expected column headers
      const headers = dataTable.locator('th');
      const headerTexts = await headers.allTextContents();
      const joinedText = headerTexts.join(' ');
      expect(joinedText).toContain('名称');
      expect(joinedText).toContain('跳点链路');
    } else {
      // Empty state should be visible
      const emptyState = page.locator('.empty-state').first();
      await expect(emptyState).toBeVisible({ timeout: 5000 });

      // Empty state should mention creating a port
      const emptyText = await emptyState.textContent();
      expect(emptyText).toContain('入站端口');
    }
  });

  test('inbound ports page has refresh button', async ({ page }) => {
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible({ timeout: 10000 });

    // Verify it has the correct aria-label
    const ariaLabel = await refreshBtn.getAttribute('aria-label');
    expect(ariaLabel).toBe('刷新入站端口列表');

    // Verify it has secondary button styling
    const hasSecondary = await refreshBtn.evaluate(el =>
      el.classList.contains('btn-secondary')
    );
    expect(hasSecondary).toBeTruthy();
  });
});

// ── System Diagnostics Export (Round 35) ──

test.describe('System Diagnostics Export (Round 35)', () => {
  test.beforeEach(async ({ page }) => {
    await navigateTo(page, '系统诊断');
  });

  test('diagnostics page has health overview', async ({ page }) => {
    // The system health overview card should be present
    const healthCard = page.locator('.card').filter({ hasText: '系统健康概览' }).first();
    await expect(healthCard).toBeVisible({ timeout: 10000 });

    // Verify the health summary grid exists
    const healthGrid = healthCard.locator('.health-summary-grid').first();
    await expect(healthGrid).toBeVisible();

    // Verify key health items are present
    const healthItems = healthGrid.locator('.health-item');
    const count = await healthItems.count();
    expect(count).toBeGreaterThanOrEqual(4);

    const healthLabels = healthGrid.locator('.health-label');
    const labels = await healthLabels.allTextContents();
    expect(labels).toContain('后端进程');
    expect(labels).toContain('网关服务');
    expect(labels).toContain('代理池');
    expect(labels).toContain('代理节点');
  });

  test('diagnostics page has diagnostic button', async ({ page }) => {
    const diagBtn = page.locator('button').filter({ hasText: '一键诊断' }).first();
    await expect(diagBtn).toBeVisible({ timeout: 10000 });

    // Verify it has primary button styling
    const hasPrimary = await diagBtn.evaluate(el =>
      el.classList.contains('btn-primary')
    );
    expect(hasPrimary).toBeTruthy();

    // Also verify the export report button exists (should be disabled initially)
    const exportBtn = page.locator('button').filter({ hasText: '导出报告' }).first();
    await expect(exportBtn).toBeVisible();
    const isDisabled = await exportBtn.isDisabled();
    expect(isDisabled).toBeTruthy();
  });
});
