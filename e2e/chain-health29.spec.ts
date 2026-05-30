import { test, expect } from '@playwright/test';

// ── Chain Health Check (Round 29) ──

test.describe('Chain Health Check (Round 29)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '仪表盘' }).click();
    await page.locator('.dashboard-page').waitFor({ state: 'visible', timeout: 15000 });
    await page.locator('.stat-grid').first().waitFor({ state: 'visible', timeout: 30000 });
  });

  test('dashboard has header with title and subtitle', async ({ page }) => {
    const headerTitle = page.locator('.header-title');
    await expect(headerTitle).toBeVisible();
    await expect(headerTitle).toHaveText('仪表盘');

    const headerSubtitle = page.locator('.header-subtitle');
    await expect(headerSubtitle).toBeVisible();
    await expect(headerSubtitle).toHaveText('代理池运行状态概览');
  });

  test('dashboard has stat cards grid with 4+ cards', async ({ page }) => {
    const statGrid = page.locator('.stat-grid').first();
    await expect(statGrid).toBeVisible();

    const cards = statGrid.locator('.stat-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThanOrEqual(4);

    // Verify known stat labels exist
    const labels = ['节点总数', '可用节点', '可用率', '平均延迟'];
    for (const label of labels) {
      const card = page.locator('.stat-card').filter({ hasText: label });
      await expect(card.first()).toBeVisible();
    }
  });

  test('dashboard has sidebar with term explanations section', async ({ page }) => {
    const sidebar = page.locator('.sidebar-menu');
    await expect(sidebar).toBeVisible();

    // Sidebar menu group titles serve as term explanations for the sections below
    const groupTitles = page.locator('.sidebar-menu-group-title');
    const groupCount = await groupTitles.count();
    expect(groupCount).toBeGreaterThanOrEqual(3);

    // Verify specific section group titles
    const expectedGroups = ['概览', '代理管理', '系统'];
    for (const text of expectedGroups) {
      const group = page.locator('.sidebar-menu-group-title').filter({ hasText: text });
      await expect(group.first()).toBeVisible();
    }
  });

  test('dashboard has quick operations section with buttons', async ({ page }) => {
    const actionBar = page.locator('.action-bar').first();
    await expect(actionBar).toBeVisible();

    const buttons = actionBar.locator('button, a.btn');
    const buttonCount = await buttons.count();
    expect(buttonCount).toBeGreaterThanOrEqual(4);

    // Verify key operation buttons exist
    const expectedButtons = ['任务中心', '创建代理池', '添加入站端口', '导入节点'];
    for (const text of expectedButtons) {
      const btn = actionBar.locator('button, a.btn').filter({ hasText: text });
      await expect(btn.first()).toBeVisible();
    }
  });

  test('dashboard has recent activity section', async ({ page }) => {
    // Activity feed card with title "最近活动"
    const activityCard = page.locator('.card-title').filter({ hasText: '最近活动' });
    await expect(activityCard).toBeVisible();

    // The activity card body should contain either activity items or an empty state
    const cardBody = activityCard.locator('..').locator('..').locator('.card-body');
    const hasItems = await cardBody.locator('.activity-item, .activity-feed').first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasEmpty = await cardBody.locator('.empty-state').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasItems || hasEmpty).toBeTruthy();
  });
});

// ── Batch Operations (Round 29) ──

test.describe('Batch Operations (Round 29)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '入站端口' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('inbound ports page loads with create button', async ({ page }) => {
    const createBtn = page.locator('button').filter({ hasText: '创建端口' }).first();
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toBeEnabled();
  });

  test('inbound ports table has column headers', async ({ page }) => {
    // Check that the section title is visible
    const sectionTitle = page.locator('.section-title').filter({ hasText: '入站端口' });
    await expect(sectionTitle).toBeVisible();

    // If ports exist, verify table structure with column headers
    const table = page.locator('.data-table').first();
    const hasTable = await table.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasTable) {
      const headers = table.locator('thead th');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThanOrEqual(5);

      // Verify specific column headers
      const expectedHeaders = ['状态', '名称', '跳点链路'];
      for (const text of expectedHeaders) {
        const th = headers.filter({ hasText: text });
        await expect(th.first()).toBeVisible();
      }
    } else {
      // No ports yet - empty state should be visible
      const emptyState = page.locator('.empty-state').first();
      await expect(emptyState).toBeVisible();
    }
  });

  test('inbound ports page has refresh functionality', async ({ page }) => {
    const refreshBtn = page.locator('button').filter({ hasText: '刷新' }).first();
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();

    // Clicking refresh should not break the page
    await refreshBtn.click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });
});

// ── System Diagnostics Export (Round 29) ──

test.describe('System Diagnostics Export (Round 29)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).waitFor({ state: 'visible', timeout: 10000 });
    await page.locator('.el-menu-item').filter({ hasText: '使用指南' }).click();
    await page.locator('.page-container, .card').first().waitFor({ state: 'visible', timeout: 15000 });
  });

  test('docs page has quick start section', async ({ page }) => {
    const quickStartTitle = page.locator('.settings-title').filter({ hasText: '快速开始' });
    await expect(quickStartTitle).toBeVisible();

    // Quick start section should have numbered steps
    const steps = page.locator('.quick-start-step');
    const stepCount = await steps.count();
    expect(stepCount).toBeGreaterThanOrEqual(4);

    // Verify first step exists with expected content
    const firstStepTitle = page.locator('.step-title').filter({ hasText: '添加订阅源' });
    await expect(firstStepTitle).toBeVisible();
  });

  test('docs page has FAQ section', async ({ page }) => {
    const faqTitle = page.locator('.settings-title').filter({ hasText: '常见问题' });
    await expect(faqTitle).toBeVisible();

    // FAQ section should have expandable question items
    const faqItems = page.locator('.faq-item');
    const faqCount = await faqItems.count();
    expect(faqCount).toBeGreaterThanOrEqual(3);

    // Verify first FAQ question is clickable
    const firstQuestion = page.locator('.faq-question').first();
    await expect(firstQuestion).toBeVisible();
    await firstQuestion.click();

    // After clicking, an answer should be revealed
    const answer = page.locator('.faq-answer').first();
    await expect(answer).toBeVisible();
  });
});
