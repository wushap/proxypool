import { test, expect } from '@playwright/test';

test('verify main pages', async ({ page }) => {
  // 1. Dashboard
  await page.goto('/');
  await expect(page).toHaveTitle(/Proxy.*Pool/i);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'test-results/verify/dashboard.png', fullPage: true });
  console.log('Dashboard screenshot taken');

  // 2. Check for console errors
  const errors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });

  // 3. Navigate to key pages via sidebar links
  const navLinks = await page.locator('nav a, .sidebar a, [role="navigation"] a').all();
  console.log(`Found ${navLinks.length} nav links`);

  // Try clicking through sidebar items
  for (const link of navLinks.slice(0, 6)) {
    const text = await link.textContent();
    const href = await link.getAttribute('href');
    if (href && href !== '#' && !href.startsWith('http')) {
      try {
        await link.click();
        await page.waitForTimeout(1500);
        const name = (text || 'unknown').trim().replace(/\s+/g, '_').substring(0, 20);
        await page.screenshot({ path: `test-results/verify/page_${name}.png`, fullPage: true });
        console.log(`Page "${text?.trim()}" screenshot taken`);
      } catch (e) {
        console.log(`Failed to navigate to "${text?.trim()}": ${e}`);
      }
    }
  }

  if (errors.length > 0) {
    console.log('Console errors found:', errors);
  }
});
