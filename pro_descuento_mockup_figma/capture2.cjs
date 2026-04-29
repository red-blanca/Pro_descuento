const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1200 } });
  const captureId = process.argv[2];
  const endpoint = process.argv[3];
  const url = process.argv[4];
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  console.log('status', resp && resp.status());
  await page.waitForTimeout(5000);
  await page.screenshot({ path: 'C:/Users/rza_w/Documents/Pro_descuento/pro_descuento_mockup_figma/capture_detailed.png', fullPage: true });
  const ok = await page.evaluate(() => !!(window.figma && window.figma.captureForDesign));
  console.log('captureFn', ok);
  await browser.close();
})();
