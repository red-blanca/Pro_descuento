const { chromium } = require('playwright')

async function main() {
  const category = process.env.ALVI_CATEGORY === '__none__' ? '' : (process.env.ALVI_CATEGORY || 'bebidas')
  const query = process.env.ALVI_QUERY || ''
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

  const jumbo = page.getByText('Jumbo', { exact: true }).locator('..')
  const alvi = page.getByText('Alvi', { exact: true }).locator('..')
  await jumbo.getByRole('checkbox').uncheck()
  await alvi.getByRole('checkbox').check()
  if (category) await alvi.locator('..').getByRole('combobox').selectOption(category)
  if (query) await page.getByPlaceholder('Palabra clave opcional si eliges categoria').fill(query)

  await page.getByRole('button', { name: 'Buscar en supermercados' }).click()
  await page.locator('article h3').first().waitFor({ timeout: 60000 })

  const titles = await page.locator('article h3').allTextContents()
  console.log(JSON.stringify({ searchPayload, count: titles.length, titles: titles.slice(0, 8) }, null, 2))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
