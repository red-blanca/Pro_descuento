import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ExternalLink, Loader2, Search, ShoppingBasket } from 'lucide-react'

const SUPERMARKET_SOURCES = [
  { id: 'jumbo', label: 'Jumbo' },
  { id: 'santaisabel', label: 'Santa Isabel' },
  { id: 'unimarc', label: 'Unimarc' },
  { id: 'alvi', label: 'Alvi' },
  { id: 'lider', label: 'Lider' },
  { id: 'acuenta', label: 'acuenta' },
  { id: 'tottus', label: 'Tottus' },
]

function flattenResults(data) {
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data?.results)) return data.results
  const out = []
  const groups = data?.results || data?.sources || data?.by_source || {}
  for (const group of Object.values(groups)) {
    if (Array.isArray(group)) out.push(...group)
    if (Array.isArray(group?.items)) out.push(...group.items)
  }
  return out
}

function ResultCard({ item }) {
  const title = item.title || item.name || 'Producto sin titulo'
  const price = item.formatted_price || item.price_text || (item.price ? `$ ${Number(item.price).toLocaleString('es-CL')}` : 'Precio no disponible')
  const original = item.formatted_original_price || item.price_original_text || (item.price_original ? `$ ${Number(item.price_original).toLocaleString('es-CL')}` : '')
  const discount = Number(item.discount_percent || 0)
  const url = item.url || item.link

  return (
    <article className="border border-matrix-green/25 bg-black/80 p-3 flex gap-3 min-h-[132px] hover:border-matrix-green hover:bg-matrix-green/5 transition-all">
      <div className="w-24 h-24 shrink-0 border border-matrix-green/20 bg-white/5 flex items-center justify-center overflow-hidden">
        {item.image ? (
          <img src={item.image} alt={title} className="w-full h-full object-contain bg-white" loading="lazy" />
        ) : (
          <ShoppingBasket size={24} className="text-matrix-green/40" />
        )}
      </div>
      <div className="min-w-0 flex-1 flex flex-col gap-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-black uppercase leading-tight text-matrix-green line-clamp-2">{title}</h3>
          {discount > 0 && (
            <span className="shrink-0 border border-matrix-green bg-matrix-green text-black px-2 py-0.5 text-[10px] font-black">
              -{Math.round(discount)}%
            </span>
          )}
        </div>
        <div className="text-[10px] uppercase text-matrix-green/45 font-black">{item.store || item.source || 'Supermercado'}</div>
        <div className="mt-auto flex items-end justify-between gap-3">
          <div>
            <div className="text-xl font-black text-matrix-green tabular-nums">{price}</div>
            {original && <div className="text-xs text-matrix-green/40 line-through tabular-nums">{original}</div>}
          </div>
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 border border-matrix-green/40 px-2 py-1 text-[10px] font-black uppercase text-matrix-green hover:bg-matrix-green hover:text-black transition-all"
            >
              Ver <ExternalLink size={12} />
            </a>
          )}
        </div>
      </div>
    </article>
  )
}

export default function SupermercadosPanel() {
  const [categoriesBySource, setCategoriesBySource] = useState({})
  const [selected, setSelected] = useState(() => ({ jumbo: true }))
  const [categoryBySource, setCategoryBySource] = useState({})
  const [query, setQuery] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [scanScope, setScanScope] = useState('complete')
  const [results, setResults] = useState([])
  const [runs, setRuns] = useState([])
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')

  useEffect(() => {
    let ignore = false
    fetch('/api/global-categories')
      .then((res) => res.json())
      .then((data) => {
        if (!ignore) {
          const categories = data.categories || data || {}
          setCategoriesBySource(categories)
          setCategoryBySource((previous) => {
            const next = { ...previous }
            for (const [source, selectedCategory] of Object.entries(previous)) {
              if (!selectedCategory) continue
              const valid = (categories[source] || []).some(
                (category) => (category.value || category.id) === selectedCategory,
              )
              if (!valid) next[source] = ''
            }
            return next
          })
        }
      })
      .catch(() => {
        if (!ignore) setCategoriesBySource({})
      })
    return () => {
      ignore = true
    }
  }, [])

  const activeSources = useMemo(
    () => SUPERMARKET_SOURCES.filter((source) => selected[source.id]).map((source) => source.id),
    [selected],
  )
  const hasCategory = activeSources.some((id) => categoryBySource[id])
  const canSearch = activeSources.length > 0 && (query.trim() || hasCategory)

  const pollJob = async (jobId) => {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, attempt < 4 ? 500 : 1500))
      const res = await fetch(`/api/global-search/${jobId}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.error || 'Error consultando estado')
      setRuns(data.runs || [])
      if (data.status === 'error') throw new Error(data.error || 'Error en busqueda')
      if (data.status === 'done' || data.status === 'completed') return data
    }
    throw new Error('La busqueda tardo demasiado en responder')
  }

  const runSearch = async () => {
    if (!canSearch || status === 'loading') return
    setError('')
    setStatus('loading')
    setResults([])
    setRuns([])

    const payload = {
      query: query.trim(),
      sources: activeSources,
      min_price: minPrice ? Number(minPrice) : 0,
      max_price: maxPrice ? Number(maxPrice) : 0,
      scan_scope: scanScope,
      max_items_per_source: scanScope === 'fast' ? 80 : 10000,
    }
    for (const id of activeSources) {
      payload[`${id}_category_id`] = categoryBySource[id] || ''
    }

    try {
      const res = await fetch('/api/global-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Error iniciando busqueda')
      const finalData = data.job_id ? await pollJob(data.job_id) : data
      setResults(flattenResults(finalData))
      setRuns(finalData.runs || [])
      setStatus('done')
    } catch (err) {
      setError(err.message || String(err))
      setStatus('error')
    }
  }

  return (
    <div className="gs-matrix-root min-h-screen bg-[#020502] text-matrix-green font-mono p-4 md:p-6 pt-20 overflow-y-auto">
      <div className="max-w-[1400px] mx-auto space-y-5">
        <header className="border-4 border-matrix-green bg-black p-4 shadow-[0_0_50px_rgba(51,255,102,0.18)]">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
            <div>
              <div className="text-[10px] font-black uppercase tracking-[0.35em] text-matrix-green/55">MODULO_DE_CATEGORIAS</div>
              <h1 className="text-3xl md:text-5xl font-black uppercase italic tracking-normal text-matrix-green glow-matrix">Supermercados</h1>
            </div>
            <div className="text-[10px] font-black uppercase text-matrix-green/55 md:text-right">
              {activeSources.length} fuentes activas // {results.length} items
            </div>
          </div>
        </header>

        <section className="border-2 border-matrix-green/35 bg-black/80 p-4 space-y-4">
          <div className="grid md:grid-cols-[1fr_160px_160px_150px] gap-3">
            <input
              type="text"
              placeholder="Palabra clave opcional si eliges categoria"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="bg-black border-2 border-matrix-green/40 px-3 py-2 text-sm font-black text-matrix-green outline-none focus:border-matrix-green"
            />
            <input
              type="number"
              placeholder="Precio min"
              value={minPrice}
              onChange={(event) => setMinPrice(event.target.value)}
              className="bg-black border-2 border-matrix-green/40 px-3 py-2 text-sm font-black text-matrix-green outline-none focus:border-matrix-green"
            />
            <input
              type="number"
              placeholder="Precio max"
              value={maxPrice}
              onChange={(event) => setMaxPrice(event.target.value)}
              className="bg-black border-2 border-matrix-green/40 px-3 py-2 text-sm font-black text-matrix-green outline-none focus:border-matrix-green"
            />
            <select
              value={scanScope}
              onChange={(event) => setScanScope(event.target.value)}
              className="bg-black border-2 border-matrix-green/40 px-3 py-2 text-sm font-black text-matrix-green outline-none focus:border-matrix-green"
            >
              <option value="fast">Rapida</option>
              <option value="complete">Completa</option>
            </select>
          </div>

          <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
            {SUPERMARKET_SOURCES.map((source) => {
              const active = Boolean(selected[source.id])
              const categories = categoriesBySource[source.id] || []
              return (
                <div key={source.id} className={`border p-3 space-y-2 ${active ? 'border-matrix-green bg-matrix-green/10' : 'border-matrix-green/25 bg-black'}`}>
                  <label className="flex items-center gap-2 text-xs font-black uppercase">
                    <input
                      type="checkbox"
                      checked={active}
                      onChange={() => setSelected((prev) => ({ ...prev, [source.id]: !prev[source.id] }))}
                      className="accent-[#33ff66]"
                    />
                    {source.label}
                  </label>
                  {active && (
                    <select
                      value={categoryBySource[source.id] || ''}
                      onChange={(event) => setCategoryBySource((prev) => ({ ...prev, [source.id]: event.target.value }))}
                      className="w-full bg-black border border-matrix-green/40 px-2 py-2 text-xs font-black text-matrix-green outline-none focus:border-matrix-green"
                    >
                      <option value="">Todas las categorias</option>
                      {categories.map((category) => (
                        <option key={category.id || category.value} value={category.value || category.id}>
                          {category.label || category.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              )
            })}
          </div>

          <div className="flex flex-col md:flex-row md:items-center gap-3 justify-between">
            <button
              type="button"
              disabled={!canSearch || status === 'loading'}
              onClick={runSearch}
              className="inline-flex items-center justify-center gap-2 bg-matrix-green text-black px-6 py-3 font-black uppercase tracking-widest disabled:opacity-40 disabled:cursor-not-allowed hover:bg-white transition-all"
            >
              {status === 'loading' ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
              {status === 'loading' ? 'Buscando...' : 'Buscar en supermercados'}
            </button>
            {!canSearch && (
              <span className="text-[10px] uppercase text-matrix-green/50 font-black">
                Selecciona una tienda y una categoria, o escribe una palabra clave.
              </span>
            )}
          </div>
        </section>

        {error && (
          <div className="border-2 border-[#ff3333] bg-[#330000] text-[#ff6666] p-3 flex items-start gap-2 text-xs font-black uppercase">
            <AlertTriangle size={16} /> {error}
          </div>
        )}

        {runs.length > 0 && (
          <section className="grid md:grid-cols-3 xl:grid-cols-7 gap-2">
            {runs.map((run) => (
              <div key={run.source} className="border border-matrix-green/25 bg-black p-2 text-[10px] uppercase font-black">
                <div>{run.source}</div>
                <div className="text-matrix-green/55">{run.count ?? 0} items // {run.elapsed_seconds ?? 0}s</div>
                {(run.warning || run.error) && <div className="mt-1 text-yellow-300 normal-case">{run.warning || run.error}</div>}
              </div>
            ))}
          </section>
        )}

        <section className="grid lg:grid-cols-2 xl:grid-cols-3 gap-3 pb-10">
          {results.map((item, index) => (
            <ResultCard key={`${item.source || item.store || 'item'}-${item.id || item.sku || item.url || index}`} item={item} />
          ))}
        </section>
      </div>
    </div>
  )
}
