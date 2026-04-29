const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });

  const captureId = 'e2257eea-4411-4ac5-9fd9-7b90f1614fa6';
  const encoded = 'https%3A%2F%2Fmcp.figma.com%2Fmcp%2Fcapture%2Fe2257eea-4411-4ac5-9fd9-7b90f1614fa6%2Fsubmit';
  const url = `http://127.0.0.1:4174/#figmacapture=${captureId}&figmaendpoint=${encoded}&figmadelay=1200`;

  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    console.log('status', resp ? resp.status() : 'no-response');
    await page.waitForTimeout(5000);
    await page.screenshot({ path: 'C:\\Users\\rza_w\\Documents\\Pro_descuento\\pro_descuento_mockup_figma\\capture_playwright.png', fullPage: true });
    const captured = await page.evaluate(() => {
      return !!(window.figma && typeof window.figma.captureForDesign === 'function');
    });
    console.log('captureFn', captured);
  } catch (err) {
    console.error(err);
  } finally {
    await browser.close();
  }
})();
