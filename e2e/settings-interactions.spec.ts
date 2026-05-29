import { test, expect } from '@playwright/test';

/**
 * Dismiss any Element Plus notification popups that may be intercepting clicks.
 * The backend fires health alerts that create toast notifications overlaying the UI.
 */
async function dismissNotifications(page: import('@playwright/test').Page) {
  const notifications = page.locator('.el-notification');
  const count = await notifications.count();
  for (let i = count - 1; i >= 0; i--) {
    const closeBtn = notifications.nth(i).locator('.el-notification__closeBtn');
    if (await closeBtn.isVisible({ timeout: 200 }).catch(() => false)) {
      await closeBtn.click({ force: true });
      await page.waitForTimeout(100);
    }
  }
}

test.describe('Settings Page Interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to settings page via sidebar menu
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');
    // Wait for settings page content to be visible
    await page.locator('.settings-card').first().waitFor();
    // Dismiss any notification toasts that may overlay the UI
    await dismissNotifications(page);
  });

  test('should load settings page and display all sections', async ({ page }) => {
    // Verify page title
    await expect(page.locator('h2.section-title:has-text("设置")')).toBeVisible();
    await expect(page.locator('text=管理应用偏好设置')).toBeVisible();

    // Verify all six settings cards are visible
    await expect(page.locator('.settings-title:has-text("外观设置")')).toBeVisible();
    await expect(page.locator('.settings-title:has-text("数据设置")')).toBeVisible();
    await expect(page.locator('.settings-title:has-text("语言设置")')).toBeVisible();
    await expect(page.locator('.settings-title:has-text("告警设置")')).toBeVisible();
    await expect(page.locator('.settings-title:has-text("快捷键")')).toBeVisible();
    await expect(page.locator('.settings-title:has-text("关于")')).toBeVisible();
  });

  test('should switch theme to dark and verify HTML class', async ({ page }) => {
    const darkRadio = page.locator('.el-radio-button').filter({ hasText: '深色' });
    await darkRadio.click();
    await page.waitForTimeout(500);

    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');
    expect(htmlClass).not.toContain('light');
  });

  test('should switch theme to light and verify HTML class', async ({ page }) => {
    const lightRadio = page.locator('.el-radio-button').filter({ hasText: '浅色' });
    await lightRadio.click();
    await page.waitForTimeout(500);

    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('light');
    expect(htmlClass).not.toContain('dark');
  });

  test('should switch theme to auto and verify HTML class', async ({ page }) => {
    // First set to a known state
    const lightRadio = page.locator('.el-radio-button').filter({ hasText: '浅色' });
    await lightRadio.click();
    await page.waitForTimeout(300);

    // Now switch to auto
    const autoRadio = page.locator('.el-radio-button').filter({ hasText: '跟随系统' });
    await autoRadio.click();
    await page.waitForTimeout(500);

    // Auto should set either dark or light based on system preference
    const htmlClass = await page.locator('html').getAttribute('class');
    const hasDarkOrLight = htmlClass?.includes('dark') || htmlClass?.includes('light');
    expect(hasDarkOrLight).toBeTruthy();
  });

  test('should cycle through all themes and verify CSS updates', async ({ page }) => {
    // Switch through all three themes
    await page.locator('.el-radio-button').filter({ hasText: '浅色' }).click();
    await page.waitForTimeout(300);
    expect(await page.locator('html').getAttribute('class')).toContain('light');

    await page.locator('.el-radio-button').filter({ hasText: '深色' }).click();
    await page.waitForTimeout(300);
    expect(await page.locator('html').getAttribute('class')).toContain('dark');

    await page.locator('.el-radio-button').filter({ hasText: '跟随系统' }).click();
    await page.waitForTimeout(300);
    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass?.includes('dark') || htmlClass?.includes('light')).toBeTruthy();
  });

  test('should change table density to compact', async ({ page }) => {
    const compactRadio = page.locator('.el-radio-button').filter({ hasText: '紧凑' });
    await compactRadio.click();
    await page.waitForTimeout(500);

    const tableDensity = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--table-density').trim()
    );
    expect(tableDensity).toBe('compact');
  });

  test('should change table density to comfortable', async ({ page }) => {
    const comfortableRadio = page.locator('.el-radio-button').filter({ hasText: '宽松' });
    await comfortableRadio.click();
    await page.waitForTimeout(500);

    const tableDensity = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--table-density').trim()
    );
    expect(tableDensity).toBe('comfortable');
  });

  test('should change table density back to normal', async ({ page }) => {
    // First set to compact
    await page.locator('.el-radio-button').filter({ hasText: '紧凑' }).click();
    await page.waitForTimeout(300);

    // Then switch to normal
    await page.locator('.el-radio-button').filter({ hasText: '标准' }).click();
    await page.waitForTimeout(500);

    const tableDensity = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--table-density').trim()
    );
    expect(tableDensity).toBe('normal');
  });

  test('should change auto-refresh interval dropdown', async ({ page }) => {
    await dismissNotifications(page);
    // Click the visible select wrapper to open dropdown (not the hidden combobox input)
    const refreshWrapper = page.locator('.el-select:has([aria-label="自动刷新间隔"]) .el-select__wrapper');
    await refreshWrapper.click();
    await page.waitForTimeout(300);

    // Select "30 秒" option
    await page.locator('.el-select-dropdown__item').filter({ hasText: '30 秒' }).click();
    await page.waitForTimeout(300);

    // Verify via the visible placeholder/selection text
    const selectionText = page.locator('.el-select:has([aria-label="自动刷新间隔"]) .el-select__placeholder');
    await expect(selectionText).toContainText('30 秒');
  });

  test('should change auto-refresh interval to 5 minutes', async ({ page }) => {
    await dismissNotifications(page);
    const refreshWrapper = page.locator('.el-select:has([aria-label="自动刷新间隔"]) .el-select__wrapper');
    await refreshWrapper.click();
    await page.waitForTimeout(300);

    await page.getByRole('option', { name: '5 分钟', exact: true }).first().click();
    await page.waitForTimeout(300);

    const selectionText = page.locator('.el-select:has([aria-label="自动刷新间隔"]) .el-select__placeholder');
    await expect(selectionText).toContainText('5 分钟');
  });

  test('should change auto-refresh interval to off', async ({ page }) => {
    await dismissNotifications(page);
    const refreshWrapper = page.locator('.el-select:has([aria-label="自动刷新间隔"]) .el-select__wrapper');
    await refreshWrapper.click();
    await page.waitForTimeout(300);

    await page.locator('.el-select-dropdown__item').filter({ hasText: '关闭' }).click();
    await page.waitForTimeout(300);

    const selectionText = page.locator('.el-select:has([aria-label="自动刷新间隔"]) .el-select__placeholder');
    await expect(selectionText).toContainText('关闭');
  });

  test('should change default startup page', async ({ page }) => {
    await dismissNotifications(page);
    const pageWrapper = page.locator('.el-select:has([aria-label="默认启动页面"]) .el-select__wrapper');
    await pageWrapper.click();
    await page.waitForTimeout(300);

    // Select "代理节点" option
    await page.locator('.el-select-dropdown__item').filter({ hasText: '代理节点' }).click();
    await page.waitForTimeout(300);

    const selectionText = page.locator('.el-select:has([aria-label="默认启动页面"]) .el-select__placeholder');
    await expect(selectionText).toContainText('代理节点');
  });

  test('should change default startup page to tasks', async ({ page }) => {
    await dismissNotifications(page);
    const pageWrapper = page.locator('.el-select:has([aria-label="默认启动页面"]) .el-select__wrapper');
    await pageWrapper.click();
    await page.waitForTimeout(300);

    await page.locator('.el-select-dropdown__item').filter({ hasText: '任务中心' }).click();
    await page.waitForTimeout(300);

    const selectionText = page.locator('.el-select:has([aria-label="默认启动页面"]) .el-select__placeholder');
    await expect(selectionText).toContainText('任务中心');
  });

  test('should toggle browser notification switch', async ({ page }) => {
    await dismissNotifications(page);
    // Element Plus renders a hidden <input role="switch">; target the visible .el-switch wrapper
    const switchInput = page.getByRole('switch', { name: '启用浏览器桌面通知' });
    const elSwitch = page.locator('.el-switch:has([aria-label="启用浏览器桌面通知"])');
    await expect(elSwitch).toBeVisible();

    // Record initial state from the hidden input
    const initialState = await switchInput.isChecked();

    // Toggle by clicking the visible wrapper
    await elSwitch.click();
    await page.waitForTimeout(300);

    // Verify the state changed
    const newState = await switchInput.isChecked();
    expect(newState).toBe(!initialState);
  });

  test('should toggle pool health alert switch', async ({ page }) => {
    await dismissNotifications(page);
    const switchInput = page.getByRole('switch', { name: '启用代理池健康告警' });
    const elSwitch = page.locator('.el-switch:has([aria-label="启用代理池健康告警"])');
    await expect(elSwitch).toBeVisible();

    const initialState = await switchInput.isChecked();

    await elSwitch.click();
    await page.waitForTimeout(300);

    const newState = await switchInput.isChecked();
    expect(newState).toBe(!initialState);
  });

  test('should toggle proxy count alert switch', async ({ page }) => {
    await dismissNotifications(page);
    const switchInput = page.getByRole('switch', { name: '启用可用代理数量告警' });
    const elSwitch = page.locator('.el-switch:has([aria-label="启用可用代理数量告警"])');
    await expect(elSwitch).toBeVisible();

    const initialState = await switchInput.isChecked();

    await elSwitch.click();
    await page.waitForTimeout(300);

    const newState = await switchInput.isChecked();
    expect(newState).toBe(!initialState);
  });

  test('should toggle backend crash detection switch', async ({ page }) => {
    await dismissNotifications(page);
    const switchInput = page.getByRole('switch', { name: '启用后端进程崩溃检测' });
    const elSwitch = page.locator('.el-switch:has([aria-label="启用后端进程崩溃检测"])');
    await expect(elSwitch).toBeVisible();

    const initialState = await switchInput.isChecked();

    await elSwitch.click();
    await page.waitForTimeout(300);

    const newState = await switchInput.isChecked();
    expect(newState).toBe(!initialState);
  });

  test('should toggle subscription refresh fail alert switch', async ({ page }) => {
    await dismissNotifications(page);
    const switchInput = page.getByRole('switch', { name: '启用订阅刷新失败告警' });
    const elSwitch = page.locator('.el-switch:has([aria-label="启用订阅刷新失败告警"])');
    await expect(elSwitch).toBeVisible();

    const initialState = await switchInput.isChecked();

    await elSwitch.click();
    await page.waitForTimeout(300);

    const newState = await switchInput.isChecked();
    expect(newState).toBe(!initialState);
  });

  test('should display all keyboard shortcuts', async ({ page }) => {
    const shortcutsCard = page.locator('.settings-card').filter({ hasText: '快捷键' });
    await expect(shortcutsCard.locator('.settings-title:has-text("快捷键")')).toBeVisible();

    // Verify all shortcuts are displayed
    const expectedShortcuts = [
      { keys: 'Ctrl + K', desc: '打开全局搜索' },
      { keys: 'Ctrl + R', desc: '刷新当前页面数据' },
      { keys: 'Ctrl + E', desc: '导出配置' },
      { keys: 'Ctrl + I', desc: '导入配置' },
      { keys: 'Shift + ?', desc: '显示帮助' },
      { keys: 'Escape', desc: '关闭对话框' },
    ];

    for (const shortcut of expectedShortcuts) {
      await expect(shortcutsCard.locator('.shortcut-keys').filter({ hasText: shortcut.keys })).toBeVisible();
      await expect(shortcutsCard.locator('.shortcut-desc').filter({ hasText: shortcut.desc })).toBeVisible();
    }
  });

  test('should display about section with version and description', async ({ page }) => {
    const aboutCard = page.locator('.settings-card').filter({ hasText: '关于' });
    await expect(aboutCard.locator('.settings-title:has-text("关于")')).toBeVisible();

    // Verify application name
    await expect(aboutCard.locator('.about-label').filter({ hasText: '应用名称' })).toBeVisible();
    await expect(aboutCard.locator('.about-value').filter({ hasText: 'Proxy Pool' })).toBeVisible();

    // Verify version
    await expect(aboutCard.locator('.about-label').filter({ hasText: '版本' })).toBeVisible();
    await expect(aboutCard.locator('.about-value').filter({ hasText: '0.2.0' })).toBeVisible();

    // Verify description
    await expect(aboutCard.locator('.about-label').filter({ hasText: '描述' })).toBeVisible();
    await expect(aboutCard.locator('.about-value').filter({ hasText: '高性能代理池管理器' })).toBeVisible();
  });

  test('should verify alert silence period dropdown options', async ({ page }) => {
    await dismissNotifications(page);
    const silenceWrapper = page.locator('.el-select:has([aria-label="告警静默期"]) .el-select__wrapper');
    await expect(silenceWrapper).toBeVisible();

    // Open dropdown and verify options using exact role option matching
    await silenceWrapper.click();
    await page.waitForTimeout(300);

    const expectedOptions = ['5 分钟', '15 分钟', '30 分钟', '1 小时', '不静默'];
    for (const option of expectedOptions) {
      await expect(page.getByRole('option', { name: option, exact: true })).toBeVisible();
    }

    // Close dropdown by pressing Escape
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
  });

  test('should persist theme after page reload', async ({ page }) => {
    // Set dark theme
    await page.locator('.el-radio-button').filter({ hasText: '深色' }).click();
    await page.waitForTimeout(500);

    // Reload the page
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.settings-card').first().waitFor();
    await dismissNotifications(page);

    // Verify dark theme is still active
    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');
  });

  test('should display language setting as disabled', async ({ page }) => {
    await expect(page.locator('.settings-title:has-text("语言设置")')).toBeVisible();
    await expect(page.locator('text=界面语言')).toBeVisible();
    await expect(page.locator('text=目前仅支持中文')).toBeVisible();

    // Language selector should be disabled
    const langSelect = page.getByRole('combobox', { name: '界面语言选择' });
    await expect(langSelect).toBeDisabled();
  });
});
