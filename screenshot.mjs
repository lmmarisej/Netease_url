import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const BASE_URL = 'http://localhost:3000';
const SCREENSHOT_DIR = './screenshots';
const USERNAME = 'admin';
const PASSWORD = 'admin123';

// 只截取有问题的那几页
const pages = [
  { path: '/sync', name: 'sync' },
  { path: '/api-docs', name: 'api-docs' },
];

mkdirSync(SCREENSHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();

// Track network fails
const failedReqs = [];
page.on('response', resp => { if (resp.status() >= 400) failedReqs.push(`${resp.status()} ${resp.url()}`); });

// Step 1: Login
console.log('=== Login ===');
await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 20000 });
await page.waitForTimeout(1500);

await page.fill('input[placeholder="请输入用户名"]', USERNAME);
await page.fill('input[placeholder="请输入密码"]', PASSWORD);
await page.click('button[type="submit"]');

await page.waitForFunction((lp) => !window.location.pathname.includes(lp), '/login', { timeout: 10000 });
await page.waitForTimeout(3000);

const token = await page.evaluate(() => localStorage.getItem('token'));
console.log(`Token: ${token ? 'YES' : 'NO'}`);
if (!token) { console.error('No token!'); await browser.close(); process.exit(1); }

// Step 2: First visit home to get fresh JS chunk references
console.log('--- visiting home to refresh cache ---');
await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle', timeout: 20000 });
await page.waitForTimeout(2000);
failedReqs.length = 0;

// Step 3: Screenshot
for (const { path, name } of pages) {
  console.log(`--- ${name} (${path}) ---`);
  failedReqs.length = 0; // reset
  try {
    await page.goto(`${BASE_URL}${path}`, { waitUntil: 'networkidle', timeout: 20000 });
    await page.waitForTimeout(5000);

    // Log failed requests
    if (failedReqs.length > 0) {
      console.log(`  Failed (${failedReqs.length}):`);
      failedReqs.forEach(r => console.log(`    ${r}`));
    }

    // Check if Vue mounted
    const appContent = await page.evaluate(() => {
      const app = document.querySelector('#app');
      return app ? app.children.length + ' children, text: ' + app.innerText.substring(0, 100) : 'NO #APP';
    });
    console.log(`  #app: ${appContent}`);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/${name}.png`, fullPage: false });
    console.log(`  -> ${name}.png saved`);
  } catch (e) {
    console.error(`  FAILED: ${e.message}`);
  }
}

await browser.close();
console.log('=== Done ===');


