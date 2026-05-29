import { test, expect } from '@playwright/test';

test.describe('Proxy Pool Templates', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to proxy pools page
    await page.locator('.el-menu-item').filter({ hasText: '多跳代理池' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.section-title').filter({ hasText: '多跳代理池' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display template library section', async ({ page }) => {
    // The template library section header "模板库" should be visible
    await expect(page.locator('h4.form-section-title').filter({ hasText: '模板库' })).toBeVisible();
  });

  test('should display template cards', async ({ page }) => {
    // Verify specific template cards are displayed
    await expect(page.locator('.template-name').filter({ hasText: '日本落地池' })).toBeVisible();
    await expect(page.locator('.template-name').filter({ hasText: '香港前置池' })).toBeVisible();
    await expect(page.locator('.template-name').filter({ hasText: '美国落地池' })).toBeVisible();
    await expect(page.locator('.template-name').filter({ hasText: '新加坡落地池' })).toBeVisible();
  });

  test('should apply template to form when clicking apply button', async ({ page }) => {
    // Click the apply button on the Japan exit template card
    const japanCard = page.locator('.pool-template-card').filter({ hasText: '日本落地池' });
    await expect(japanCard).toBeVisible();
    await japanCard.locator('button:has-text("应用")').click();
    await page.waitForTimeout(500);

    // Verify the form name was populated from the template
    const nameInput = page.locator('input[placeholder*="exit"]');
    const nameValue = await nameInput.inputValue();
    expect(nameValue).toBe('日本落地池');
  });

  test('should display template category tabs', async ({ page }) => {
    // Verify all category tabs are present
    const categoryTabs = page.locator('.template-category-tabs .btn');
    await expect(categoryTabs.filter({ hasText: '全部' })).toBeVisible();
    await expect(categoryTabs.filter({ hasText: '按地区' })).toBeVisible();
    await expect(categoryTabs.filter({ hasText: '按用途' })).toBeVisible();
    await expect(categoryTabs.filter({ hasText: '自定义' })).toBeVisible();
  });

  test('should filter templates by region category', async ({ page }) => {
    // Click "按地区" tab
    const regionTab = page.locator('.template-category-tabs .btn').filter({ hasText: '按地区' });
    await regionTab.click();
    await page.waitForTimeout(300);

    // Region templates should be visible
    await expect(page.locator('.template-name').filter({ hasText: '日本落地池' })).toBeVisible();
    await expect(page.locator('.template-name').filter({ hasText: '美国落地池' })).toBeVisible();

    // Use-case templates should NOT be visible
    const highSpeed = page.locator('.template-name').filter({ hasText: '高速测试池' });
    await expect(highSpeed).not.toBeVisible();
  });

  test('should filter templates by use-case category', async ({ page }) => {
    // Click "按用途" tab
    const usecaseTab = page.locator('.template-category-tabs .btn').filter({ hasText: '按用途' });
    await usecaseTab.click();
    await page.waitForTimeout(300);

    // Use-case templates should be visible
    await expect(page.locator('.template-name').filter({ hasText: '高速测试池' })).toBeVisible();
    await expect(page.locator('.template-name').filter({ hasText: 'ChatGPT 解锁池' })).toBeVisible();

    // Region templates should NOT be visible
    const japanPool = page.locator('.template-name').filter({ hasText: '日本落地池' });
    await expect(japanPool).not.toBeVisible();
  });
});

test.describe('Settings Alerts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to settings page
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');
    // Wait for settings content to appear
    await page.locator('.settings-title').filter({ hasText: '告警设置' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display alert settings section', async ({ page }) => {
    await expect(page.locator('.settings-title').filter({ hasText: '告警设置' })).toBeVisible();
    await expect(page.locator('.setting-name').filter({ hasText: '浏览器通知' })).toBeVisible();
  });

  test('should display browser notification toggle', async ({ page }) => {
    const toggle = page.locator('.el-switch').filter({ has: page.getByLabel('启用浏览器桌面通知') });
    await expect(toggle).toBeVisible();
  });

  test('should display pool health alert toggle', async ({ page }) => {
    const toggle = page.locator('.el-switch').filter({ has: page.getByLabel('启用代理池健康告警') });
    await expect(toggle).toBeVisible();
    await expect(page.locator('.setting-name').filter({ hasText: '代理池健康告警' })).toBeVisible();
  });

  test('should display proxy count alert toggle', async ({ page }) => {
    const toggle = page.locator('.el-switch').filter({ has: page.getByLabel('启用可用代理数量告警') });
    await expect(toggle).toBeVisible();
    await expect(page.locator('.setting-name').filter({ hasText: '可用代理数量告警' })).toBeVisible();
  });

  test('should display backend crash alert toggle', async ({ page }) => {
    const toggle = page.locator('.el-switch').filter({ has: page.getByLabel('启用后端进程崩溃检测') });
    await expect(toggle).toBeVisible();
    await expect(page.locator('.setting-name').filter({ hasText: '后端进程崩溃检测' })).toBeVisible();
  });

  test('should display subscription fail alert toggle', async ({ page }) => {
    const toggle = page.locator('.el-switch').filter({ has: page.getByLabel('启用订阅刷新失败告警') });
    await expect(toggle).toBeVisible();
    await expect(page.locator('.setting-name').filter({ hasText: '订阅刷新失败告警' })).toBeVisible();
  });
});

test.describe('Settings Keyboard Shortcuts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to settings page
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('.settings-title').filter({ hasText: '快捷键' }).waitFor({ state: 'visible', timeout: 10000 });
  });

  test('should display keyboard shortcuts section', async ({ page }) => {
    await expect(page.locator('.settings-title').filter({ hasText: '快捷键' })).toBeVisible();
  });

  test('should list Ctrl+K shortcut', async ({ page }) => {
    await expect(page.locator('.shortcut-keys').filter({ hasText: 'Ctrl + K' })).toBeVisible();
    await expect(page.locator('.shortcut-desc').filter({ hasText: '打开全局搜索' })).toBeVisible();
  });

  test('should list Escape shortcut', async ({ page }) => {
    await expect(page.locator('.shortcut-keys').filter({ hasText: 'Escape' })).toBeVisible();
    await expect(page.locator('.shortcut-desc').filter({ hasText: '关闭对话框' })).toBeVisible();
  });
});
