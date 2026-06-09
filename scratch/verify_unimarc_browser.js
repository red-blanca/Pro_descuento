const { chromium } = require('playwright')

async function main() {
  const query = process.env.UNIMARC_QUERY === '__none__' ? '' : (process.env.UNIMARC_QUERY || 'arroz')
  const category = process.env.UNIMARC_CATEGORY || ''
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  let searchPayload = null

  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/global-search')) {
      searchPayload = request.postDataJSON()
    }
  })

  await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Supermercados' }).click()
  await page.getByText('Jumbo', { exact: true }).locator('..').getByRole('checkbox').uncheck()
  const unimarc = page.getByText('Unimarc', { exact: true }).locator('..')
  await unimarc.getByRole('checkbox').check()
  if (category) await unimarc.locator('..').getByRole('combobox').selectOption(category)
  if (query) await page.getByPlaceholder('Palabra clave opcional si eliges categoria').fill(query)
  await page.getByRole('button', { name: 'Buscar en supermercados' }).click()
  await page.locator('article h3').first().waitFor({ timeout: 60000 })

  const titles = await page.locator('article h3').allTextContents()
  const prices = await page.locator('article .text-xl').allTextContents()
  console.log(JSON.stringify({ searchPayload, count: titles.length, titles: titles.slice(0, 6), prices: prices.slice(0, 6) }, null, 2))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
