import React, { useEffect, useState } from 'react'
import {
  Search,
  Download,
  Play,
  AlertTriangle,
  Loader2
} from 'lucide-react'
import * as XLSX from 'xlsx'
import './index.css'

const API = 'http://127.0.0.1:8020'

const COMMON_STORES = [
  { id: 'lider', name: 'Lider' },
  { id: 'falabella', name: 'Falabella' },
  { id: 'pcfactory', name: 'PcFactory' },
  { id: 'paris', name: 'Paris' },
  { id: 'ripley', name: 'Ripley' },
  { id: 'abc', name: 'Abc' },
  { id: 'hites', name: 'Hites' },
  { id: 'lapolar', name: 'La Polar' },
  { id: 'mercadolibre', name: 'Mercado Libre' }
]

function App() {
  const [form, setForm] = useState({
    query: '',
    retails: [],
    knastaday: 0,
    category: '',
    limit: 80,
    max_pages: 100,
    scan_scope: 'fast',
  })

  const [loading, setLoading] = useState(false)
  const [loadingMeta, setLoadingMeta] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState(null)
  const [categories, setCategories] = useState([])
  const [retails, setRetails] = useState(COMMON_STORES)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [lastElapsedSeconds, setLastElapsedSeconds] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    const loadMeta = async () => {
      setLoadingMeta(true)
      try {
        const params = new URLSearchParams({
          query: form.query.trim(),
          knastaday: String(form.knastaday || 0),
          retails: form.retails.join(','),
        })
        const response = await fetch(`${API}/api/categories?${params.toString()}`, {
          signal: controller.signal,
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'No se pudieron cargar categorias')
        setCategories(data.categories || [])
      } catch (err) {
        if (err.name !== 'AbortError') setCategories([])
      } finally {
        if (!controller.signal.aborted) setLoadingMeta(false)
      }
    }
    loadMeta()
    return () => controller.abort()
  }, [form.knastaday, form.retails.join(','), form.query])

  useEffect(() => {
    const controller = new AbortController()
    const loadRetails = async () => {
      try {
        const params = new URLSearchParams({
          query: form.query.trim(),
          knastaday: String(form.knastaday || 0),
          category: form.category,
        })
        const response = await fetch(`${API}/api/retails?${params.toString()}`, {
          signal: controller.signal,
        })
        const data = await response.json()
        if (response.ok && data.retails?.length) setRetails(data.retails)
      } catch {}
    }
    loadRetails()
    return () => controller.abort()
  }, [form.knastaday, form.category, form.query])

  const updateScanScope = (value) => {
    setForm(prev => ({
      ...prev,
      scan_scope: value,
      limit: value === 'complete' && Number(prev.limit) <= 80 ? 5000 : prev.limit,
      max_pages: value === 'complete' && Number(prev.max_pages) <= 100 ? 500 : prev.max_pages,
    }))
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setElapsedSeconds(0)
    setLastElapsedSeconds(null)
    const startedAt = performance.now()
    
    const timerId = setInterval(() => {
      setElapsedSeconds(prev => prev + 1)
    }, 1000)

    try {
      const response = await fetch(`${API}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: form.query,
          retails: form.retails,
          knastaday: parseInt(form.knastaday) || 0,
          category: form.category,
          limit: parseInt(form.limit) || 80,
          max_pages: parseInt(form.max_pages) || 100,
          scan_scope: form.scan_scope,
        })
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Error al buscar en Knasta')
      }

      const data = await response.json()
      setResults(data)
      setLastElapsedSeconds(((performance.now() - startedAt) / 1000).toFixed(1))
    } catch (err) {
      setError(err.message)
    } finally {
      clearInterval(timerId)
      setLoading(false)
    }
  }

  const exportExcel = () => {
    if (!results || !results.items.length) return

    const rows = results.items.map((item, index) => ({
      'Posicion': index + 1,
      'Titulo': item.title,
      'Precio Formateado': item.formatted_price,
      'Precio Num': item.price,
      'Tienda': item.retail,
      'Descuento %': item.discount_percentage,
      'Link': item.url
    }))

    const wb = XLSX.utils.book_new()
    const ws = XLSX.utils.json_to_sheet(rows)
    XLSX.utils.book_append_sheet(wb, ws, "Knasta")
    XLSX.writeFile(wb, `Knasta_Export_${new Date().getTime()}.xlsx`)
  }

  const setPreset = (type) => {
    if (type === 'hoy') {
      setForm({ ...form, query: '', knastaday: 1, category: '' })
    } else if (type === 'tecno') {
      setForm({ ...form, query: '', knastaday: 0, category: '20106' })
    } else if (type === 'tienda') {
      setForm({ ...form, retails: ['falabella', 'lider', 'pcfactory'] })
    }
  }

  const toggleRetail = (storeId) => {
    setForm(prev => ({
      ...prev,
      retails: prev.retails.includes(storeId) 
        ? prev.retails.filter(id => id !== storeId)
        : [...prev.retails, storeId]
    }))
  }

  return (
    <div className="container">
      <header className="header">
        <h1>Pro Descuento: Knasta Scraper</h1>
        <p>Busca ofertas, filtra por tiendas y explora rebajas diarias.</p>
      </header>

      <div className="card">
        <div style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <button type="button" className="badge" style={{ border: 'none', cursor: 'pointer', padding: '0.5rem 1rem' }} onClick={() => setPreset('hoy')}>
            🔥 Ofertas de Hoy
          </button>
          <button type="button" className="badge" style={{ border: 'none', cursor: 'pointer', padding: '0.5rem 1rem', backgroundColor: 'rgba(167, 139, 250, 0.2)', color: '#c4b5fd' }} onClick={() => setPreset('tecno')}>
            💻 Ofertas Tecno
          </button>
          <button type="button" className="badge" style={{ border: 'none', cursor: 'pointer', padding: '0.5rem 1rem', backgroundColor: 'rgba(52, 211, 153, 0.2)', color: '#6ee7b7' }} onClick={() => setPreset('tienda')}>
            🏪 Multitiendas
          </button>
        </div>

        <form onSubmit={handleSearch}>
          <div className="form-grid">
            <div className="form-group">
              <label>Búsqueda (Opcional)</label>
              <input 
                type="text" 
                className="form-control" 
                placeholder="Ej: notebook gamer"
                value={form.query}
                onChange={e => setForm({...form, query: e.target.value})}
              />
            </div>

            <div className="form-group">
              <label>Knasta Day</label>
              <select 
                className="form-control"
                value={form.knastaday}
                onChange={e => setForm({...form, knastaday: parseInt(e.target.value)})}
              >
                <option value={0}>Todos los días</option>
                <option value={1}>Ofertas de Hoy (1 día)</option>
                <option value={3}>Últimos 3 días</option>
                <option value={7}>Últimos 7 días</option>
              </select>
            </div>

            <div className="form-group">
              <label>Categoría</label>
              <select 
                className="form-control"
                value={form.category}
                onChange={e => setForm({...form, category: e.target.value})}
                disabled={loadingMeta}
              >
                <option value="">{loadingMeta ? 'Cargando categorías...' : 'Todas las categorías'}</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>
                    {cat.path || cat.name} ({Number(cat.count || 0).toLocaleString('es-CL')})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Cobertura</label>
              <select 
                className="form-control"
                value={form.scan_scope}
                onChange={e => updateScanScope(e.target.value)}
              >
                <option value="fast">Muestra rápida</option>
                <option value="complete">Completa hasta el tope</option>
              </select>
            </div>

            <div className="form-group">
              <label>Tope productos</label>
              <input 
                type="number" 
                className="form-control" 
                min="1"
                value={form.limit}
                onChange={e => setForm({...form, limit: e.target.value})}
              />
            </div>

            <div className="form-group">
              <label>Tope páginas</label>
              <input 
                type="number" 
                className="form-control" 
                min="1"
                max="500"
                value={form.max_pages}
                onChange={e => setForm({...form, max_pages: e.target.value})}
              />
            </div>
          </div>
          
          <div className="form-group" style={{ marginTop: '1.5rem' }}>
            <label>Tiendas (Selecciona una o más para filtrar)</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
              {retails.map(store => (
                <button 
                  type="button"
                  key={store.id} 
                  className={`badge ${form.retails.includes(store.id) ? 'active' : ''}`}
                  style={{
                    border: '1px solid var(--border)',
                    backgroundColor: form.retails.includes(store.id) ? 'var(--primary)' : 'transparent',
                    color: form.retails.includes(store.id) ? 'white' : 'var(--text-muted)',
                    cursor: 'pointer'
                  }}
                  onClick={() => toggleRetail(store.id)}
                >
                  {store.name || store.label}{store.count != null ? ` (${Number(store.count).toLocaleString('es-CL')})` : ''}
                </button>
              ))}
              {form.retails.length > 0 && (
                <button type="button" style={{ border: 'none', background: 'transparent', color: 'var(--danger)', cursor: 'pointer', fontSize: '0.875rem', marginLeft: '0.5rem' }} onClick={() => setForm({...form, retails: []})}>
                  Limpiar tiendas
                </button>
              )}
            </div>
          </div>

          <div className="actions">
            <button type="submit" className="btn btn-success" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="loading-spinner" /> 
                  Buscando... ({elapsedSeconds}s)
                </>
              ) : (
                <>
                  <Play size={20} />
                  Buscar Ofertas
                </>
              )}
            </button>
            {results && results.items.length > 0 && (
              <button type="button" className="btn btn-secondary" onClick={exportExcel}>
                <Download size={20} />
                Exportar a Excel
              </button>
            )}
          </div>
        </form>
      </div>

      {error && (
        <div className="card" style={{ borderLeft: '4px solid var(--danger)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--danger)' }}>
            <AlertTriangle />
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {results && (
        <div className="card" style={{ padding: '0' }}>
          <div className="status-bar" style={{ borderRadius: '1rem 1rem 0 0', border: 'none', borderBottom: '1px solid var(--border)', margin: '0' }}>
            <div>
              <span className="badge" style={{ marginRight: '1rem' }}>
                Total Encontrados: {results.total_matches}
              </span>
              <span className="badge" style={{ marginRight: '1rem' }}>
                Mostrando: {results.items.length}
              </span>
              <span className="badge" style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)', color: '#cbd5e1' }}>
                Tiempo de búsqueda: {lastElapsedSeconds ?? elapsedSeconds} segundos
              </span>
              <span className="badge" style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)', color: '#cbd5e1' }}>
                {results.pages_fetched || 0} páginas · {results.fetched_raw || 0} productos revisados
              </span>
            </div>
            <div>
              <a href={results.search_url} target="_blank" rel="noreferrer" className="product-link">
                Ver búsqueda original en Knasta
              </a>
            </div>
          </div>

          <div className="table-container" style={{ border: 'none', borderRadius: '0 0 1rem 1rem' }}>
            <table style={{ fontSize: '0.9rem' }}>
              <thead>
                <tr>
                  <th style={{ width: '5%' }}>#</th>
                  <th style={{ width: '45%' }}>Producto</th>
                  <th style={{ width: '15%' }}>Precio</th>
                  <th style={{ width: '15%' }}>Descuento</th>
                  <th style={{ width: '20%' }}>Tienda</th>
                </tr>
              </thead>
              <tbody>
                {results.items.map((item, idx) => (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    <td>
                      <a href={item.url} target="_blank" rel="noreferrer" className="product-link" title={item.title}>
                        {item.title}
                      </a>
                    </td>
                    <td style={{ fontWeight: 'bold', color: 'var(--success)' }}>
                      {item.formatted_price}
                    </td>
                    <td>
                      {item.discount_percentage < 0 ? (
                        <span className="badge danger" style={{ padding: '0.1rem 0.4rem', fontSize: '0.75rem' }}>{item.discount_percentage}%</span>
                      ) : item.discount_percentage > 0 ? (
                        <span className="badge" style={{ padding: '0.1rem 0.4rem', fontSize: '0.75rem' }}>{item.discount_percentage}%</span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td>
                       <span style={{ padding: '0.2rem 0.5rem', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px', fontSize: '0.8rem' }}>
                         {item.retail}
                       </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
