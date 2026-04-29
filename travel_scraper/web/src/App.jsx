import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Calculator, Download, FileSpreadsheet, Loader2, Search, SlidersHorizontal } from 'lucide-react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8050/api'

const ORDERS = [
  { value: 'relevance', label: 'Relevancia / tienda' },
  { value: 'price_asc', label: 'Precio menor' },
  { value: 'price_desc', label: 'Precio mayor' },
  { value: 'discount_desc', label: 'Mayor descuento' },
  { value: 'name_asc', label: 'Nombre A-Z' },
]

function App() {
  const [categories, setCategories] = useState([])
  const [loadingCategories, setLoadingCategories] = useState(true)
  const [form, setForm] = useState({
    query: '',
    category_id: '',
    ordering: 'relevance',
    min_price: '',
    max_price: '',
    include_words: '',
    exclude_words: '',
    scan_scope: 'fast',
    preview_limit: '200',
    max_items: '10000',
  })
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')
  const [summary, setSummary] = useState(null)
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      setLoadingCategories(true)
      try {
        const response = await fetch(`${API_BASE}/categories`, { signal: controller.signal })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'No se pudieron cargar categorias')
        setCategories(data.categories || [])
      } catch (err) {
        if (err.name !== 'AbortError') setError(err.message)
      } finally {
        if (!controller.signal.aborted) setLoadingCategories(false)
      }
    }
    load()
    return () => controller.abort()
  }, [])

  const hasInput = useMemo(() => true, [])

  const setField = (field, value) => setForm(prev => ({ ...prev, [field]: value }))

  const payload = () => ({
    query: form.query.trim(),
    category_id: form.category_id,
    ordering: form.ordering,
    min_price: Number(form.min_price) || 0,
    max_price: Number(form.max_price) || 0,
    include_words: form.include_words.split(',').map(word => word.trim()).filter(Boolean),
    exclude_words: form.exclude_words.split(',').map(word => word.trim()).filter(Boolean),
    scan_scope: form.scan_scope,
    preview_limit: Number(form.preview_limit) || 200,
    max_items: Number(form.max_items) || 10000,
  })

  const runJsonAction = async (action) => {
    setLoading(action)
    setError('')
    if (action !== 'preview') setPreview(null)

    try {
      const response = await fetch(`${API_BASE}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload()),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Error consultando Travel')

      if (action === 'count') {
        setSummary({
          mainLabel: 'Coincidencias',
          mainValue: data.count,
          total: data.count,
          pages: 1,
          elapsed: data.elapsed_seconds,
        })
      } else {
        setPreview(data)
        setSummary({
          mainLabel: 'Filas en vista previa',
          mainValue: data.count,
          total: data.total_matches,
          pages: data.pages_fetched,
          elapsed: data.elapsed_seconds,
        })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading('')
    }
  }

  const exportExcel = async () => {
    setLoading('export')
    setError('')
    try {
      const response = await fetch(`${API_BASE}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload()),
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Error exportando Excel')
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `travel_export_${Date.now()}.xlsx`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading('')
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Pro Descuento</p>
          <h1>Travel Tienda Scraper</h1>
        </div>
        <span className="status-pill">Oracle Commerce</span>
      </header>

      {error && (
        <div className="alert">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      <section className="workspace">
        <form className="search-panel" onSubmit={(event) => {
          event.preventDefault()
          runJsonAction('preview')
        }}>
          <div className="section-heading">
            <Search size={19} />
            <h2>Busqueda</h2>
          </div>

          <div className="form-grid">
            <label>
              <span>Categoria</span>
              <select value={form.category_id} onChange={event => setField('category_id', event.target.value)} disabled={loadingCategories}>
                <option value="">{loadingCategories ? 'Cargando categorias...' : 'Todas las categorias'}</option>
                {categories.map(category => (
                  <option key={category.id} value={category.id}>
                    {'  '.repeat(Math.min(category.depth || 0, 4))}{category.path}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Texto</span>
              <input value={form.query} onChange={event => setField('query', event.target.value)} placeholder="notebook, bose, cafetera" />
            </label>

            <label>
              <span>Orden</span>
              <select value={form.ordering} onChange={event => setField('ordering', event.target.value)}>
                {ORDERS.map(order => <option key={order.value} value={order.value}>{order.label}</option>)}
              </select>
            </label>

            <label>
              <span>Modo</span>
              <select value={form.scan_scope} onChange={event => setField('scan_scope', event.target.value)}>
                <option value="fast">Rapido</option>
                <option value="complete">Completo hasta 10.000</option>
              </select>
            </label>
          </div>

          <div className="section-heading compact">
            <SlidersHorizontal size={18} />
            <h2>Filtros</h2>
          </div>

          <div className="form-grid dense">
            <label>
              <span>Precio minimo</span>
              <input type="number" min="0" value={form.min_price} onChange={event => setField('min_price', event.target.value)} placeholder="0" />
            </label>
            <label>
              <span>Precio maximo</span>
              <input type="number" min="0" value={form.max_price} onChange={event => setField('max_price', event.target.value)} placeholder="Sin limite" />
            </label>
            <label>
              <span>Incluir palabras</span>
              <input value={form.include_words} onChange={event => setField('include_words', event.target.value)} placeholder="hp, gamer" />
            </label>
            <label>
              <span>Excluir palabras</span>
              <input value={form.exclude_words} onChange={event => setField('exclude_words', event.target.value)} placeholder="refurbished" />
            </label>
            <label>
              <span>Vista previa</span>
              <input type="number" min="1" max="10000" value={form.preview_limit} onChange={event => setField('preview_limit', event.target.value)} />
            </label>
            <label>
              <span>Maximo exportacion</span>
              <input type="number" min="1" max="10000" value={form.max_items} onChange={event => setField('max_items', event.target.value)} />
            </label>
          </div>

          <div className="actions">
            <button type="button" className="button secondary" disabled={!hasInput || Boolean(loading)} onClick={() => runJsonAction('count')}>
              {loading === 'count' ? <Loader2 className="spin" size={17} /> : <Calculator size={17} />}
              Calcular
            </button>
            <button type="submit" className="button secondary" disabled={Boolean(loading)}>
              {loading === 'preview' ? <Loader2 className="spin" size={17} /> : <FileSpreadsheet size={17} />}
              Previsualizar
            </button>
            <button type="button" className="button primary" disabled={Boolean(loading)} onClick={exportExcel}>
              {loading === 'export' ? <Loader2 className="spin" size={17} /> : <Download size={17} />}
              Exportar Excel
            </button>
          </div>
        </form>

        <aside className="summary-panel">
          <div className="metric">
            <span>{summary?.mainLabel || 'Listo para buscar'}</span>
            <strong>{summary ? summary.mainValue.toLocaleString('es-CL') : '-'}</strong>
          </div>
          <div className="metric-row">
            <div className="metric small">
              <span>Total API</span>
              <strong>{summary ? summary.total.toLocaleString('es-CL') : '-'}</strong>
            </div>
            <div className="metric small">
              <span>Paginas</span>
              <strong>{summary?.pages || '-'}</strong>
            </div>
          </div>
          <div className="metric small">
            <span>Tiempo</span>
            <strong>{summary ? `${summary.elapsed}s` : '-'}</strong>
          </div>
        </aside>
      </section>

      {preview && (
        <section className="results">
          <div className="results-head">
            <h2>Vista previa</h2>
            <span>{preview.rows.length.toLocaleString('es-CL')} filas</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>{preview.columns.map(column => <th key={column}>{column}</th>)}</tr>
              </thead>
              <tbody>
                {preview.rows.map((row, index) => (
                  <tr key={`${row.SKU}-${index}`}>
                    <td>{row.Posicion}</td>
                    <td>{row.SKU}</td>
                    <td className="title-cell">{row.Nombre}</td>
                    <td>{row.Marca || '-'}</td>
                    <td>{row.Categoria || '-'}</td>
                    <td>{row['Precio Normal'] || '-'}</td>
                    <td>{row['Precio Oferta'] || '-'}</td>
                    <td>{row.Descuento || '-'}</td>
                    <td>{row.Link ? <a href={row.Link} target="_blank" rel="noreferrer">Abrir</a> : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  )
}

export default App
