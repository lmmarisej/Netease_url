const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    const out = path.join(__dirname, 'screenshots', 'login.png');
    await page.screenshot({ path: out, fullPage: true });
    console.log('Saved:', out);
  } catch (e) {
    console.error('Error:', e);
  } finally {
    await browser.close();
  }
})();
