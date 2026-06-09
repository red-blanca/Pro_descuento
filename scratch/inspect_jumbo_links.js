const { chromium } = require('playwright')

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ locale: 'es-CL' })
  await page.goto(process.env.INSPECT_URL || 'https://www.jumbo.cl', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForTimeout(5000)
  const links = await page.locator('a[href]').evaluateAll((nodes) =>
    nodes.map((node) => ({
      text: (node.textContent || '').replace(/\s+/g, ' ').trim(),
      href: node.href,
      aria: node.getAttribute('aria-label') || '',
    })),
  )
  const unique = [...new Map(links.map((link) => [link.href, link])).values()]
  console.log(JSON.stringify(unique, null, 2))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
