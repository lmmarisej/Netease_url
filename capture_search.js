const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    // 1. 登录
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button:has-text("登")');
    await page.waitForNavigation();
    await page.waitForTimeout(1000);

    // 2. 进入音乐搜索
    await page.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);

    // 3. 输入歌曲名，用回车触发搜索
    const input = page.locator('input[placeholder="输入歌曲名、歌手名..."]');
    await input.fill('晴天');
    await input.press('Enter');

    // 4. 等待搜索结果出现（最多等 15 秒）
    await page.waitForSelector('.v-list-item, .v-table, .v-card-item', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);

    // 5. 截图
    const out = path.join(__dirname, 'screenshots', '01_音乐搜索.png');
    await page.screenshot({ path: out, fullPage: true });
    console.log('Saved:', out);
  } catch (e) {
    console.error('Error:', e);
  } finally {
    await browser.close();
  }
})();
