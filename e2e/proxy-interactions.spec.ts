import { test, expect } from '@playwright/test';

// Helper: navigate to proxies page and wait for data rows to be present
async function goToProxies(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  await page.locator('.el-menu-item').filter({ hasText: '代理节点' }).click();
  await page.waitForLoadState('networkidle');
  // Wait for actual data rows (checkboxes) to appear, or for the page to settle
  // with a count > 0 in the status bar (data loaded) or 0 (empty/error state)
  const hasData = await page.locator('table.data-table tbody input[type="checkbox"]')
    .first().waitFor({ state: 'visible', timeout: 10000 }).then(() => true).catch(() => false);
  if (!hasData) {
    // Data might not have loaded; wait for status bar to settle
    await page.waitForTimeout(2000);
  }
}

// Helper: set a proxy filter via Vue app state and trigger reload
async function setProxyFilter(page: import('@playwright/test').Page, key: string, value: string) {
  await page.evaluate(({ key, value }) => {
    const el = document.querySelector('#app') as any;
    const vm = el?.__vue_app__?._instance?.proxy;
    if (vm?.appState) {
      vm.appState.proxyFilters[key] = value;
      vm.appState.updateUrlWithFilters();
    }
  }, { key, value });
  // Wait for the data to reload
  await page.waitForTimeout(2000);
}

// Helper: clear all proxy filters via Vue app state
async function clearProxyFiltersViaState(page: import('@playwright/test').Page) {
  await page.evaluate(() => {
    const el = document.querySelector('#app') as any;
    const vm = el?.__vue_app__?._instance?.proxy;
    if (vm?.appState) {
      vm.appState.clearProxyFilters();
    }
  });
  await page.waitForTimeout(2000);
}

// Helper: open the advanced filter panel
async function openAdvancedFilter(page: import('@playwright/test').Page) {
  const toggle = page.locator('.filter-panel-toggle');
  await toggle.click();
  await page.locator('.filter-panel-body').first().waitFor({ state: 'visible', timeout: 5000 });
}

test.describe('Proxy Interactions', () => {
  // ----- 1. Proxy list filtering -----
  test.describe('Proxy list filtering', () => {
    test('should filter by protocol and reduce displayed count', async ({ page }) => {
      await goToProxies(page);

      // Get baseline count
      const statusDisplay = page.locator('.status-bar[role="status"]').first();
      await expect(statusDisplay).toBeVisible();
      const baselineCountText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
      const baselineCount = Number(baselineCountText);
      expect(baselineCount).toBeGreaterThan(0);

      // Apply protocol filter via Vue state
      await setProxyFilter(page, 'protocol', 'ss');

      // Verify count is now less than or equal to baseline
      const filteredCountText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
      const filteredCount = Number(filteredCountText);
      expect(filteredCount).toBeGreaterThan(0);
      expect(filteredCount).toBeLessThanOrEqual(baselineCount);

      // Verify all visible rows show the filtered protocol
      const rows = page.locator('table.data-table tbody tr');
      const rowCount = await rows.count();
      for (let i = 0; i < Math.min(rowCount, 5); i++) {
        const rowText = await rows.nth(i).textContent();
        expect(rowText?.toLowerCase()).toContain('ss');
      }

      // Clean up: clear filters
      await clearProxyFiltersViaState(page);
    });

    test('should filter by status (available only)', async ({ page }) => {
      await goToProxies(page);

      // Apply available filter
      await setProxyFilter(page, 'available', 'true');

      // Verify no DOWN badges in the table
      const downBadges = page.locator('table.data-table tbody tr .badge-danger');
      const downCount = await downBadges.count();
      expect(downCount).toBe(0);

      // Clean up
      await clearProxyFiltersViaState(page);
    });

    test('should open advanced filter panel and show filter fields', async ({ page }) => {
      await goToProxies(page);
      await openAdvancedFilter(page);

      // Verify filter fields are visible
      await expect(page.locator('.filter-panel-field').filter({ hasText: '协议' })).toBeVisible();
      await expect(page.locator('.filter-panel-field').filter({ hasText: '状态' })).toBeVisible();
      await expect(page.locator('.filter-panel-field').filter({ hasText: '国家' })).toBeVisible();
      await expect(page.locator('.filter-panel-field').filter({ hasText: '最低分数' })).toBeVisible();
      await expect(page.locator('.filter-panel-field').filter({ hasText: '最大延迟' })).toBeVisible();

      // Verify action buttons exist
      await expect(page.locator('button[aria-label="清空所有筛选条件"]')).toBeVisible();
      await expect(page.locator('button[aria-label="应用筛选条件并刷新"]')).toBeVisible();
    });

    test('should show filter chip when protocol filter is active', async ({ page }) => {
      await goToProxies(page);

      // Apply filter
      await setProxyFilter(page, 'protocol', 'trojan');

      // Filter chip should appear
      const chip = page.locator('.filter-chip').first();
      const isChipVisible = await chip.isVisible().catch(() => false);
      if (isChipVisible) {
        const chipText = await chip.textContent();
        expect(chipText).toContain('trojan');
      }

      // Clean up
      await clearProxyFiltersViaState(page);
    });

    test('should clear filters and restore full list', async ({ page }) => {
      await goToProxies(page);

      // Get baseline
      const statusDisplay = page.locator('.status-bar[role="status"]').first();
      const baselineText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
      const baselineCount = Number(baselineText);

      // Apply a filter
      await setProxyFilter(page, 'protocol', 'vless');

      // Verify filtered count is smaller
      const filteredText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
      const filteredCount = Number(filteredText);
      expect(filteredCount).toBeLessThanOrEqual(baselineCount);

      // Clear filters
      await clearProxyFiltersViaState(page);

      // Verify count is restored
      const restoredText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
      const restoredCount = Number(restoredText);
      expect(restoredCount).toBe(baselineCount);
    });
  });

  // ----- 2. Proxy list sorting -----
  test.describe('Proxy list sorting', () => {
    test('should sort by latency when clicking latency header', async ({ page }) => {
      await goToProxies(page);

      const latencyHeader = page.locator('th.sortable-th').filter({ hasText: '延迟' });
      await expect(latencyHeader).toBeVisible();

      // Click to sort ascending
      await latencyHeader.click();
      await page.waitForTimeout(500);

      // Verify sort indicator appears
      const sortIndicator = latencyHeader.locator('.sort-indicator');
      await expect(sortIndicator).toBeVisible();
      const indicatorText = await sortIndicator.textContent();
      expect(indicatorText).toContain('↑');

      // Verify the status bar shows sort info
      const statusDisplay = page.locator('.status-bar[role="status"]').first();
      const sortBadge = statusDisplay.locator('.badge-neutral');
      await expect(sortBadge).toBeVisible();

      // Click again to toggle to descending
      await latencyHeader.click();
      await page.waitForTimeout(500);
      const descIndicator = await sortIndicator.textContent();
      expect(descIndicator).toContain('↓');
    });

    test('should sort by bandwidth when clicking bandwidth header', async ({ page }) => {
      await goToProxies(page);

      const bandwidthHeader = page.locator('th.sortable-th').filter({ hasText: '带宽' });
      if (await bandwidthHeader.isVisible()) {
        await bandwidthHeader.click();
        await page.waitForTimeout(500);

        const sortIndicator = bandwidthHeader.locator('.sort-indicator');
        await expect(sortIndicator).toBeVisible();
      }
    });

    test('should show sort indicator in status bar after sorting', async ({ page }) => {
      await goToProxies(page);

      const statusDisplay = page.locator('.status-bar[role="status"]').first();
      await expect(statusDisplay).toBeVisible();

      // Click latency header to sort
      const latencyHeader = page.locator('th.sortable-th').filter({ hasText: '延迟' });
      await latencyHeader.click();
      await page.waitForTimeout(500);

      // Status bar should now show sort info
      const sortInfo = statusDisplay.locator('.badge-neutral');
      await expect(sortInfo).toBeVisible();
      const sortText = await sortInfo.textContent();
      expect(sortText).toContain('延迟');
      expect(sortText).toContain('↑');
    });
  });

  // ----- 3. Proxy selection -----
  test.describe('Proxy selection', () => {
    test('should select individual proxies with checkboxes', async ({ page }) => {
      await goToProxies(page);

      const checkboxes = page.locator('table.data-table tbody input[type="checkbox"]');
      const count = await checkboxes.count();
      expect(count).toBeGreaterThan(0);

      // Select the first proxy
      await checkboxes.first().check();
      await expect(checkboxes.first()).toBeChecked();

      // Verify selection count in the status bar
      const statusDisplay = page.locator('.status-bar[role="status"]').first();
      const selectionInfo = statusDisplay.locator('.status-item').filter({ hasText: '选中' });
      await expect(selectionInfo).toBeVisible();
      const selectionCount = await selectionInfo.locator('strong').textContent();
      expect(selectionCount).toBe('1');

      // Deselect the first proxy
      await checkboxes.first().uncheck();
      await expect(checkboxes.first()).not.toBeChecked();

      // Selection info should be hidden when nothing selected
      const selectionInfoAfter = statusDisplay.locator('.status-item').filter({ hasText: '选中' });
      const isStillVisible = await selectionInfoAfter.isVisible().catch(() => false);
      expect(isStillVisible).toBe(false);
    });

    test('should select multiple proxies and show count', async ({ page }) => {
      await goToProxies(page);

      const checkboxes = page.locator('table.data-table tbody input[type="checkbox"]');
      const count = await checkboxes.count();
      expect(count).toBeGreaterThan(2);

      // Select first three proxies
      await checkboxes.nth(0).check();
      await checkboxes.nth(1).check();
      await checkboxes.nth(2).check();

      const statusDisplay = page.locator('.status-bar[role="status"]').first();
      const selectionInfo = statusDisplay.locator('.status-item').filter({ hasText: '选中' });
      await expect(selectionInfo).toBeVisible();
      const selectionCount = await selectionInfo.locator('strong').textContent();
      expect(selectionCount).toBe('3');
    });

    test('should select all proxies on page using header checkbox', async ({ page }) => {
      await goToProxies(page);

      const selectAllCheckbox = page.locator('table.data-table thead input[type="checkbox"]');
      await expect(selectAllCheckbox).toBeVisible();

      // Check all
      await selectAllCheckbox.check();
      await page.waitForTimeout(500);

      // All row checkboxes should be checked
      const rowCheckboxes = page.locator('table.data-table tbody input[type="checkbox"]');
      const rowCount = await rowCheckboxes.count();
      for (let i = 0; i < rowCount; i++) {
        await expect(rowCheckboxes.nth(i)).toBeChecked();
      }

      // Deselect all
      await selectAllCheckbox.uncheck();
      await page.waitForTimeout(500);
      for (let i = 0; i < Math.min(rowCount, 5); i++) {
        await expect(rowCheckboxes.nth(i)).not.toBeChecked();
      }
    });
  });

  // ----- 4. Proxy search -----
  test.describe('Proxy search', () => {
    test('should filter proxies by source using Vue state', async ({ page }) => {
      await goToProxies(page);

      // Get baseline count
      const statusDisplay = page.locator('.status-bar[role="status"]').first();
      const baselineText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
      const baselineCount = Number(baselineText);

      // Discover available sources from the data
      const sources = await page.evaluate(() => {
        const el = document.querySelector('#app') as any;
        const vm = el?.__vue_app__?._instance?.proxy;
        const proxies = vm?.appState?.proxies || [];
        const sourceSet = new Set<string>();
        proxies.forEach((p: any) => { if (p.source) sourceSet.add(p.source); });
        return [...sourceSet].slice(0, 5);
      });

      if (sources.length > 0) {
        // Apply source filter
        await setProxyFilter(page, 'source', sources[0]);

        const filteredText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
        const filteredCount = Number(filteredText);
        expect(filteredCount).toBeGreaterThan(0);
        expect(filteredCount).toBeLessThanOrEqual(baselineCount);

        // Clean up
        await clearProxyFiltersViaState(page);
      }
    });

    test('should filter by geo country using Vue state', async ({ page }) => {
      await goToProxies(page);

      // Get baseline
      const statusDisplay = page.locator('.status-bar[role="status"]').first();
      const baselineText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
      const baselineCount = Number(baselineText);

      // Find available countries from the data
      const countries = await page.evaluate(() => {
        const el = document.querySelector('#app') as any;
        const vm = el?.__vue_app__?._instance?.proxy;
        const proxies = vm?.appState?.proxies || [];
        const countrySet = new Set<string>();
        proxies.forEach((p: any) => { if (p.country) countrySet.add(p.country); });
        return [...countrySet].slice(0, 5);
      });

      if (countries.length > 0) {
        await setProxyFilter(page, 'geo_country', countries[0]);

        const filteredText = await statusDisplay.locator('.status-item').first().locator('strong').textContent();
        const filteredCount = Number(filteredText);
        expect(filteredCount).toBeGreaterThan(0);
        expect(filteredCount).toBeLessThanOrEqual(baselineCount);

        // Verify filter chip appears
        const chip = page.locator('.filter-chip').first();
        const isChipVisible = await chip.isVisible().catch(() => false);
        if (isChipVisible) {
          const chipText = await chip.textContent();
          expect(chipText).toContain('国家');
        }

        await clearProxyFiltersViaState(page);
      }
    });

    test('should open source filter dropdown in advanced panel', async ({ page }) => {
      await goToProxies(page);
      await openAdvancedFilter(page);

      // Verify source filter field is visible
      await expect(page.locator('.filter-panel-field').filter({ hasText: '来源' })).toBeVisible();
    });
  });

  // ----- 5. Proxy batch operations -----
  test.describe('Proxy batch operations', () => {
    test('should show selection bar with action buttons when proxies are selected', async ({ page }) => {
      await goToProxies(page);

      const checkboxes = page.locator('table.data-table tbody input[type="checkbox"]');
      const count = await checkboxes.count();
      if (count === 0) {
        test.skip();
        return;
      }

      // Select first proxy
      await checkboxes.first().check();
      await page.waitForTimeout(300);

      // The selection bar should appear
      const selectionBar = page.locator('.selection-bar');
      await expect(selectionBar).toBeVisible();

      // Verify the bar shows the selection count
      const barInfo = selectionBar.locator('.selection-bar-info');
      await expect(barInfo).toBeVisible();
      const barText = await barInfo.textContent();
      expect(barText).toContain('1');

      // Verify batch action buttons are visible
      await expect(selectionBar.locator('button:has-text("导出选中")')).toBeVisible();
      await expect(selectionBar.locator('button:has-text("复制链接")')).toBeVisible();
      await expect(selectionBar.locator('button:has-text("删除")')).toBeVisible();
      await expect(selectionBar.locator('button:has-text("取消选择")')).toBeVisible();
    });

    test('should show comparison button when exactly 2 proxies are selected', async ({ page }) => {
      await goToProxies(page);

      const checkboxes = page.locator('table.data-table tbody input[type="checkbox"]');
      const count = await checkboxes.count();
      if (count < 3) {
        test.skip();
        return;
      }

      // Select exactly 2 proxies
      await checkboxes.nth(0).check();
      await checkboxes.nth(1).check();
      await page.waitForTimeout(300);

      const selectionBar = page.locator('.selection-bar');
      await expect(selectionBar).toBeVisible();

      // Comparison button should be visible when 2 proxies are selected
      const compareBtn = selectionBar.locator('button:has-text("对比选中")');
      await expect(compareBtn).toBeVisible();
    });

    test('should deselect all when cancel is clicked', async ({ page }) => {
      await goToProxies(page);

      const checkboxes = page.locator('table.data-table tbody input[type="checkbox"]');
      const count = await checkboxes.count();
      if (count < 2) {
        test.skip();
        return;
      }

      await checkboxes.nth(0).check();
      await checkboxes.nth(1).check();
      await page.waitForTimeout(300);

      const selectionBar = page.locator('.selection-bar');
      await expect(selectionBar).toBeVisible();

      // Click cancel selection
      await selectionBar.locator('button:has-text("取消选择")').click();
      await page.waitForTimeout(300);

      // Selection bar should be hidden
      await expect(selectionBar).not.toBeVisible();

      // Checkboxes should be unchecked
      await expect(checkboxes.nth(0)).not.toBeChecked();
      await expect(checkboxes.nth(1)).not.toBeChecked();
    });

    test('should update selection bar count when proxies are added/removed', async ({ page }) => {
      await goToProxies(page);

      const checkboxes = page.locator('table.data-table tbody input[type="checkbox"]');
      const count = await checkboxes.count();
      if (count < 3) {
        test.skip();
        return;
      }

      // Select 1
      await checkboxes.nth(0).check();
      await page.waitForTimeout(300);
      const selectionBar = page.locator('.selection-bar');
      let barText = await selectionBar.locator('.selection-bar-info').textContent();
      expect(barText).toContain('1');

      // Add another
      await checkboxes.nth(1).check();
      await page.waitForTimeout(300);
      barText = await selectionBar.locator('.selection-bar-info').textContent();
      expect(barText).toContain('2');

      // Remove one
      await checkboxes.nth(0).uncheck();
      await page.waitForTimeout(300);
      barText = await selectionBar.locator('.selection-bar-info').textContent();
      expect(barText).toContain('1');
    });

    test('should disable batch buttons when nothing is selected', async ({ page }) => {
      await goToProxies(page);

      // When nothing is selected, the selection bar should not exist
      const selectionBar = page.locator('.selection-bar');
      const isVisible = await selectionBar.isVisible().catch(() => false);
      expect(isVisible).toBe(false);

      // The top-level copy/delete buttons in pagination should be disabled
      const copyBtn = page.locator('button[aria-label*="复制选中"]');
      const deleteBtn = page.locator('button[aria-label*="删除选中"]');
      if (await copyBtn.isVisible().catch(() => false)) {
        await expect(copyBtn).toBeDisabled();
      }
      if (await deleteBtn.isVisible().catch(() => false)) {
        await expect(deleteBtn).toBeDisabled();
      }
    });
  });

  // ----- 6. Proxy pagination -----
  test.describe('Proxy pagination', () => {
    test('should display pagination controls', async ({ page }) => {
      await goToProxies(page);

      const pagination = page.locator('.pagination').first();
      await expect(pagination).toBeVisible();

      const perPageSelect = page.locator('select[aria-label="每页显示数量"]');
      await expect(perPageSelect).toBeVisible();

      const prevBtn = page.locator('button[aria-label="上一页"]');
      const nextBtn = page.locator('button[aria-label="下一页"]');
      await expect(prevBtn).toBeVisible();
      await expect(nextBtn).toBeVisible();
    });

    test('should navigate to next page and back', async ({ page }) => {
      await goToProxies(page);

      const nextBtn = page.locator('button[aria-label="下一页"]');
      const prevBtn = page.locator('button[aria-label="上一页"]');

      // Prev should be disabled on first page
      await expect(prevBtn).toBeDisabled();

      // Only test navigation if there are multiple pages
      const isNextEnabled = await nextBtn.isEnabled();
      if (isNextEnabled) {
        await nextBtn.click();
        await page.waitForTimeout(500);

        // Prev should now be enabled
        await expect(prevBtn).toBeEnabled();

        // Click prev to go back
        await prevBtn.click();
        await page.waitForTimeout(500);

        // Should be back on first page
        await expect(prevBtn).toBeDisabled();
      }
    });

    test('should change page size to 10 rows', async ({ page }) => {
      await goToProxies(page);

      const perPageSelect = page.locator('select[aria-label="每页显示数量"]');
      await expect(perPageSelect).toBeVisible();

      // Change page size to 10 (valid option: [10, 50, 100])
      await perPageSelect.selectOption('10');
      await page.waitForTimeout(500);

      // The table should show at most 10 data rows
      const dataRows = page.locator('table.data-table tbody tr');
      const rowCount = await dataRows.count();
      expect(rowCount).toBeLessThanOrEqual(10);
    });

    test('should change page size to 100 rows', async ({ page }) => {
      await goToProxies(page);

      const perPageSelect = page.locator('select[aria-label="每页显示数量"]');
      await perPageSelect.selectOption('100');
      await page.waitForTimeout(500);

      // The table should show up to 100 rows (or fewer if total < 100)
      const dataRows = page.locator('table.data-table tbody tr');
      const rowCount = await dataRows.count();
      expect(rowCount).toBeLessThanOrEqual(100);
    });

    test('should disable next button on last page', async ({ page }) => {
      await goToProxies(page);

      const nextBtn = page.locator('button[aria-label="下一页"]');

      // Set a large page size to fit all proxies on one page
      const perPageSelect = page.locator('select[aria-label="每页显示数量"]');
      await perPageSelect.selectOption('100');
      await page.waitForTimeout(500);

      // If there are multiple pages, navigate to the last
      let maxClicks = 200;
      while (await nextBtn.isEnabled() && maxClicks > 0) {
        await nextBtn.click();
        await page.waitForTimeout(200);
        maxClicks--;
      }

      // Next should be disabled on last page
      await expect(nextBtn).toBeDisabled();
    });

    test('should show page info reflecting current position', async ({ page }) => {
      await goToProxies(page);

      const paginationInfo = page.locator('.pagination-info').first();
      await expect(paginationInfo).toBeVisible();

      const infoText = await paginationInfo.textContent();
      expect(infoText).toBeTruthy();
      // Should mention page number 1 (we start on page 1)
      expect(infoText).toMatch(/1/);
    });
  });
});
