import { useEffect, useState } from 'react'
import { AlertTriangle, Download, Loader2, Play, Search, SlidersHorizontal } from 'lucide-react'
import * as XLSX from 'xlsx'

const MODES = [
  { id: 'search', label: 'Busqueda' },
  { id: 'offers', label: 'Ofertas del dia' },
  { id: 'all_offers', label: 'Todas las ofertas' },
  { id: 'minimums', label: 'Precios minimos' },
  { id: 'best', label: 'Mejores ofertas' },
]

const STORES = [
  'falabella',
  'ripley',
  'paris',
  'sodimac',
  'lider',
  'abcdin',
  'pcFactory',
  'hites',
  'easy',
  'sparta',
  'knasta',
]

function App() {
  const [form, setForm] = useState({
    query: '',
    mode: 'all_offers',
    stores: [],
    category: '',
    min_discount: 0,
    min_price: 0,
    max_price: 0,
    only_available: false,
    sort: '',
    limit: 80,
    max_pages: 100,
    scan_scope: 'fast',
  })
  const [loading, setLoading] = useState(false)
  const [loadingCategories, setLoadingCategories] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState(null)
  const [categories, setCategories] = useState([])
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [lastElapsedSeconds, setLastElapsedSeconds] = useState(null)

  const canSearch = form.mode !== 'search' || form.query.trim()

  useEffect(() => {
    const controller = new AbortController()
    const loadCategories = async () => {
      setLoadingCategories(true)
      try {
        const params = new URLSearchParams({
          mode: form.mode,
          query: form.mode === 'search' ? form.query.trim() : '',
        })
        const response = await fetch(`/api/categories?${params.toString()}`, {
          signal: controller.signal,
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'No se pudieron cargar categorias')
        setCategories(data.categories || [])
      } catch (err) {
        if (err.name !== 'AbortError') {
          setCategories([])
        }
      } finally {
        if (!controller.signal.aborted) setLoadingCategories(false)
      }
    }
    loadCategories()
    return () => controller.abort()
  }, [form.mode, form.mode === 'search' ? form.query : ''])

  const update = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const updateScanScope = (value) => {
    setForm((prev) => ({
      ...prev,
      scan_scope: value,
      limit: value === 'complete' && Number(prev.limit) <= 80 ? 5000 : prev.limit,
      max_pages: value === 'complete' && Number(prev.max_pages) <= 4 ? 100 : prev.max_pages,
    }))
  }

  const toggleStore = (store) => {
    setForm((prev) => ({
      ...prev,
      stores: prev.stores.includes(store)
        ? prev.stores.filter((item) => item !== store)
        : [...prev.stores, store],
    }))
  }

  const runSearch = async (event) => {
    event.preventDefault()
    if (!canSearch) return
    setLoading(true)
    setError('')
    setElapsedSeconds(0)
    setLastElapsedSeconds(null)
    const startedAt = performance.now()

    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...form,
          min_discount: Number(form.min_discount) || 0,
          min_price: Number(form.min_price) || 0,
          max_price: Number(form.max_price) || 0,
          limit: Number(form.limit) || 80,
          max_pages: Number(form.max_pages) || 100,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Error buscando en TuGanga')
      setResults(data)
      setLastElapsedSeconds(((performance.now() - startedAt) / 1000).toFixed(1))
    } catch (err) {
      setError(err.message)
    } finally {
      clearInterval(timer)
      setLoading(false)
    }
  }

  const exportExcel = () => {
    if (!results?.items?.length) return
    const rows = results.items.map((item, index) => ({
      Posicion: index + 1,
      Titulo: item.title,
      Precio: item.formatted_price,
      PrecioAnterior: item.formatted_old_price,
      Descuento: `${item.discount_percentage || 0}%`,
      Tienda: item.store,
      Marca: item.brand,
      Categoria: item.category,
      Disponible: item.available ? 'Si' : 'No',
      Link: item.url,
    }))
    const wb = XLSX.utils.book_new()
    const ws = XLSX.utils.json_to_sheet(rows)
    XLSX.utils.book_append_sheet(wb, ws, 'TuGanga')
    XLSX.writeFile(wb, `TuGanga_Export_${Date.now()}.xlsx`)
  }

  return (
    <main className="page">
      <section className="hero">
        <div>
          <p className="eyebrow">Pro Descuento</p>
          <h1>TuGanga Scraper</h1>
          <p>Busca ofertas, precios minimos y productos comparados desde TuGanga.</p>
        </div>
      </section>

      <section className="panel">
        <form onSubmit={runSearch}>
          <div className="section-title">
            <Search size={16} /> Busqueda y modo
          </div>
          <div className="grid">
            <label>
              Busqueda {form.mode === 'search' ? '' : '(opcional)'}
              <input
                placeholder={form.mode === 'search' ? 'ej: notebook, celular, zapatillas' : 'filtrar dentro del modo'}
                value={form.query}
                onChange={(event) => update('query', event.target.value)}
              />
            </label>
            <label>
              Modo
              <select value={form.mode} onChange={(event) => update('mode', event.target.value)}>
                {MODES.map((mode) => (
                  <option key={mode.id} value={mode.id}>{mode.label}</option>
                ))}
              </select>
            </label>
            <label>
              Categoria
              <select
                value={form.category}
                onChange={(event) => update('category', event.target.value)}
                disabled={loadingCategories}
              >
                <option value="">
                  {loadingCategories ? 'Cargando categorias...' : 'Todas las categorias'}
                </option>
                {categories.map((category) => (
                  <option key={category.value} value={category.value}>
                    {category.label} ({Number(category.count || 0).toLocaleString('es-CL')})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Cobertura
              <select value={form.scan_scope} onChange={(event) => updateScanScope(event.target.value)}>
                <option value="fast">Muestra rapida</option>
                <option value="complete">Completa hasta el tope</option>
              </select>
            </label>
            <label>
              Descuento minimo %
              <input
                min="0"
                max="100"
                type="number"
                value={form.min_discount}
                onChange={(event) => update('min_discount', event.target.value)}
              />
            </label>
            <label>
              Precio minimo
              <input
                min="0"
                type="number"
                value={form.min_price}
                onChange={(event) => update('min_price', event.target.value)}
              />
            </label>
            <label>
              Precio maximo
              <input
                min="0"
                type="number"
                value={form.max_price}
                onChange={(event) => update('max_price', event.target.value)}
              />
            </label>
            <label>
              Tope productos
              <input
                min="1"
                type="number"
                value={form.limit}
                onChange={(event) => update('limit', event.target.value)}
              />
            </label>
            <label>
              Tope paginas
              <input
                min="1"
                max="500"
                type="number"
                value={form.max_pages}
                onChange={(event) => update('max_pages', event.target.value)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={form.only_available}
                onChange={(event) => update('only_available', event.target.checked)}
              />
              Solo disponibles
            </label>
          </div>

          <div className="section-title stores-title">
            <SlidersHorizontal size={16} /> Tiendas
          </div>
          <div className="stores">
            {STORES.map((store) => (
              <button
                key={store}
                type="button"
                className={`chip ${form.stores.includes(store) ? 'active' : ''}`}
                onClick={() => toggleStore(store)}
              >
                {store}
              </button>
            ))}
            {form.stores.length > 0 && (
              <button type="button" className="clear" onClick={() => update('stores', [])}>
                limpiar
              </button>
            )}
          </div>

          <div className="actions">
            <button className="btn primary" disabled={!canSearch || loading} type="submit">
              {loading ? (
                <>
                  <Loader2 className="spin" size={18} />
                  Buscando... {elapsedSeconds}s
                </>
              ) : (
                <>
                  <Play size={18} />
                  Buscar
                </>
              )}
            </button>
            {results?.items?.length > 0 && (
              <button className="btn secondary" type="button" onClick={exportExcel}>
                <Download size={18} />
                Exportar Excel
              </button>
            )}
          </div>
        </form>
      </section>

      {error && (
        <section className="panel error">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </section>
      )}

      {results && (
        <section className="panel">
          <div className="summary">
            <strong>{results.items.length}</strong> resultados capturados de {Number(results.total_matches || 0).toLocaleString('es-CL')} reportados.
            <span>{results.pages_fetched || 0} paginas · {results.fetched_raw || 0} productos revisados</span>
            {lastElapsedSeconds != null && <span>{lastElapsedSeconds}s</span>}
            {results.search_url && (
              <a href={results.search_url} target="_blank" rel="noreferrer">abrir en TuGanga</a>
            )}
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Tienda</th>
                  <th>Precio</th>
                  <th>Antes</th>
                  <th>Dcto</th>
                  <th>Estado</th>
                  <th>Link</th>
                </tr>
              </thead>
              <tbody>
                {results.items.map((item, index) => (
                  <tr key={`${item.id}-${index}`}>
                    <td>
                      <div className="title">{item.title}</div>
                      <div className="meta">{item.brand || '-'} · {item.category || '-'}</div>
                    </td>
                    <td>{item.store}</td>
                    <td className="price">{item.formatted_price || '-'}</td>
                    <td>{item.formatted_old_price || '-'}</td>
                    <td>{item.discount_percentage || 0}%</td>
                    <td>{item.available ? 'Disponible' : 'No disponible'}</td>
                    <td><a href={item.url} target="_blank" rel="noreferrer">abrir</a></td>
                  </tr>
                ))}
                {!results.items.length && (
                  <tr>
                    <td colSpan="7">Sin resultados para los filtros actuales.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  )
}

export default App
