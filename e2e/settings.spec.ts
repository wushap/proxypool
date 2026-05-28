import { test, expect } from '@playwright/test';

test.describe('Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to settings page via sidebar menu
    await page.locator('.el-menu-item').filter({ hasText: '设置' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load settings page and display title', async ({ page }) => {
    await expect(page.locator('h2.section-title:has-text("设置")')).toBeVisible();
    await expect(page.locator('text=管理应用偏好设置')).toBeVisible();
  });

  test('should display theme settings section', async ({ page }) => {
    await expect(page.locator('text=外观设置')).toBeVisible();
    await expect(page.locator('text=主题模式')).toBeVisible();
    await expect(page.locator('text=表格密度')).toBeVisible();

    // Verify theme radio buttons exist
    await expect(page.locator('text=浅色')).toBeVisible();
    await expect(page.locator('text=深色')).toBeVisible();
    await expect(page.locator('text=跟随系统')).toBeVisible();
  });

  test('should display data settings section', async ({ page }) => {
    await expect(page.locator('text=数据设置')).toBeVisible();
    await expect(page.locator('text=自动刷新间隔')).toBeVisible();
    await expect(page.locator('text=默认启动页面')).toBeVisible();
  });

  test('should display alert settings section', async ({ page }) => {
    await expect(page.locator('text=告警设置')).toBeVisible();
    await expect(page.locator('text=浏览器通知')).toBeVisible();
    await expect(page.locator('text=代理池健康告警')).toBeVisible();
    await expect(page.locator('text=可用代理数量告警')).toBeVisible();
    await expect(page.locator('text=后端进程崩溃检测')).toBeVisible();
    await expect(page.locator('text=订阅刷新失败告警')).toBeVisible();
    await expect(page.locator('text=告警静默期')).toBeVisible();
  });

  test('should display keyboard shortcuts section', async ({ page }) => {
    await expect(page.locator('text=快捷键')).toBeVisible();
    await expect(page.locator('text=Ctrl + K')).toBeVisible();
    await expect(page.locator('text=打开全局搜索')).toBeVisible();
  });

  test('should display about section with version info', async ({ page }) => {
    await expect(page.locator('text=关于')).toBeVisible();
    await expect(page.locator('text=应用名称')).toBeVisible();
    await expect(page.locator('text=Proxy Pool')).toBeVisible();
    await expect(page.locator('text=版本')).toBeVisible();
    await expect(page.locator('text=0.2.0')).toBeVisible();
  });

  test('should change theme to dark mode', async ({ page }) => {
    const darkRadio = page.locator('.el-radio-button').filter({ hasText: '深色' });
    if (await darkRadio.isVisible()) {
      await darkRadio.click();
      await page.waitForTimeout(300);

      // Verify dark class is applied to html element
      const htmlClass = await page.locator('html').getAttribute('class');
      expect(htmlClass).toContain('dark');
    }
  });

  test('should change theme back to light mode', async ({ page }) => {
    const lightRadio = page.locator('.el-radio-button').filter({ hasText: '浅色' });
    if (await lightRadio.isVisible()) {
      await lightRadio.click();
      await page.waitForTimeout(300);

      const htmlClass = await page.locator('html').getAttribute('class');
      expect(htmlClass).toContain('light');
    }
  });

  test('should change table density setting', async ({ page }) => {
    const compactRadio = page.locator('.el-radio-button').filter({ hasText: '紧凑' });
    if (await compactRadio.isVisible()) {
      await compactRadio.click();
      await page.waitForTimeout(300);

      // Verify CSS variable was updated
      const tableDensity = await page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue('--table-density').trim()
      );
      expect(tableDensity).toBe('compact');
    }
  });

  test('should reset settings to defaults', async ({ page }) => {
    const resetButton = page.locator('button:has-text("重置为默认设置")');
    if (await resetButton.isVisible()) {
      await resetButton.click();
      await page.waitForTimeout(300);

      // After reset, theme should be "auto" (跟随系统)
      const autoRadio = page.locator('.el-radio-button').filter({ hasText: '跟随系统' });
      await expect(autoRadio).toHaveAttribute('aria-pressed', 'true');
    }
  });

  test('should display language setting as disabled', async ({ page }) => {
    await expect(page.locator('text=界面语言')).toBeVisible();
    await expect(page.locator('text=目前仅支持中文')).toBeVisible();

    // Language selector should be disabled
    const langSelect = page.locator('[aria-label="界面语言选择"]');
    if (await langSelect.isVisible()) {
      await expect(langSelect).toBeDisabled();
    }
  });
});
