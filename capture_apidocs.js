const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    // 登录
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button:has-text("登")');
    await page.waitForNavigation();
    await page.waitForTimeout(1000);

    // 截图 API 文档页
    await page.goto('http://localhost:3000/api-docs', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    const out = path.join(__dirname, 'screenshots', '09_API文档.png');
    await page.screenshot({ path: out, fullPage: true });
    console.log('Saved:', out);
  } catch (e) {
    console.error('Error:', e);
  } finally {
    await browser.close();
  }
})();
