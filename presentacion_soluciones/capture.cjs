const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1650, height: 5000 } });
  const url = process.argv[2];
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  console.log('status', resp ? resp.status() : 'no');
  await page.waitForTimeout(7000);
  await page.screenshot({ path: 'C:/Users/rza_w/Documents/Pro_descuento/presentacion_soluciones/presentacion_capture.png', fullPage: true });
  const hasCapture = await page.evaluate(() => !!(window.figma && window.figma.captureForDesign));
  console.log('captureFn', hasCapture);
  await browser.close();
})();
