import { test, expect } from '@playwright/test';

test.describe('Docs Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Navigate to docs page via sidebar menu
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('should load docs page and display title', async ({ page }) => {
    await expect(page.locator('h2.section-title:has-text("使用指南")')).toBeVisible();
    await expect(page.locator('text=快速上手 Proxy Pool')).toBeVisible();
  });

  test('should display quick start guide with 5 steps', async ({ page }) => {
    await expect(page.locator('.settings-title').filter({ hasText: '快速开始' })).toBeVisible();

    // Verify all 5 steps
    await expect(page.locator('.step-title:has-text("添加订阅源")')).toBeVisible();
    await expect(page.locator('.step-title:has-text("创建代理池")')).toBeVisible();
    await expect(page.locator('.step-title:has-text("配置入站端口")')).toBeVisible();
    await expect(page.locator('.step-title:has-text("测试代理")')).toBeVisible();
    await expect(page.locator('.step-title:has-text("开始使用")')).toBeVisible();

    // Verify step numbers
    const steps = page.locator('.step-number');
    await expect(steps).toHaveCount(5);
  });

  test('should display feature overview grid', async ({ page }) => {
    await expect(page.locator('text=功能概览')).toBeVisible();

    // Verify all 6 feature items
    await expect(page.locator('.feature-name:has-text("代理节点")')).toBeVisible();
    await expect(page.locator('.feature-name:has-text("代理池")')).toBeVisible();
    await expect(page.locator('.feature-name:has-text("订阅管理")')).toBeVisible();
    await expect(page.locator('.feature-name:has-text("任务中心")')).toBeVisible();
    await expect(page.locator('.feature-name:has-text("入站端口")')).toBeVisible();
    await expect(page.locator('.feature-name:has-text("设置")')).toBeVisible();

    const featureItems = page.locator('.feature-item');
    await expect(featureItems).toHaveCount(6);
  });

  test('should display FAQ section with expandable questions', async ({ page }) => {
    await expect(page.locator('text=常见问题')).toBeVisible();

    // Verify FAQ questions are visible
    await expect(page.locator('text=如何添加代理？')).toBeVisible();
    await expect(page.locator('text=前置池和落地池有什么区别？')).toBeVisible();
    await expect(page.locator('text=如何提高代理速度？')).toBeVisible();
    await expect(page.locator('text=如何备份配置？')).toBeVisible();
  });

  test('should expand and collapse FAQ answers', async ({ page }) => {
    // Click on first FAQ question
    const firstQuestion = page.locator('.faq-question').first();
    await firstQuestion.click();
    await page.waitForTimeout(200);

    // Answer should be visible
    const answer = page.locator('.faq-answer').first();
    await expect(answer).toBeVisible();
    await expect(answer).toContainText('订阅管理');

    // Click again to collapse
    await firstQuestion.click();
    await page.waitForTimeout(200);
    await expect(answer).not.toBeVisible();
  });

  test('should display API reference section', async ({ page }) => {
    await expect(page.locator('.settings-title').filter({ hasText: 'API 参考' })).toBeVisible();
    await expect(page.locator('.api-title:has-text("FastAPI 自动生成文档")')).toBeVisible();
    await expect(page.locator('.api-url:has-text("/api/docs")')).toBeVisible();

    // Verify API docs link
    const apiLink = page.locator('.api-reference a:has-text("打开 API 文档")');
    await expect(apiLink).toBeVisible();
    await expect(apiLink).toHaveAttribute('href', '/api/docs');
  });

  test('should display API docs link in header', async ({ page }) => {
    const apiDocsLink = page.locator('.section-header a:has-text("API 文档")');
    await expect(apiDocsLink.first()).toBeVisible();
  });
});
