const { chromium } = require('playwright')

const defaultTargets = [
  { id: 'jumbo', url: 'https://www.jumbo.cl/lacteos-y-quesos/leches' },
  { id: 'santaisabel', url: 'https://www.santaisabel.cl/lacteos-y-quesos/leches' },
  { id: 'unimarc', url: 'https://www.unimarc.cl/category/bebidas-y-licores/bebidas' },
  { id: 'alvi', url: 'https://www.alvi.cl/category/despensa' },
  { id: 'lider', url: 'https://www.lider.cl/supermercado/category/despensa' },
  { id: 'acuenta', url: 'https://www.acuenta.cl/category/despensa' },
  { id: 'tottus', url: 'https://www.tottus.cl/tottus-cl/category/despensa' },
]
const targets = process.argv.length > 2
  ? process.argv.slice(2).map((url, index) => ({ id: `arg${index + 1}`, url }))
  : defaultTargets

const interesting = /(api|graphql|search|browse|product|catalog|category|plp|constructor|cnstrc|commerce|falabella|walmart|lider|acuenta|tottus|jumbo|unimarc|santaisabel|alvi)/i

async function inspectTarget(browser, target) {
  const context = await browser.newContext({
    locale: 'es-CL',
    timezoneId: 'America/Santiago',
    viewport: { width: 1440, height: 1000 },
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
  })
  const page = await context.newPage()
  const rows = []

  page.on('response', async (response) => {
    const request = response.request()
    const url = response.url()
    const type = request.resourceType()
    if (!interesting.test(url) && !['xhr', 'fetch'].includes(type)) return
    const headers = response.headers()
    const contentType = headers['content-type'] || ''
    const row = {
      type,
      status: response.status(),
      method: request.method(),
      url,
      contentType,
      postData: request.postData() || '',
      sample: '',
    }
    if (/json|javascript|text|html/i.test(contentType) && ['xhr', 'fetch', 'document'].includes(type)) {
      try {
        const text = await response.text()
        row.sample = text.slice(0, 500).replace(/\s+/g, ' ')
      } catch {
        row.sample = ''
      }
    }
    rows.push(row)
  })

  let loaded = false
  try {
    await page.goto(target.url, { waitUntil: 'domcontentloaded', timeout: 45000 })
    loaded = true
    await page.waitForTimeout(8000)
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight * 0.6)).catch(() => {})
    await page.waitForTimeout(3000)
  } catch (error) {
    rows.push({ type: 'navigation_error', status: 0, method: 'GET', url: target.url, contentType: '', sample: String(error.message || error) })
  }

  const pageInfo = loaded
    ? await page.evaluate(() => {
        const text = document.documentElement.innerHTML
        const reactQuery = document.querySelector('#__REACT_QUERY_STATE__')?.textContent || ''
        const scripts = [...document.scripts].map((script) => script.src).filter(Boolean).slice(0, 30)
        const links = [...document.querySelectorAll('a[href]')]
          .map((a) => a.href)
          .filter((href) => /category|categoria|despensa|lacteos|bebidas|search|busca/i.test(href))
          .slice(0, 40)
        return {
          title: document.title,
          url: location.href,
          htmlLength: text.length,
          reactQueryLength: reactQuery.length,
          productIdCount: (text.match(/productId/g) || []).length,
          priceCount: (text.match(/price/g) || []).length,
          scripts,
          links,
        }
      })
    : {}

  await context.close()
  return { target, pageInfo, rows }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const out = []
  for (const target of targets) {
    console.error(`Inspecting ${target.id} ${target.url}`)
    out.push(await inspectTarget(browser, target))
  }
  await browser.close()
  console.log(JSON.stringify(out, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
