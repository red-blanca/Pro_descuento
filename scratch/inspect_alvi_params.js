const { chromium } = require('playwright')

async function main() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    locale: 'es-CL',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
  })
  const page = await context.newPage()
  await page.goto('https://www.alvi.cl/category/bebidas', { waitUntil: 'domcontentloaded', timeout: 45000 })
  const scriptUrls = await page.evaluate(() => [...document.scripts].map((script) => script.src).filter(Boolean))
  const output = []
  for (const url of scriptUrls) {
    if (!url.includes('/_next/static/chunks/')) continue
    const text = await page.evaluate(async (scriptUrl) => (await fetch(scriptUrl)).text(), url)
    for (const pattern of ['intelligence-search-plp', 'hideUnavailableItems', 'fq=', 'categoryData.fq', 'selectedFacets']) {
      let index = text.indexOf(pattern)
      while (index >= 0) {
        output.push({ url, pattern, sample: text.slice(Math.max(0, index - 500), index + 900) })
        index = text.indexOf(pattern, index + pattern.length)
      }
    }
  }
  console.log(JSON.stringify(output, null, 2))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
