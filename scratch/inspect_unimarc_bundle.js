const { chromium } = require('playwright')

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  await page.goto('https://www.unimarc.cl/category/bebidas-y-licores/bebidas', { waitUntil: 'domcontentloaded', timeout: 45000 })
  const scripts = await page.evaluate(() => [...document.scripts].map((script) => script.src).filter(Boolean))
  const output = []
  for (const url of scripts) {
    if (!url.includes('/_next/static/')) continue
    const text = await page.evaluate(async (scriptUrl) => (await fetch(scriptUrl)).text(), url)
    for (const pattern of ['catalog/product/search', 'product/search', 'fullText', 'promotionsOnly']) {
      let index = text.indexOf(pattern)
      while (index >= 0) {
        output.push({ url, pattern, sample: text.slice(Math.max(0, index - 700), index + 1400) })
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
