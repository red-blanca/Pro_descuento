const { chromium } = require('playwright')

async function inspect(url, searchTerm = '') {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ locale: 'es-CL', timezoneId: 'America/Santiago' })
  const page = await context.newPage()
  const calls = []

  page.on('response', async (response) => {
    if (!response.url().includes('nextgentheadless.instaleap.io/api/')) return
    const request = response.request()
    let responseBody = ''
    try {
      responseBody = await response.text()
    } catch {}
    calls.push({
      status: response.status(),
      url: response.url(),
      headers: await request.allHeaders(),
      requestBody: request.postData(),
      responseBody,
    })
  })

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForTimeout(6000)
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

  const html = await page.content()
  const productSignals = await page.evaluate(() => ({
    links: [...document.querySelectorAll('a[href*="/p/"], a[href*="/product"], a[href*="/producto"]')].slice(0, 20).map((a) => ({
      href: a.href,
      text: (a.textContent || '').replace(/\s+/g, ' ').trim(),
    })),
    buttons: [...document.querySelectorAll('button')].filter((button) => /agregar/i.test(button.textContent || '')).slice(0, 20).map((button) => ({
      text: (button.textContent || '').replace(/\s+/g, ' ').trim(),
      parent: (button.parentElement?.parentElement?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 500),
    })),
  }))
  const result = { initialUrl: url, finalUrl: page.url(), inputs, calls, html, productSignals }
  await context.close()
  await browser.close()
  return result
}

async function main() {
  const url = process.argv[2] || 'https://www.acuenta.cl/ca/bebidas-y-snacks/02'
  const searchTerm = process.argv[3] || ''
  console.log(JSON.stringify(await inspect(url, searchTerm), null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
