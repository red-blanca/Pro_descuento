const { chromium } = require('playwright')

const urls = [
  'https://www.santaisabel.cl/lacteos-y-quesos/leches/leche-liquida',
  'https://www.santaisabel.cl/bebidas-aguas-y-jugos/bebidas-gaseosas',
]

async function capture(browser, url) {
  const context = await browser.newContext({ locale: 'es-CL', timezoneId: 'America/Santiago' })
  const page = await context.newPage()
  let captured = null

  page.on('response', async (response) => {
    const request = response.request()
    if (captured || request.method() !== 'POST' || !request.url().includes('bff.santaisabel.cl/catalog/plp')) return
    captured = {
      status: response.status(),
      url: request.url(),
      headers: await request.allHeaders(),
      body: request.postDataJSON(),
    }
  })

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForTimeout(10000)
  await context.close()
  return captured
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const captures = []
  for (const url of urls) captures.push(await capture(browser, url))
  await browser.close()
  console.log(JSON.stringify(captures, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
