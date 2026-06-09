const { chromium } = require('playwright')

async function inspect(url, searchTerm = '') {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ locale: 'es-CL', timezoneId: 'America/Santiago' })
  const page = await context.newPage()
  const rows = []

  page.on('response', async (response) => {
    const request = response.request()
    const requestUrl = response.url()
    if (!/unimarc|smu|product|search|catalog|category|graphql|api/i.test(requestUrl)) return
    const headers = request.headers()
    const requestBody = request.postData() || ''
    let body = ''
    try {
      body = await response.text()
    } catch {}
    rows.push({
      status: response.status(),
      method: request.method(),
      type: request.resourceType(),
      url: requestUrl,
      headers,
      requestBody,
      responseBody: body.slice(0, 5000),
    })
  })

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForTimeout(7000)
  const inputs = await page.locator('input').evaluateAll((nodes) =>
    nodes.map((node) => ({ placeholder: node.placeholder, type: node.type, aria: node.getAttribute('aria-label') })),
  )
  if (searchTerm) {
    const input = page.locator('input[placeholder*="buscar" i], input[placeholder*="busca" i], input[type="search"]').first()
    if (await input.count()) {
      await input.fill(searchTerm)
      await input.press('Enter')
      await page.waitForTimeout(8000)
    }
  }
  const links = await page.locator('a[href]').evaluateAll((nodes) =>
    nodes.map((a) => ({ href: a.href, text: (a.textContent || '').replace(/\s+/g, ' ').trim() }))
      .filter((item) => /category|categoria|bebida|lacteo|despensa|limpieza/i.test(item.href + item.text))
      .slice(0, 80),
  )
  await page.waitForTimeout(1000)
  const result = { initialUrl: url, finalUrl: page.url(), inputs, links, rows }
  await context.close()
  await browser.close()
  return result
}

async function main() {
  console.log(JSON.stringify(await inspect(process.argv[2] || 'https://www.unimarc.cl', process.argv[3] || ''), null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
