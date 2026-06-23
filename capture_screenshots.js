const playwright = require('playwright');
const path = require('path');
const fs = require('fs');

const screenshotDir = path.join(__dirname, 'screenshots');

const pages = [
  { name: '01_音乐搜索', url: '/' },
  { name: '02_歌词查询', url: '/lyrics' },
  { name: '03_文件管理', url: '/files' },
  { name: '04_歌单同步', url: '/sync' },
  { name: '05_配置', url: '/config' },
  { name: '06_消息推送', url: '/magicpush' },
  { name: '07_任务管理', url: '/tasks' },
  { name: '08_运行日志', url: '/logs' },
  { name: '09_API文档', url: '/api-docs' }
];

(async () => {
  const browser = await playwright.chromium.launch();
  const page = await browser.newPage();

  try {
    // 登录
    console.log('Logging in...');
    await page.goto('http://localhost:3000/login');
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button:has-text("登")');
    await page.waitForNavigation();
    await page.waitForTimeout(1000);

    // 为每个页面截图
    for (const pageConfig of pages) {
      console.log(`Capturing: ${pageConfig.name}`);
      await page.goto(`http://localhost:3000${pageConfig.url}`);
      await page.waitForTimeout(1500);
      
      const screenshotPath = path.join(screenshotDir, `${pageConfig.name}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log(`✓ Saved: ${screenshotPath}`);
    }

    console.log('\n✅ All screenshots saved successfully!');
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await browser.close();
  }
})();
