const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: 3 });
  const file = 'file://' + path.resolve(__dirname, 'diagram.html');
  await page.goto(file);
  await page.waitForSelector('#wrap svg', { timeout: 15000 });
  await page.waitForTimeout(300);
  const el = await page.$('#wrap');
  await el.screenshot({ path: path.resolve(__dirname, 'architektur.png') });
  await browser.close();
  console.log('done');
})().catch((e) => { console.error(e); process.exit(1); });
