const { chromium } = require('playwright')

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ locale: 'es-CL' })
  const requests = []

  page.on('request', (request) => {
    const url = request.url()
    if (url.includes('alvi.cl') && (url.includes('product') || url.includes('search') || url.includes('busca'))) {
      requests.push({ method: request.method(), url, body: request.postData() })
    }
  })

  await page.goto('https://www.alvi.cl', { waitUntil: 'domcontentloaded', timeout: 45000 })
  const inputs = await page.locator('input').evaluateAll((nodes) =>
    nodes.map((node) => ({
      placeholder: node.placeholder,
      type: node.type,
      name: node.name,
      ariaLabel: node.getAttribute('aria-label'),
    })),
  )
  console.error(JSON.stringify({ inputs }, null, 2))

  const search = page.locator('input').filter({ has: undefined }).first()
  const candidate = page.locator('input[placeholder*="Busca" i], input[placeholder*="Qué" i], input[type="search"]').first()
  if (await candidate.count()) {
    await candidate.fill('arroz')
    await candidate.press('Enter')
    await page.waitForTimeout(8000)
  } else {
    console.error('No search input found')
  }

  console.log(JSON.stringify({ finalUrl: page.url(), requests }, null, 2))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
