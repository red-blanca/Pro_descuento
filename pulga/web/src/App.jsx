import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  Calculator,
  Clock3,
  FileJson,
  Hash,
  LayoutGrid,
  MapPin,
  Search,
  Settings2,
  SlidersHorizontal,
  Tag,
} from 'lucide-react'
import './App.css'

const CATEGORIES = [
  { key: '', label: 'Todas' },
  { key: 'tecnologia', label: 'Tecnologia' },
  { key: 'moda', label: 'Moda' },
  { key: 'bebes', label: 'Bebe y Ninos' },
  { key: 'entretenimiento', label: 'Entretenimiento' },
  { key: 'coleccionismo', label: 'Coleccionismo' },
  { key: 'deporte', label: 'Deporte' },
  { key: 'bicicletas', label: 'Bicicletas' },
  { key: 'hogar', label: 'Hogar y Jardin' },
  { key: 'electrodomesticos', label: 'Electrodomesticos' },
]

function App() {
  const [form, setForm] = useState({
    query: '',
    category: '',
    all_results: true,
    max_pages: 0,
    min_price: 0,
    max_price: 0,
    word: '',
    include_words: [],
    exclude_words: [],
    condition: 'any',
    sort_price: true,
    city: '',
    preview_limit: 200,
  })
  const [countResult, setCountResult] = useState(null)
  const [countElapsed, setCountElapsed] = useState(null)
  const [totalAvailable, setTotalAvailable] = useState(null)
  const [applied, setApplied] = useState(null)
  const [status, setStatus] = useState('')
  const [loadingCount, setLoadingCount] = useState(false)
  const [loadingExport, setLoadingExport] = useState(false)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [countRunMs, setCountRunMs] = useState(0)
  const [exportRunMs, setExportRunMs] = useState(0)
  const [previewRunMs, setPreviewRunMs] = useState(0)
  const [includeDraft, setIncludeDraft] = useState('')
  const [excludeDraft, setExcludeDraft] = useState('')
  const [previewRows, setPreviewRows] = useState([])
  const [previewColumns, setPreviewColumns] = useState([])
  const [previewElapsed, setPreviewElapsed] = useState(null)
  const [view, setView] = useState('main')
  const [columnFilters, setColumnFilters] = useState({
    Posicion: '',
    Titulo: '',
    Precio: '',
    Condicion: '',
    Ciudad: '',
    Vendedor: '',
    Link: '',
  })

  const canSubmit = useMemo(
    () => Boolean(form.query.trim() || form.category.trim()),
    [form.query, form.category],
  )

  const resolvedColumns = previewColumns.length
    ? previewColumns
    : ['Posicion', 'Titulo', 'Precio', 'Condicion', 'Ciudad', 'Vendedor', 'Link']

  const filteredPreviewRows = useMemo(() => {
    if (!previewRows.length) return []
    return previewRows.filter((row) =>
      resolvedColumns.every((col) => {
        const needle = (columnFilters[col] || '').trim().toLowerCase()
        if (!needle) return true
        const hay = String(row[col] ?? '').toLowerCase()
        return hay.includes(needle)
      }),
    )
  }, [previewRows, resolvedColumns, columnFilters])

  const onChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const runWithLiveTimer = async (setterLoading, setterRunMs, task) => {
    setterLoading(true)
    setterRunMs(0)
    const startedAt = performance.now()
    const tick = setInterval(() => {
      setterRunMs(performance.now() - startedAt)
    }, 120)
    try {
      await task()
    } finally {
      clearInterval(tick)
      setterRunMs(performance.now() - startedAt)
      setterLoading(false)
    }
  }

  const addIncludeWord = () => {
    const value = includeDraft.trim()
    if (!value) return
    setForm((prev) => {
      if (prev.include_words.includes(value)) return prev
      return { ...prev, include_words: [...prev.include_words, value] }
    })
    setIncludeDraft('')
  }

  const addExcludeWord = () => {
    const value = excludeDraft.trim()
    if (!value) return
    setForm((prev) => {
      if (prev.exclude_words.includes(value)) return prev
      return { ...prev, exclude_words: [...prev.exclude_words, value] }
    })
    setExcludeDraft('')
  }

  const removeIncludeWord = (word) => {
    setForm((prev) => ({
      ...prev,
      include_words: prev.include_words.filter((w) => w !== word),
    }))
  }

  const removeExcludeWord = (word) => {
    setForm((prev) => ({
      ...prev,
      exclude_words: prev.exclude_words.filter((w) => w !== word),
    }))
  }

  const runCount = async () => {
    if (!canSubmit) return
    setStatus('')
    await runWithLiveTimer(setLoadingCount, setCountRunMs, async () => {
      try {
        const res = await fetch('/api/count', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Error en conteo')
        setCountResult(data.count)
        setTotalAvailable(data.total_available ?? null)
        setCountElapsed(data.elapsed_seconds)
        setApplied(data.applied_filters || null)
      } catch (err) {
        setStatus(err.message)
      }
    })
  }

  const runPreview = async () => {
    if (!canSubmit) return
    setStatus('')
    await runWithLiveTimer(setLoadingPreview, setPreviewRunMs, async () => {
      try {
        const res = await fetch('/api/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Error en previsualizacion')
        setPreviewColumns(data.columns || [])
        setPreviewRows(data.rows || [])
        setPreviewElapsed(data.elapsed_seconds ?? null)
        setTotalAvailable(data.total_available ?? null)
        setView('preview')
      } catch (err) {
        setStatus(err.message)
      }
    })
  }

  const runExport = async () => {
    if (!canSubmit) return
    setStatus('')
    await runWithLiveTimer(setLoadingExport, setExportRunMs, async () => {
      try {
        const res = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
        })
        if (!res.ok) {
          const data = await res.json()
          throw new Error(data.detail || 'Error exportando')
        }
        const blob = await res.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `pulga_export_${Date.now()}.json`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
        setStatus('JSON exportado correctamente.')
      } catch (err) {
        setStatus(err.message)
      }
    })
  }

  /* ─── Preview View ─── */
  if (view === 'preview') {
    return (
      <main className="page">
        <section className="panel preview-page fade-in-section">
          <div className="hero section-reveal fade-1">
            <h1>Previsualizacion</h1>
            <button className="btn ghost" type="button" onClick={() => setView('main')}>
              <span className="btn-content"><ArrowLeft size={16} />Volver</span>
            </button>
          </div>
          <div className="preview-meta section-reveal fade-2">
            <span>Filas: {filteredPreviewRows.length} / {previewRows.length}</span>
            {totalAvailable != null && <span>Disponibles en Pulga: {totalAvailable.toLocaleString()}</span>}
            <span>Tiempo: {previewElapsed != null ? `${previewElapsed}s` : '-'}</span>
          </div>
          <div className="table-wrap section-reveal fade-3">
            <table className="preview-table">
              <thead>
                <tr>
                  {resolvedColumns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
                <tr className="filter-row">
                  {resolvedColumns.map((col) => (
                    <th key={`${col}-filter`}>
                      <input
                        className="col-filter-input"
                        placeholder={`Filtrar...`}
                        value={columnFilters[col] || ''}
                        onChange={(e) =>
                          setColumnFilters((prev) => ({ ...prev, [col]: e.target.value }))
                        }
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredPreviewRows.map((row, idx) => (
                  <tr className="preview-row" key={`${row.Link}-${idx}`} style={{ animationDelay: `${Math.min(idx, 40) * 18}ms` }}>
                    <td>{row.Posicion}</td>
                    <td>{row.Titulo}</td>
                    <td>{row.Precio}</td>
                    <td><span className={`condition-badge ${row.Condicion === 'Nuevo' ? 'cond-new' : row.Condicion === 'Usado' ? 'cond-used' : ''}`}>{row.Condicion}</span></td>
                    <td>{row.Ciudad}</td>
                    <td>{row.Vendedor}</td>
                    <td>
                      {row.Link ? (
                        <a href={row.Link} target="_blank" rel="noreferrer">abrir</a>
                      ) : '-'}
                    </td>
                  </tr>
                ))}
                {!filteredPreviewRows.length && (
                  <tr><td colSpan={7}>Sin datos con los filtros actuales.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    )
  }

  /* ─── Main View ─── */
  return (
    <main className="page">
      <section className="panel visual-panel fade-in-section">
        <div className="hero section-reveal fade-1">
          <div className="hero-left">
            <span className="logo-icon">🪲</span>
            <h1>Pulga.cl Scraper</h1>
          </div>
          <span className="badge">Marketplace 2da Mano</span>
        </div>
        <p className="hint section-reveal fade-2">
          Busca productos de segunda mano en Pulga.cl. Filtra, previsualiza y exporta a JSON.
        </p>

        {/* ── Search Section ── */}
        <div className="section section-reveal fade-3">
          <div className="section-title"><Search size={14} /> Busqueda</div>
          <div className="grid">
            <label>
              Busqueda
              <input
                placeholder="ej: notebook, iphone, zapatillas..."
                value={form.query}
                onChange={(e) => onChange('query', e.target.value)}
              />
            </label>
            <label>
              <span className="label-with-icon"><LayoutGrid size={13} /> Categoria</span>
              <select value={form.category} onChange={(e) => onChange('category', e.target.value)}>
                {CATEGORIES.map((cat) => (
                  <option key={cat.key} value={cat.key}>{cat.label}</option>
                ))}
              </select>
            </label>
            <label>
              Precio minimo
              <input
                type="number"
                value={form.min_price}
                onChange={(e) => onChange('min_price', Number(e.target.value || 0))}
              />
            </label>
            <label>
              Precio maximo
              <input
                type="number"
                value={form.max_price}
                onChange={(e) => onChange('max_price', Number(e.target.value || 0))}
              />
            </label>
            <label>
              <span className="label-with-icon"><Tag size={13} /> Condicion</span>
              <select value={form.condition} onChange={(e) => onChange('condition', e.target.value)}>
                <option value="any">Cualquiera</option>
                <option value="new">Nuevo</option>
                <option value="used">Usado</option>
              </select>
            </label>
            <label>
              <span className="label-with-icon"><MapPin size={13} /> Ciudad</span>
              <input
                placeholder="ej: Santiago, Curico"
                value={form.city}
                onChange={(e) => onChange('city', e.target.value)}
              />
            </label>
            <label className="full">
              Palabras a incluir
              <div className="word-editor">
                <input
                  placeholder="ej: gamer"
                  value={includeDraft}
                  onChange={(e) => setIncludeDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addIncludeWord() } }}
                />
                <button type="button" onClick={addIncludeWord}>Agregar</button>
              </div>
              <div className="chips">
                {form.include_words.map((word) => (
                  <button className="chip include" key={word} type="button" onClick={() => removeIncludeWord(word)} title="Quitar">
                    {word} ×
                  </button>
                ))}
              </div>
            </label>
            <label className="full">
              Palabras a descartar
              <div className="word-editor">
                <input
                  placeholder="ej: funda, carcasa"
                  value={excludeDraft}
                  onChange={(e) => setExcludeDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addExcludeWord() } }}
                />
                <button type="button" onClick={addExcludeWord}>Agregar</button>
              </div>
              <div className="chips">
                {form.exclude_words.map((word) => (
                  <button className="chip exclude" key={word} type="button" onClick={() => removeExcludeWord(word)} title="Quitar">
                    {word} ×
                  </button>
                ))}
              </div>
            </label>
            <label>
              Max paginas (0 = sin limite)
              <input type="number" value={form.max_pages} onChange={(e) => onChange('max_pages', Number(e.target.value || 0))} />
            </label>
            <label>
              Limite preview
              <input type="number" min="1" max="2000" value={form.preview_limit} onChange={(e) => onChange('preview_limit', Number(e.target.value || 1))} />
            </label>
          </div>
        </div>

        {/* ── Config Section ── */}
        <div className="section section-reveal fade-4">
          <div className="section-title"><Settings2 size={14} /> Configuracion</div>
          <div className="checks">
            <label className="switch-card">
              <span>Buscar todas las paginas</span>
              <input type="checkbox" checked={form.all_results} onChange={(e) => onChange('all_results', e.target.checked)} />
              <span className="switch"><span className="switch-knob" /></span>
            </label>
            <label className="switch-card">
              <span>Ordenar por precio</span>
              <input type="checkbox" checked={form.sort_price} onChange={(e) => onChange('sort_price', e.target.checked)} />
              <span className="switch"><span className="switch-knob" /></span>
            </label>
          </div>
        </div>

        {/* ── Actions ── */}
        <div className="actions section-reveal fade-5">
          <button className="btn accent" disabled={!canSubmit || loadingCount} onClick={runCount}>
            {loadingCount ? (
              <span className="btn-content"><span className="loader" />Calculando... {(countRunMs / 1000).toFixed(1)}s</span>
            ) : (
              <span className="btn-content"><Calculator size={16} />Calcular cantidad</span>
            )}
          </button>
          <button className="btn info" disabled={!canSubmit || loadingPreview} onClick={runPreview}>
            {loadingPreview ? (
              <span className="btn-content"><span className="loader" />Cargando tabla... {(previewRunMs / 1000).toFixed(1)}s</span>
            ) : (
              <span className="btn-content"><SlidersHorizontal size={16} />Previsualizar tabla</span>
            )}
          </button>
          <button className="btn outline" disabled={!canSubmit || loadingExport} onClick={runExport}>
            {loadingExport ? (
              <span className="btn-content"><span className="loader" />Exportando... {(exportRunMs / 1000).toFixed(1)}s</span>
            ) : (
              <span className="btn-content"><FileJson size={16} />Exportar JSON</span>
            )}
          </button>
        </div>

        {/* ── Results ── */}
        <div className="results section-reveal fade-6">
          <div className="section-title"><SlidersHorizontal size={14} /> Resumen</div>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-icon"><Hash size={14} /></div>
              <div>
                <div className="kpi-label">Resultados filtrados</div>
                <div className="kpi-value">{countResult ?? '-'}</div>
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-icon icon-total"><LayoutGrid size={14} /></div>
              <div>
                <div className="kpi-label">Total en Pulga</div>
                <div className="kpi-value">{totalAvailable != null ? totalAvailable.toLocaleString() : '-'}</div>
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-icon icon-time"><Clock3 size={14} /></div>
              <div>
                <div className="kpi-label">Tiempo</div>
                <div className="kpi-value">{countElapsed != null ? `${countElapsed}s` : '-'}</div>
              </div>
            </div>
          </div>
          {applied && (
            <div className="applied-filters">
              <Tag size={13} />
              {applied.query && <span>query="{applied.query}"</span>}
              {applied.category && <span>cat={applied.category}</span>}
              {(applied.include_words || []).length > 0 && <span>include=[{applied.include_words.join(', ')}]</span>}
              {(applied.exclude_words || []).length > 0 && <span>exclude=[{applied.exclude_words.join(', ')}]</span>}
              {applied.city && <span>city={applied.city}</span>}
            </div>
          )}
          {status && <div className="status status-pulse">{status}</div>}
          {(loadingCount || loadingExport || loadingPreview) && (
            <div className="running-hint">
              Proceso activo: {loadingCount ? 'conteo' : loadingPreview ? 'previsualizacion' : 'exportacion JSON'}
            </div>
          )}
        </div>

        <footer className="foot">Pulga.cl Scraper v1.0 — Datos de pulga.cl para uso personal.</footer>
      </section>
    </main>
  )
}

export default App
