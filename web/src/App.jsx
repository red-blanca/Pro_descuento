import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Calculator, Clock3, FileSpreadsheet, Globe, Hash, Search, Settings2, SlidersHorizontal } from 'lucide-react'
import './App.css'

function App() {
  const [form, setForm] = useState({
    query: '',
    country: 'cl',
    all_results: false,
    max_pages: 0,
    min_price: 0,
    max_price: 0,
    min_discount: 0,
    word: '',
    include_words: [],
    exclude_words: [],
    condition: 'any',
    sort_price: true,
    include_international: false,
    cookie_file: '',
    search_url: '',
    category_url: '',
    scan_scope: 'fast',
    preview_limit: 200,
  })
  const [exactCount, setExactCount] = useState(null)
  const [exactElapsed, setExactElapsed] = useState(null)
  const [applied, setApplied] = useState(null)
  const [status, setStatus] = useState('')
  const [loadingExactCount, setLoadingExactCount] = useState(false)
  const [loadingExport, setLoadingExport] = useState(false)
  const [exactCountRunMs, setExactCountRunMs] = useState(0)
  const [exportRunMs, setExportRunMs] = useState(0)
  const [previewRunMs, setPreviewRunMs] = useState(0)
  const [includeDraft, setIncludeDraft] = useState('')
  const [excludeDraft, setExcludeDraft] = useState('')
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [previewRows, setPreviewRows] = useState([])
  const [previewColumns, setPreviewColumns] = useState([])
  const [previewElapsed, setPreviewElapsed] = useState(null)
  const [countMeta, setCountMeta] = useState(null)
  const [view, setView] = useState('main')
  const [columnFilters, setColumnFilters] = useState({
    Posicion: '',
    Titulo: '',
    Precio: '',
    Descuento: '',
    Estado: '',
    Link: '',
  })

  const canSubmit = useMemo(
    () => Boolean(form.query.trim() || form.search_url.trim() || form.category_url.trim()),
    [form.query, form.search_url, form.category_url],
  )
  const resolvedColumns = previewColumns.length
    ? previewColumns
    : ['Posicion', 'Titulo', 'Precio', 'Descuento', 'Estado', 'Link']

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

  const PREDEFINED_CATEGORIES = [
    { id: 'computacion', name: 'Computación' },
    { id: 'celulares-telefonia', name: 'Celulares y Telefonía' },
    { id: 'electronica', name: 'Electrónica, Audio y Video' },
    { id: 'hogar-muebles', name: 'Hogar y Muebles' },
    { id: 'consolas-videojuegos', name: 'Consolas y Videojuegos' },
    { id: 'deportes-fitness', name: 'Deportes y Fitness' },
    { id: 'herramientas', name: 'Herramientas' },
    { id: 'construccion', name: 'Construcción' },
    { id: 'belleza-cuidado-personal', name: 'Belleza y Cuidado Personal' },
    { id: 'accesorios-para-vehiculos', name: 'Accesorios para Vehículos' },
    { id: 'vestuario-y-calzado', name: 'Vestuario y Calzado' },
    { id: 'juegos-juguetes', name: 'Juegos y Juguetes' },
    { id: 'salud-equipamiento-medico', name: 'Salud y Equipamiento Médico' },
    { id: 'bebes', name: 'Bebés' },
    { id: 'electrodomesticos', name: 'Electrodomésticos' },
  ]

  const updateScanScope = (value) => {
    setForm((prev) => ({
      ...prev,
      scan_scope: value,
      all_results: value === 'complete',
      preview_limit: value === 'complete' && Number(prev.preview_limit) <= 200 ? 1000 : prev.preview_limit,
      max_pages: value === 'complete' && Number(prev.max_pages) === 0 ? 100 : prev.max_pages,
    }))
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

  const addExcludeWord = () => {
    const value = excludeDraft.trim()
    if (!value) return
    setForm((prev) => {
      if (prev.exclude_words.includes(value)) return prev
      return { ...prev, exclude_words: [...prev.exclude_words, value] }
    })
    setExcludeDraft('')
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
        a.download = `mercadolibre_export_${Date.now()}.xlsx`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
        setStatus('Excel exportado correctamente.')
      } catch (err) {
        setStatus(err.message)
      }
    })
  }

  const runExactCount = async () => {
    if (!canSubmit) return
    setStatus('')
    await runWithLiveTimer(setLoadingExactCount, setExactCountRunMs, async () => {
      try {
        const res = await fetch('/api/count-exact', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Error en conteo exacto')
        setExactCount(data.count)
        setExactElapsed(data.elapsed_seconds)
        setCountMeta(data)
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
        setCountMeta(data)
        setView('preview')
      } catch (err) {
        setStatus(err.message)
      }
    })
  }

  if (view === 'preview') {
    return (
      <main className="page">
        <section className="panel preview-page fade-in-section">
          <div className="hero section-reveal fade-1">
            <h1>Previsualizacion de Excel</h1>
            <button className="btn ghost" type="button" onClick={() => setView('main')}>
              <span className="btn-content"><ArrowLeft size={16} />Volver</span>
            </button>
          </div>
          <div className="preview-meta section-reveal fade-2">
            <span>Filas: {filteredPreviewRows.length} / {previewRows.length}</span>
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
                        placeholder={`Filtrar ${col}`}
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
                  <tr className="preview-row" key={`${row.Link}-${idx}`} style={{ animationDelay: `${idx * 20}ms` }}>
                    <td>{row.Posicion}</td>
                    <td>{row.Titulo}</td>
                    <td>{row.Precio}</td>
                    <td>{row.Descuento}</td>
                    <td>{row.Estado}</td>
                    <td>
                      {row.Link ? (
                        <a href={row.Link} target="_blank" rel="noreferrer">
                          abrir
                        </a>
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                ))}
                {!filteredPreviewRows.length && (
                  <tr>
                    <td colSpan={6}>Sin datos con los filtros actuales.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="page">
      <section className="panel visual-panel fade-in-section">
        <div className="hero section-reveal fade-1">
          <h1>MercadoLibre Export UI</h1>
          <span className="badge">Diseno integrado</span>
        </div>
        <p className="hint section-reveal fade-2">
          Configura filtros, calcula cantidad de resultados y exporta Excel sin listar productos.
        </p>

        <div className="section section-reveal fade-3">
          <div className="section-title">
            <Search size={14} /> Busqueda principal
          </div>
          <div className="grid">
          <label>
            Busqueda
            <input value={form.query} onChange={(e) => onChange('query', e.target.value)} />
          </label>
          <label>
            Pais
            <select value={form.country} onChange={(e) => onChange('country', e.target.value)}>
              <option value="cl">Chile</option>
              <option value="ar">Argentina</option>
              <option value="mx">Mexico</option>
              <option value="co">Colombia</option>
              <option value="pe">Peru</option>
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
            Descuento minimo %
            <input
              type="number"
              min="0"
              max="100"
              value={form.min_discount}
              onChange={(e) => onChange('min_discount', Number(e.target.value || 0))}
            />
          </label>
          <label>
            Estado
            <select value={form.condition} onChange={(e) => onChange('condition', e.target.value)}>
              <option value="any">Cualquiera</option>
              <option value="new">Nuevo</option>
              <option value="used">Usado</option>
              <option value="reconditioned">Reacondicionado</option>
            </select>
          </label>
          <label>
            Categoria
            <select
              value={form.category_url}
              onChange={(e) => onChange('category_url', e.target.value)}
            >
              <option value="">Todas las categorias</option>
              {PREDEFINED_CATEGORIES.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Cobertura
            <select value={form.scan_scope} onChange={(e) => updateScanScope(e.target.value)}>
              <option value="fast">Muestra rapida</option>
              <option value="complete">Completa hasta el tope</option>
            </select>
          </label>
          <label className="full">
            Palabras a incluir (dinamico)
            <div className="exclude-editor">
              <input
                placeholder="ej: gamer"
                value={includeDraft}
                onChange={(e) => setIncludeDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addIncludeWord()
                  }
                }}
              />
              <button type="button" onClick={addIncludeWord}>
                Agregar
              </button>
            </div>
            <div className="chips">
              {form.include_words.map((word) => (
                <button
                  className="chip include"
                  key={word}
                  type="button"
                  onClick={() => removeIncludeWord(word)}
                  title="Quitar"
                >
                  {word} x
                </button>
              ))}
            </div>
          </label>
          <label className="full">
            Palabras a descartar (dinamico)
            <div className="exclude-editor">
              <input
                placeholder="ej: carcasa"
                value={excludeDraft}
                onChange={(e) => setExcludeDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addExcludeWord()
                  }
                }}
              />
              <button type="button" onClick={addExcludeWord}>
                Agregar
              </button>
            </div>
            <div className="chips">
              {form.exclude_words.map((word) => (
                <button
                  className="chip exclude"
                  key={word}
                  type="button"
                  onClick={() => removeExcludeWord(word)}
                  title="Quitar"
                >
                  {word} x
                </button>
              ))}
            </div>
          </label>
          <label>
            Tope paginas (0 = sin limite)
            <input
              type="number"
              value={form.max_pages}
              onChange={(e) => onChange('max_pages', Number(e.target.value || 0))}
            />
          </label>
          <label>
            Tope preview/export
            <input
              type="number"
              min="1"
              max="10000"
              value={form.preview_limit}
              onChange={(e) => onChange('preview_limit', Number(e.target.value || 1))}
            />
          </label>
          <label className="full">
            URL exacta (opcional)
            <input
              placeholder="https://listado.mercadolibre.cl/..."
              value={form.search_url}
              onChange={(e) => onChange('search_url', e.target.value)}
            />
          </label>
          <label className="full">
            Archivo cookies (opcional)
            <input value={form.cookie_file} onChange={(e) => onChange('cookie_file', e.target.value)} />
          </label>
        </div>
        </div>

        <div className="section section-reveal fade-4">
          <div className="section-title">
            <Settings2 size={14} /> Configuracion de ejecucion
          </div>
        <div className="checks">
          <label className="switch-card">
            <span>Buscar todas las paginas</span>
            <input
              type="checkbox"
              checked={form.all_results}
              onChange={(e) => onChange('all_results', e.target.checked)}
            />
            <span className="switch">
              <span className="switch-knob" />
            </span>
          </label>
          <label className="switch-card">
            <span>Ordenar por precio</span>
            <input
              type="checkbox"
              checked={form.sort_price}
              onChange={(e) => onChange('sort_price', e.target.checked)}
            />
            <span className="switch">
              <span className="switch-knob" />
            </span>
          </label>
          <label className="switch-card">
            <span>Incluir internacionales</span>
            <input
              type="checkbox"
              checked={form.include_international}
              onChange={(e) => onChange('include_international', e.target.checked)}
            />
            <span className="switch">
              <span className="switch-knob" />
            </span>
          </label>
        </div>
        </div>

        <div className="actions section-reveal fade-5">
          <button className="btn warn" disabled={!canSubmit || loadingExactCount} onClick={runExactCount}>
            {loadingExactCount ? (
              <span className="btn-content">
                <span className="loader" />
                Calculando exacto... {(exactCountRunMs / 1000).toFixed(1)}s
              </span>
            ) : (
              <span className="btn-content"><Calculator size={16} />Calcular cantidad</span>
            )}
          </button>
          <button className="btn info" disabled={!canSubmit || loadingPreview} onClick={runPreview}>
            {loadingPreview ? (
              <span className="btn-content">
                <span className="loader" />
                Cargando tabla... {(previewRunMs / 1000).toFixed(1)}s
              </span>
            ) : (
              <span className="btn-content"><SlidersHorizontal size={16} />Previsualizar tabla</span>
            )}
          </button>
          <button className="btn outline" disabled={!canSubmit || loadingExport} onClick={runExport}>
            {loadingExport ? (
              <span className="btn-content">
                <span className="loader" />
                Exportando... {(exportRunMs / 1000).toFixed(1)}s
              </span>
            ) : (
              <span className="btn-content"><FileSpreadsheet size={16} />Exportar Excel</span>
            )}
          </button>
        </div>

        <div className="results section-reveal fade-6">
          <div className="section-title">
            <SlidersHorizontal size={14} /> Resumen
          </div>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-icon"><Hash size={14} /></div>
              <div>
                <div className="kpi-label">Resultados</div>
                <div className="kpi-value">{exactCount ?? '-'}</div>
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-icon"><Clock3 size={14} /></div>
              <div>
                <div className="kpi-label">Tiempo</div>
                <div className="kpi-value">{exactElapsed != null ? `${exactElapsed}s` : '-'}</div>
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-icon"><SlidersHorizontal size={14} /></div>
              <div>
                <div className="kpi-label">Paginas / items</div>
                <div className="kpi-value">
                  {countMeta ? `${countMeta.pages_fetched || 0} / ${countMeta.fetched_raw || 0}` : '-'}
                </div>
              </div>
            </div>
          </div>
          {applied && (
            <div className="applied-filters">
              <Globe size={13} /> include=[{(applied.include_words || []).join(', ')}] exclude=[
              {(applied.exclude_words || []).join(', ')}] country={applied.country}
            </div>
          )}
          {status && <div className="status status-pulse">{status}</div>}
          {(loadingExactCount || loadingExport || loadingPreview) && (
            <div className="running-hint">
              Proceso activo: {loadingExactCount ? 'calculo exacto' : loadingPreview ? 'previsualizacion' : 'exportacion de Excel'}
            </div>
          )}
        </div>
        <footer className="foot">MercadoLibre Export Tool v2.0 - Datos para uso personal.</footer>
      </section>
    </main>
  )
}

export default App
