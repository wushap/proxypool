import { test, expect } from '@playwright/test';

async function navigateTo(page: any, menuText: string) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  // Wait for sidebar menu to be ready
  await page.locator('.el-menu-item').first().waitFor({ state: 'visible', timeout: 15000 });
  // Dismiss any notification popups before clicking
  const notifications = page.locator('.el-notification');
  const closeBtns = notifications.locator('.el-notification__closeBtn');
  const closeCount = await closeBtns.count();
  for (let i = 0; i < closeCount; i++) {
    await closeBtns.nth(i).click({ timeout: 1000 }).catch(() => {});
  }
  await page.locator('.el-menu-item').filter({ hasText: menuText }).click();
  // Wait for the page content to render
  await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
}

// ── Chain Routing (Round 26) ──

test.describe('Chain Routing (Round 26)', () => {
  test('inbound ports page loads with page title visible', async ({ page }) => {
    await navigateTo(page, '入站端口');

    // The page title "入站端口" should be visible
    await expect(
      page.locator('.section-title').filter({ hasText: '入站端口' })
    ).toBeVisible({ timeout: 10000 });

    // Page description hint should also be present
    await expect(
      page.locator('.form-hint').filter({ hasText: '入站端口' })
    ).toBeVisible();
  });

  test('port creation form has required input fields', async ({ page }) => {
    await navigateTo(page, '入站端口');

    // Click the create button to open the wizard
    const createBtn = page.locator('button:has-text("创建端口")');
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    // Wait for the dialog to appear
    const dialog = page.locator('.el-dialog');
    await expect(dialog).toBeVisible({ timeout: 10000 });

    // Dialog title should indicate creation
    await expect(dialog.locator('.el-dialog__title').filter({ hasText: '创建入站端口' })).toBeVisible();

    // Step 1 form should have name input field
    const nameInput = dialog.locator('input').first();
    await expect(nameInput).toBeVisible();

    // Form should have at least 2 inputs (name + listen_host) and a number input for port
    const inputs = dialog.locator('input');
    const inputCount = await inputs.count();
    expect(inputCount).toBeGreaterThanOrEqual(2);

    // Close the dialog
    await dialog.locator('.el-dialog__close').click();
  });

  test('port table shows columns for port number and status', async ({ page }) => {
    await navigateTo(page, '入站端口');

    // If ports exist, the data table should be visible
    const table = page.locator('.data-table');
    if (await table.isVisible().catch(() => false)) {
      // Table should have header columns
      const headers = table.locator('thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(5);

      // Extract header texts to verify key columns
      const headerTexts: string[] = [];
      for (let i = 0; i < headerCount; i++) {
        const text = await headers.nth(i).textContent();
        headerTexts.push(text?.trim() || '');
      }

      // Verify status column exists
      expect(headerTexts).toContain('状态');
      // Verify name column exists
      expect(headerTexts).toContain('名称');
      // Verify operations column exists
      expect(headerTexts).toContain('操作');
    } else {
      // No ports yet - the empty state should be visible
      await expect(page.locator('.empty-state')).toBeVisible();
      // Empty state should have a create button
      await expect(page.locator('.empty-state button:has-text("创建")')).toBeVisible();
    }
  });

  test('clicking create button shows form or action', async ({ page }) => {
    await navigateTo(page, '入站端口');

    // The "创建端口" button should be visible in the section header
    const createBtn = page.locator('button:has-text("创建端口")');
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toBeEnabled();

    // Clicking it should open the wizard dialog
    await createBtn.click();

    // Dialog with create form should appear
    const dialog = page.locator('.el-dialog');
    await expect(dialog).toBeVisible({ timeout: 10000 });

    // Wizard step indicators should be visible (3 steps)
    const steps = dialog.locator('.port-wizard-step');
    const stepCount = await steps.count();
    expect(stepCount).toBe(3);

    // Step labels should be visible
    await expect(dialog.locator('.port-wizard-step-label').filter({ hasText: '基础配置' })).toBeVisible();
    await expect(dialog.locator('.port-wizard-step-label').filter({ hasText: '跳点选择' })).toBeVisible();
    await expect(dialog.locator('.port-wizard-step-label').filter({ hasText: '会话策略' })).toBeVisible();

    // Close the dialog
    await dialog.locator('.el-dialog__close').click();
  });

  test('page has at least one interactive element', async ({ page }) => {
    await navigateTo(page, '入站端口');

    // The page should have at least one button, input, or select
    const buttons = page.locator('.page-container button, .card button');
    const inputs = page.locator('.page-container input, .card input');
    const selects = page.locator('.page-container select, .card select');

    const buttonCount = await buttons.count();
    const inputCount = await inputs.count();
    const selectCount = await selects.count();

    const totalInteractive = buttonCount + inputCount + selectCount;
    expect(totalInteractive).toBeGreaterThanOrEqual(1);

    // Specifically, refresh and create buttons should always exist
    await expect(page.locator('button:has-text("刷新")')).toBeVisible();
    await expect(page.locator('button:has-text("创建端口")')).toBeVisible();
  });
});

// ── Subscription Intelligence (Round 26) ──

test.describe('Subscription Intelligence (Round 26)', () => {
  test('subscription table has column headers', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // Wait for either the table or empty state
    const table = page.locator('.data-table');
    const emptyState = page.locator('.empty-state');
    const hasTable = await table.isVisible({ timeout: 10000 }).catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();

    if (hasTable) {
      // Verify table has column headers
      const headers = table.locator('thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(8);

      // Extract header texts
      const headerTexts: string[] = [];
      for (let i = 0; i < headerCount; i++) {
        const text = await headers.nth(i).textContent();
        headerTexts.push(text?.trim() || '');
      }

      // Verify key column headers exist
      expect(headerTexts).toContain('名称');
      expect(headerTexts).toContain('链接');
      expect(headerTexts).toContain('状态');
      expect(headerTexts).toContain('操作');
    }
  });

  test('refresh button is visible on subscriptions page', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // The section header should have refresh buttons
    // "刷新全部" refreshes all subscriptions
    const refreshAllBtn = page.locator('button:has-text("刷新全部")');
    await expect(refreshAllBtn).toBeVisible({ timeout: 10000 });
    await expect(refreshAllBtn).toBeEnabled();

    // "刷新列表" refreshes the subscription list
    const refreshListBtn = page.locator('button:has-text("刷新列表")');
    await expect(refreshListBtn).toBeVisible();
    await expect(refreshListBtn).toBeEnabled();
  });

  test('add subscription form or button is accessible', async ({ page }) => {
    await navigateTo(page, '订阅管理');

    // The add subscription form row should be visible with inputs
    const nameInput = page.locator('input[placeholder="订阅名称"]');
    const urlInput = page.locator('input[placeholder="订阅链接 URL"]');
    const addBtn = page.locator('button:has-text("添加订阅")').first();

    // All three elements should be visible
    await expect(nameInput).toBeVisible({ timeout: 10000 });
    await expect(urlInput).toBeVisible();
    await expect(addBtn).toBeVisible();
    await expect(addBtn).toBeEnabled();
  });
});

// ── System Diagnostics Export (Round 26) ──

test.describe('System Diagnostics Export (Round 26)', () => {
  test('page has diagnostics sections with headers', async ({ page }) => {
    await navigateTo(page, '系统诊断');

    // Page title should be visible
    await expect(
      page.locator('.section-title').filter({ hasText: '系统诊断' })
    ).toBeVisible({ timeout: 10000 });

    // System health overview section
    await expect(
      page.locator('.settings-title').filter({ hasText: '系统健康概览' })
    ).toBeVisible();

    // Health summary grid should have category labels
    const categories = ['后端进程', '网关服务', '代理池', '代理节点'];
    for (const cat of categories) {
      await expect(
        page.locator('.health-summary-grid .health-label').filter({ hasText: cat })
      ).toBeVisible();
    }

    // Diagnostics button should be present
    await expect(page.locator('button:has-text("一键诊断")')).toBeVisible();
  });

  test('settings page loads with configuration form visible', async ({ page }) => {
    await navigateTo(page, '设置');

    // Page title should be visible
    await expect(
      page.locator('.section-title').filter({ hasText: '设置' })
    ).toBeVisible({ timeout: 10000 });

    // Settings grid should be visible
    await expect(page.locator('.settings-grid')).toBeVisible();

    // Theme settings card should be visible
    await expect(
      page.locator('.settings-title').filter({ hasText: '外观设置' })
    ).toBeVisible();

    // Theme mode radio buttons should be present
    const themeLabel = page.locator('.setting-name').filter({ hasText: '主题模式' });
    await expect(themeLabel).toBeVisible();

    // Theme radio group should have options (light, dark, auto)
    const radioButtons = page.locator('.el-radio-button');
    const radioCount = await radioButtons.count();
    expect(radioCount).toBeGreaterThanOrEqual(3);

    // Data settings card should also be visible
    await expect(
      page.locator('.settings-title').filter({ hasText: '数据设置' })
    ).toBeVisible();
  });
});
