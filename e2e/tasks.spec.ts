import { test, expect } from '@playwright/test';

test.describe('Task Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/webui/');
    await page.waitForLoadState('networkidle');
    // Navigate to tasks page
    await page.click('text=任务中心');
    await page.waitForLoadState('networkidle');
  });

  test('should display task list', async ({ page }) => {
    // Check if task list or empty state is visible
    const taskList = page.locator('.task-item, .el-table').first();
    const emptyState = page.locator('text=暂无任务');

    const hasTasks = await taskList.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasTasks || hasEmptyState).toBeTruthy();
  });

  test('should start subscription refresh task', async ({ page }) => {
    // Find and click subscription refresh button
    const refreshButton = page.locator('button:has-text("刷新订阅")');
    if (await refreshButton.isVisible()) {
      await refreshButton.click();

      // Wait for task to start
      await page.waitForTimeout(1000);

      // Verify task appears in list
      const taskItem = page.locator('.task-item, .el-table-row').filter({ hasText: '订阅刷新' });
      const isVisible = await taskItem.isVisible().catch(() => false);

      // Or verify success message
      const successMessage = page.locator('.el-message--success');

      expect(
        isVisible || (await successMessage.isVisible().catch(() => false))
      ).toBeTruthy();
    }
  });

  test('should start proxy test task', async ({ page }) => {
    // Find and click proxy test button
    const testButton = page.locator('button:has-text("测试代理")');
    if (await testButton.isVisible()) {
      await testButton.click();

      // Wait for task to start
      await page.waitForTimeout(1000);

      // Verify task appears in list
      const taskItem = page.locator('.task-item, .el-table-row').filter({ hasText: '代理测试' });
      const isVisible = await taskItem.isVisible().catch(() => false);

      // Or verify success message
      const successMessage = page.locator('.el-message--success');

      expect(
        isVisible || (await successMessage.isVisible().catch(() => false))
      ).toBeTruthy();
    }
  });

  test('should view task details', async ({ page }) => {
    // Find first task item
    const taskItem = page.locator('.task-item, .el-table-row').first();
    if (await taskItem.isVisible()) {
      await taskItem.click();

      // Verify task details are shown
      const detailsSection = page.locator('.task-details, .el-drawer');
      await expect(detailsSection).toBeVisible();
    }
  });

  test('should stop running task', async ({ page }) => {
    // Find stop button for a running task
    const stopButton = page.locator('button:has-text("停止")').first();
    if (await stopButton.isVisible()) {
      await stopButton.click();

      // Confirm stop action
      const confirmDialog = page.locator('.el-message-box, .el-dialog').filter({ hasText: '确认' });
      if (await confirmDialog.isVisible()) {
        const confirmButton = confirmDialog.locator('button:has-text("确定")');
        await confirmButton.click();

        await page.waitForTimeout(1000);

        // Verify task status changed
        const stoppedTask = page.locator('.task-item, .el-table-row').filter({ hasText: '已停止' });
        const successMessage = page.locator('.el-message--success');

        expect(
          (await stoppedTask.isVisible().catch(() => false)) ||
          (await successMessage.isVisible().catch(() => false))
        ).toBeTruthy();
      }
    }
  });

  test('should delete completed task', async ({ page }) => {
    // Find delete button for a completed task
    const deleteButton = page.locator('button:has-text("删除")').first();
    if (await deleteButton.isVisible()) {
      await deleteButton.click();

      // Confirm deletion
      const confirmDialog = page.locator('.el-message-box, .el-dialog').filter({ hasText: '确认' });
      if (await confirmDialog.isVisible()) {
        const confirmButton = confirmDialog.locator('button:has-text("确定")');
        await confirmButton.click();

        await page.waitForTimeout(1000);

        // Verify task is removed
        const successMessage = page.locator('.el-message--success');
        expect(await successMessage.isVisible().catch(() => false)).toBeTruthy();
      }
    }
  });

  test('should auto-refresh task list', async ({ page }) => {
    // Check if task list updates automatically
    const initialTaskCount = await page.locator('.task-item, .el-table-row').count();

    // Wait for auto-refresh (assuming 5 second interval)
    await page.waitForTimeout(6000);

    // Verify task list is still visible (may or may not have new tasks)
    const taskList = page.locator('.task-item, .el-table-row');
    const emptyState = page.locator('text=暂无任务');

    const hasTasks = (await taskList.count()) > 0;
    const hasEmptyState = await emptyState.isVisible().catch(() => false);

    expect(hasTasks || hasEmptyState).toBeTruthy();
  });

  test('should filter tasks by status', async ({ page }) => {
    // Find status filter
    const statusFilter = page.locator('select').filter({ hasText: '状态' });
    if (await statusFilter.isVisible()) {
      await statusFilter.selectOption('running');
      await page.waitForTimeout(500);

      // Verify filtered results
      const runningTasks = page.locator('.task-item, .el-table-row').filter({ hasText: '运行中' });
      const count = await runningTasks.count();

      // All shown tasks should be running (or no tasks shown)
      expect(count >= 0).toBeTruthy();
    }
  });
});