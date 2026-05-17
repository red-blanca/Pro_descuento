import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Calculator, Clock3, Cookie, FileJson, Globe, Hash, Search, Settings2, ShieldCheck, ShieldAlert, ShieldX, SlidersHorizontal } from 'lucide-react'
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
    strict_mode: false,
    smart_filter: true,
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
  const [cookieModalOpen, setCookieModalOpen] = useState(false)
  const [cookieRawText, setCookieRawText] = useState('')
  const [cookieStatus, setCookieStatus] = useState(null)
  const [cookieSaving, setCookieSaving] = useState(false)
  const [cookieMsg, setCookieMsg] = useState('')
  const [facebookCookieStatus, setFacebookCookieStatus] = useState(null)
  const [facebookCookieProfile, setFacebookCookieProfile] = useState('curico')
  const [facebookCookieRawText, setFacebookCookieRawText] = useState('')
  const [facebookCookieSaving, setFacebookCookieSaving] = useState(false)
  const [facebookCookieMsg, setFacebookCookieMsg] = useState('')
  const [globalForm, setGlobalForm] = useState({
    query: '',
    scan_scope: 'fast',
    max_items_per_source: 10000,
    min_price: 0,
    max_price: 0,
    min_discount: 0,
    include_words_text: '',
    exclude_words_text: '',
    sources: [
      'mercadolibre',
      'facebook_marketplace',
      'pulga',
      'knasta',
      'solotodo',
      'travel',
      'tuganga',
      'descuentosrata',
    ],
    mercadolibre_word: '',
    mercadolibre_search_url: '',
    mercadolibre_condition: 'used',
    sort_price: false,
    include_international: false,
    facebook_word: '',
    facebook_marketplace_path: 'curico',
    facebook_location_query: 'Curico, Maule, Chile',
    facebook_latitude: -34.98749193781055,
    facebook_longitude: -71.24675716218236,
    facebook_radius_km: 35,
    facebook_include_talca: true,
    pulga_category: 'tecnologia',
    pulga_condition: 'any',
    pulga_city: '',
    pulga_word: '',
    knasta_category: '20106',
    knasta_retails_text: '',
    knasta_knastaday: 0,
    solotodo_category_id: 4,
    solotodo_country_id: 1,
    solotodo_ordering: 'offer_price_usd',
    travel_category_id: 'TiendaMonitores',
    travel_ordering: 'relevance',
    tuganga_mode: 'all_offers',
    tuganga_stores_text: '',
    tuganga_category: '',
    tuganga_only_available: false,
    tuganga_sort: '',
    descuentosrata_all: true,
    descuentosrata_limit: 10000,
    strict_mode: false,
    smart_filter: true,
  })
  const [globalResult, setGlobalResult] = useState(null)
  const [globalStatus, setGlobalStatus] = useState('')
  const [globalLoading, setGlobalLoading] = useState(false)
  const [globalRunMs, setGlobalRunMs] = useState(0)
  const [globalCategories, setGlobalCategories] = useState({
    pulga: [],
    knasta: [],
    solotodo: [],
    travel: [],
    tuganga: [],
  })
  const [globalCategoriesLoading, setGlobalCategoriesLoading] = useState(false)

  const fetchCookieStatus = async () => {
    try {
      const res = await fetch('/api/cookies/status')
      if (res.ok) {
        const data = await res.json()
        setCookieStatus(data)
      }
    } catch {
      // Cookie status is optional; the rest of the UI can load without it.
    }
  }

  const fetchFacebookCookieStatus = async () => {
    try {
      const res = await fetch('/api/facebook-cookies/status')
      if (res.ok) {
        const data = await res.json()
        setFacebookCookieStatus(data)
      }
    } catch {
      // Facebook cookie status is optional; searches will report errors if needed.
    }
  }

  useEffect(() => {
    fetchCookieStatus()
    fetchFacebookCookieStatus()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const loadGlobalCategories = async () => {
      setGlobalCategoriesLoading(true)
      try {
        const params = new URLSearchParams({
          query: globalForm.query.trim(),
          knasta_knastaday: String(globalForm.knasta_knastaday || 0),
          knasta_retails: globalForm.knasta_retails_text,
          tuganga_mode: globalForm.tuganga_mode,
        })
        const res = await fetch(`/api/global-categories?${params.toString()}`, { signal: controller.signal })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'No se pudieron cargar categorias')
        setGlobalCategories(data.categories || {})
      } catch (err) {
        if (err.name !== 'AbortError') {
          setGlobalCategories((prev) => prev)
        }
      } finally {
        if (!controller.signal.aborted) setGlobalCategoriesLoading(false)
      }
    }
    loadGlobalCategories()
    return () => controller.abort()
  }, [globalForm.query, globalForm.knasta_knastaday, globalForm.knasta_retails_text, globalForm.tuganga_mode])

  const saveCookies = async () => {
    if (!cookieRawText.trim()) return
    setCookieSaving(true)
    setCookieMsg('')
    try {
      const res = await fetch('/api/cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: cookieRawText }),
      })
      if (!res.ok) {
        let errorMsg = 'Error guardando cookies'
        try {
          const data = await res.json()
          errorMsg = data.detail || errorMsg
        } catch {
          // Ignore JSON parse error
        }
        throw new Error(errorMsg)
      }
      const data = await res.json()
      setCookieMsg(`✅ ${data.cookie_count} cookies guardadas correctamente`)
      setCookieRawText('')
      await fetchCookieStatus()
    } catch (err) {
      setCookieMsg(`❌ ${err.message}`)
    } finally {
      setCookieSaving(false)
    }
  }

  const saveFacebookCookies = async () => {
    if (!facebookCookieRawText.trim()) return
    setFacebookCookieSaving(true)
    setFacebookCookieMsg('')
    try {
      const res = await fetch('/api/facebook-cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile: facebookCookieProfile,
          raw_text: facebookCookieRawText,
        }),
      })
      if (!res.ok) {
        let errorMsg = 'Error guardando cookies de Facebook'
        try {
          const data = await res.json()
          errorMsg = data.detail || errorMsg
        } catch {
          // Ignore JSON parse error
        }
        throw new Error(errorMsg)
      }
      const data = await res.json()
      setFacebookCookieMsg(`${data.cookie_count} cookies guardadas para ${data.profile}`)
      setFacebookCookieRawText('')
      await fetchFacebookCookieStatus()
    } catch (err) {
      setFacebookCookieMsg(err.message)
    } finally {
      setFacebookCookieSaving(false)
    }
  }

  const cookieHealth = useMemo(() => {
    if (!cookieStatus || !cookieStatus.exists || cookieStatus.cookie_count === 0) {
      return { color: 'red', label: 'Sin cookies', icon: 'x' }
    }
    const age = cookieStatus.age_minutes ?? 9999
    const hasEssential = (cookieStatus.essential_found || []).length >= 2
    if (age > 180 || !hasEssential) {
      return { color: 'yellow', label: `${Math.round(age)}min - Posiblemente expiradas`, icon: 'warn' }
    }
    return { color: 'green', label: `${Math.round(age)}min - Activas`, icon: 'ok' }
  }, [cookieStatus])

  const facebookCookieHealth = useMemo(() => {
    if (!facebookCookieStatus || !facebookCookieStatus.exists) {
      return { color: 'red', label: 'Facebook sin cookies', icon: 'x' }
    }
    if (!facebookCookieStatus.all_valid) {
      return { color: 'yellow', label: 'Facebook incompleto', icon: 'warn' }
    }
    return { color: 'green', label: 'Facebook listo', icon: 'ok' }
  }, [facebookCookieStatus])

  const canSubmit = useMemo(
    () => Boolean(form.query.trim() || form.search_url.trim() || form.category_url.trim()),
    [form.query, form.search_url, form.category_url],
  )
  const canGlobalSubmit = useMemo(
    () => Boolean(globalForm.query.trim() || (globalForm.sources.length === 1 && globalForm.sources[0] === 'descuentosrata')),
    [globalForm.query, globalForm.sources],
  )
  const resolvedColumns = useMemo(
    () => previewColumns.length
      ? previewColumns
      : ['Posicion', 'Titulo', 'Precio', 'Descuento', 'Estado', 'Link'],
    [previewColumns],
  )

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

  const onGlobalChange = (key, value) => {
    setGlobalForm((prev) => ({ ...prev, [key]: value }))
  }

  const toggleGlobalSource = (source) => {
    setGlobalForm((prev) => {
      const exists = prev.sources.includes(source)
      const sources = exists ? prev.sources.filter((item) => item !== source) : [...prev.sources, source]
      return { ...prev, sources }
    })
  }

  const csvToList = (value) =>
    String(value || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)

  const buildGlobalPayload = () => ({
    ...globalForm,
    include_words: csvToList(globalForm.include_words_text),
    exclude_words: csvToList(globalForm.exclude_words_text),
    knasta_retails: csvToList(globalForm.knasta_retails_text),
    tuganga_stores: csvToList(globalForm.tuganga_stores_text),
    tuganga_categories: globalForm.tuganga_category ? [globalForm.tuganga_category] : [],
  })

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
          let errorMsg = 'Error exportando'
          try {
            const data = await res.json()
            errorMsg = data.detail || errorMsg
          } catch {
            // Ignore JSON parse error on 500
          }
          throw new Error(errorMsg)
        }
        const blob = await res.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `mercadolibre_export_${Date.now()}.json`
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

  const safeJson = async (res) => {
    const text = await res.text()
    try {
      return JSON.parse(text)
    } catch {
      if (text.trimStart().startsWith('<')) {
        throw new Error(
          res.status === 502
            ? 'Timeout del servidor (502). Intenta con menos fuentes o modo rapido.'
            : `El servidor respondio con HTML en vez de JSON (status ${res.status})`
        )
      }
      throw new Error(`Respuesta invalida del servidor (status ${res.status})`)
    }
  }

  const pollGlobalJob = async (jobId) => {
    // Poll every 2 seconds until the job finishes
    while (true) {
      await new Promise((r) => setTimeout(r, 2000))
      const res = await fetch(`/api/global-search/${jobId}`)
      const data = await safeJson(res)
      if (!res.ok) throw new Error(data.detail || 'Error consultando estado del job')
      if (data.status === 'error') throw new Error(data.error || 'Error en busqueda conjunta')
      if (data.status === 'done') return data
      // Still running — update status and keep polling
      setGlobalStatus(`Buscando... ${data.elapsed_seconds}s`)
    }
  }

  const startGlobalJob = async () => {
    const res = await fetch('/api/global-search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildGlobalPayload()),
    })
    const data = await safeJson(res)
    if (!res.ok) throw new Error(data.detail || 'Error iniciando busqueda conjunta')
    return data.job_id
  }

  const runGlobalSearch = async () => {
    if (!canGlobalSubmit) return
    setGlobalStatus('')
    setGlobalResult(null)
    setGlobalLoading(true)
    setGlobalRunMs(0)
    const startedAt = performance.now()
    const tick = setInterval(() => setGlobalRunMs(performance.now() - startedAt), 120)
    try {
      const jobId = await startGlobalJob()
      setGlobalStatus('Busqueda iniciada, esperando resultados...')
      const data = await pollGlobalJob(jobId)
      setGlobalResult(data)
      setGlobalStatus(`Busqueda lista: ${data.total_count} resultados en ${data.elapsed_seconds}s`)
    } catch (err) {
      setGlobalStatus(err.message)
    } finally {
      clearInterval(tick)
      setGlobalRunMs(performance.now() - startedAt)
      setGlobalLoading(false)
    }
  }

  const downloadGlobalJson = async () => {
    if (!canGlobalSubmit) return
    setGlobalStatus('')

    // If we already have results loaded, download directly from memory
    let data = globalResult
    if (!data || !data.items || !data.items.length) {
      // No results yet — run the search first via polling
      setGlobalLoading(true)
      setGlobalRunMs(0)
      const startedAt = performance.now()
      const tick = setInterval(() => setGlobalRunMs(performance.now() - startedAt), 120)
      try {
        const jobId = await startGlobalJob()
        setGlobalStatus('Busqueda iniciada, esperando resultados...')
        data = await pollGlobalJob(jobId)
        setGlobalResult(data)
        setGlobalStatus(`Busqueda lista: ${data.total_count} resultados en ${data.elapsed_seconds}s`)
      } catch (err) {
        setGlobalStatus(err.message)
        return
      } finally {
        clearInterval(tick)
        setGlobalRunMs(performance.now() - startedAt)
        setGlobalLoading(false)
      }
    }

    if (!data || !data.items || !data.items.length) {
      setGlobalStatus('No hay resultados para descargar.')
      return
    }

    // Generate and download JSON from client memory — instant, no timeout
    const jsonStr = JSON.stringify(data.items, null, 2)
    const blob = new Blob([jsonStr], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `global_search_${Date.now()}.json`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
    setGlobalStatus(`JSON combinado descargado (${data.items.length} items)`)
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
            <h1>Previsualizacion de datos</h1>
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
          <div className="hero-actions">
            <button
              className={`cookie-status-btn cookie-${cookieHealth.color}`}
              type="button"
              onClick={() => { setCookieMsg(''); setFacebookCookieMsg(''); setCookieModalOpen(true) }}
              title="Gestionar cookies de MercadoLibre"
            >
              {cookieHealth.icon === 'ok' && <ShieldCheck size={14} />}
              {cookieHealth.icon === 'warn' && <ShieldAlert size={14} />}
              {cookieHealth.icon === 'x' && <ShieldX size={14} />}
              <span>{cookieHealth.label}</span>
            </button>
            <button
              className={`cookie-status-btn cookie-${facebookCookieHealth.color}`}
              type="button"
              onClick={() => { setCookieMsg(''); setFacebookCookieMsg(''); setCookieModalOpen(true) }}
              title="Gestionar cookies de Facebook Marketplace"
            >
              {facebookCookieHealth.icon === 'ok' && <ShieldCheck size={14} />}
              {facebookCookieHealth.icon === 'warn' && <ShieldAlert size={14} />}
              {facebookCookieHealth.icon === 'x' && <ShieldX size={14} />}
              <span>{facebookCookieHealth.label}</span>
            </button>
            <span className="badge">Diseno integrado</span>
          </div>
        </div>
        <p className="hint section-reveal fade-2">
          Configura filtros, calcula cantidad de resultados y exporta JSON sin listar productos.
        </p>

        <div className="section section-reveal fade-3 global-search-box">
          <div className="section-title">
            <Globe size={14} /> Busqueda conjunta
          </div>
          <div className="grid">
            <label>
              Busqueda unica
              <input value={globalForm.query} onChange={(e) => onGlobalChange('query', e.target.value)} />
            </label>
            <label>
              Alcance
              <select value={globalForm.scan_scope} onChange={(e) => onGlobalChange('scan_scope', e.target.value)}>
                <option value="fast">Rapido</option>
                <option value="complete">Completo</option>
              </select>
            </label>
            <label>
              Tope por fuente
              <input
                type="number"
                min="1"
                max="10000"
                value={globalForm.max_items_per_source}
                onChange={(e) => onGlobalChange('max_items_per_source', Number(e.target.value || 1))}
              />
            </label>
            <label>
              Precio minimo
              <input
                type="number"
                value={globalForm.min_price}
                onChange={(e) => onGlobalChange('min_price', Number(e.target.value || 0))}
              />
            </label>
            <label>
              Precio maximo
              <input
                type="number"
                value={globalForm.max_price}
                onChange={(e) => onGlobalChange('max_price', Number(e.target.value || 0))}
              />
            </label>
            <label>
              Descuento minimo
              <input
                type="number"
                min="0"
                max="100"
                value={globalForm.min_discount}
                onChange={(e) => onGlobalChange('min_discount', Number(e.target.value || 0))}
              />
            </label>
            <label>
              Incluir palabras
              <input
                placeholder="gamer, ips"
                value={globalForm.include_words_text}
                onChange={(e) => onGlobalChange('include_words_text', e.target.value)}
              />
            </label>
            <label>
              Excluir palabras
              <input
                placeholder="repuesto, carcasa"
                value={globalForm.exclude_words_text}
                onChange={(e) => onGlobalChange('exclude_words_text', e.target.value)}
              />
            </label>
            <div className="full global-advanced-checks">
              <label className="source-check">
                <input
                  type="checkbox"
                  checked={globalForm.strict_mode}
                  onChange={(e) => onGlobalChange('strict_mode', e.target.checked)}
                />
                <span title="Coincidencia de palabras completas">Modo estricto</span>
              </label>
              <label className="source-check">
                <input
                  type="checkbox"
                  checked={globalForm.smart_filter}
                  onChange={(e) => onGlobalChange('smart_filter', e.target.checked)}
                />
                <span title="Filtro automatico de accesorios">Filtro anti-basura</span>
              </label>
            </div>
          </div>
          <div className="source-grid">
            {[
              ['mercadolibre', 'MercadoLibre'],
              ['facebook_marketplace', 'Facebook'],
              ['pulga', 'Pulga'],
              ['knasta', 'Knasta'],
              ['solotodo', 'SoloTodo'],
              ['travel', 'Travel'],
              ['tuganga', 'TuGanga'],
              ['descuentosrata', 'DescuentosRata'],
            ].map(([key, label]) => (
              <label className="source-check" key={key}>
                <input
                  type="checkbox"
                  checked={globalForm.sources.includes(key)}
                  onChange={() => toggleGlobalSource(key)}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <div className="source-accordions">
            <details className="source-accordion">
              <summary>MercadoLibre</summary>
              <div className="grid">
                <label>
                  Pais
                  <select value={globalForm.country} onChange={(e) => onGlobalChange('country', e.target.value)}>
                    <option value="cl">Chile</option>
                    <option value="ar">Argentina</option>
                    <option value="mx">Mexico</option>
                    <option value="co">Colombia</option>
                    <option value="pe">Peru</option>
                  </select>
                </label>
                <label>
                  Estado
                  <select value={globalForm.mercadolibre_condition} onChange={(e) => onGlobalChange('mercadolibre_condition', e.target.value)}>
                    <option value="any">Cualquiera</option>
                    <option value="new">Nuevo</option>
                    <option value="used">Usado</option>
                    <option value="reconditioned">Reacondicionado</option>
                  </select>
                </label>
                <label>
                  Palabra obligatoria
                  <input value={globalForm.mercadolibre_word} onChange={(e) => onGlobalChange('mercadolibre_word', e.target.value)} />
                </label>
                <label className="full">
                  URL exacta
                  <input value={globalForm.mercadolibre_search_url} onChange={(e) => onGlobalChange('mercadolibre_search_url', e.target.value)} />
                </label>
              </div>
              <div className="source-inline-checks">
                <label className="source-check">
                  <input type="checkbox" checked={globalForm.sort_price} onChange={(e) => onGlobalChange('sort_price', e.target.checked)} />
                  <span>Ordenar por precio</span>
                </label>
                <label className="source-check">
                  <input type="checkbox" checked={globalForm.include_international} onChange={(e) => onGlobalChange('include_international', e.target.checked)} />
                  <span>Incluir internacionales</span>
                </label>
              </div>
            </details>
            <details className="source-accordion">
              <summary>Facebook Marketplace</summary>
              <div className="grid">
                <label>
                  Marketplace path
                  <input value={globalForm.facebook_marketplace_path} onChange={(e) => onGlobalChange('facebook_marketplace_path', e.target.value)} />
                </label>
                <label>
                  Palabra obligatoria
                  <input value={globalForm.facebook_word} onChange={(e) => onGlobalChange('facebook_word', e.target.value)} />
                </label>
                <label>
                  Ubicacion
                  <input value={globalForm.facebook_location_query} onChange={(e) => onGlobalChange('facebook_location_query', e.target.value)} />
                </label>
                <label>
                  Radio km
                  <input type="number" value={globalForm.facebook_radius_km} onChange={(e) => onGlobalChange('facebook_radius_km', Number(e.target.value || 1))} />
                </label>
                <label>
                  Latitud
                  <input type="number" step="0.000001" value={globalForm.facebook_latitude ?? ''} onChange={(e) => onGlobalChange('facebook_latitude', Number(e.target.value || 0))} />
                </label>
                <label>
                  Longitud
                  <input type="number" step="0.000001" value={globalForm.facebook_longitude ?? ''} onChange={(e) => onGlobalChange('facebook_longitude', Number(e.target.value || 0))} />
                </label>
              </div>
              <label className="source-check standalone">
                <input type="checkbox" checked={globalForm.facebook_include_talca} onChange={(e) => onGlobalChange('facebook_include_talca', e.target.checked)} />
                <span>Incluir Talca</span>
              </label>
            </details>
            <details className="source-accordion">
              <summary>Pulga</summary>
              <div className="grid">
                <label>
                  Categoria
                  <select value={globalForm.pulga_category} onChange={(e) => onGlobalChange('pulga_category', e.target.value)}>
                    {(globalCategories.pulga || []).map((category) => (
                      <option key={category.value} value={category.value}>{category.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Condicion
                  <select value={globalForm.pulga_condition} onChange={(e) => onGlobalChange('pulga_condition', e.target.value)}>
                    <option value="any">Cualquiera</option>
                    <option value="new">Nuevo</option>
                    <option value="used">Usado</option>
                  </select>
                </label>
                <label>
                  Ciudad
                  <input value={globalForm.pulga_city} onChange={(e) => onGlobalChange('pulga_city', e.target.value)} />
                </label>
                <label>
                  Palabra obligatoria
                  <input value={globalForm.pulga_word} onChange={(e) => onGlobalChange('pulga_word', e.target.value)} />
                </label>
              </div>
            </details>
            <details className="source-accordion">
              <summary>Knasta</summary>
              <div className="grid">
                <label>
                  Categoria
                  <select value={globalForm.knasta_category} onChange={(e) => onGlobalChange('knasta_category', e.target.value)} disabled={globalCategoriesLoading}>
                    <option value="">{globalCategoriesLoading ? 'Cargando categorias...' : 'Todas las categorias'}</option>
                    {(globalCategories.knasta || []).map((category) => (
                      <option key={category.value} value={category.value}>
                        {category.label}{category.count != null ? ` (${Number(category.count).toLocaleString('es-CL')})` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Retails
                  <input placeholder="pcfactory, paris" value={globalForm.knasta_retails_text} onChange={(e) => onGlobalChange('knasta_retails_text', e.target.value)} />
                </label>
                <label>
                  KnastaDay
                  <input type="number" min="0" value={globalForm.knasta_knastaday} onChange={(e) => onGlobalChange('knasta_knastaday', Number(e.target.value || 0))} />
                </label>
              </div>
            </details>
            <details className="source-accordion">
              <summary>SoloTodo</summary>
              <div className="grid">
                <label>
                  Categoria ID
                  <select value={String(globalForm.solotodo_category_id)} onChange={(e) => onGlobalChange('solotodo_category_id', Number(e.target.value || 0))} disabled={globalCategoriesLoading}>
                    <option value="0">{globalCategoriesLoading ? 'Cargando categorias...' : 'Todas'}</option>
                    {(globalCategories.solotodo || []).map((category) => (
                      <option key={category.value} value={category.value}>{category.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Pais ID
                  <input type="number" value={globalForm.solotodo_country_id} onChange={(e) => onGlobalChange('solotodo_country_id', Number(e.target.value || 1))} />
                </label>
                <label>
                  Orden
                  <input value={globalForm.solotodo_ordering} onChange={(e) => onGlobalChange('solotodo_ordering', e.target.value)} />
                </label>
              </div>
            </details>
            <details className="source-accordion">
              <summary>Travel</summary>
              <div className="grid">
                <label>
                  Categoria ID
                  <select value={globalForm.travel_category_id} onChange={(e) => onGlobalChange('travel_category_id', e.target.value)} disabled={globalCategoriesLoading}>
                    <option value="">{globalCategoriesLoading ? 'Cargando categorias...' : 'Todas las categorias'}</option>
                    {(globalCategories.travel || []).map((category) => (
                      <option key={category.value} value={category.value}>
                        {'  '.repeat(Math.min(category.depth || 0, 4))}{category.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Orden
                  <select value={globalForm.travel_ordering} onChange={(e) => onGlobalChange('travel_ordering', e.target.value)}>
                    <option value="relevance">Relevancia</option>
                    <option value="price_asc">Precio ascendente</option>
                    <option value="price_desc">Precio descendente</option>
                    <option value="discount_desc">Descuento descendente</option>
                    <option value="name_asc">Nombre ascendente</option>
                  </select>
                </label>
              </div>
            </details>
            <details className="source-accordion">
              <summary>TuGanga</summary>
              <div className="grid">
                <label>
                  Modo
                  <select value={globalForm.tuganga_mode} onChange={(e) => onGlobalChange('tuganga_mode', e.target.value)}>
                    <option value="search">Busqueda</option>
                    <option value="offers">Ofertas</option>
                    <option value="all_offers">Todas ofertas</option>
                    <option value="minimums">Minimos</option>
                    <option value="best">Mejores</option>
                  </select>
                </label>
                <label>
                  Tiendas
                  <input placeholder="lider, ripley" value={globalForm.tuganga_stores_text} onChange={(e) => onGlobalChange('tuganga_stores_text', e.target.value)} />
                </label>
                <label className="full">
                  Categoria
                  <select
                    value={globalForm.tuganga_category}
                    onChange={(e) => onGlobalChange('tuganga_category', e.target.value)}
                    disabled={globalCategoriesLoading}
                  >
                    <option value="">
                      {globalCategoriesLoading ? 'Cargando categorias...' : 'Todas las categorias'}
                    </option>
                    {(globalCategories.tuganga || []).map((category) => (
                      <option key={category.value} value={category.value}>
                        {category.label}{category.count != null ? ` (${Number(category.count).toLocaleString('es-CL')})` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Orden
                  <input value={globalForm.tuganga_sort} onChange={(e) => onGlobalChange('tuganga_sort', e.target.value)} />
                </label>
              </div>
              <label className="source-check standalone">
                <input type="checkbox" checked={globalForm.tuganga_only_available} onChange={(e) => onGlobalChange('tuganga_only_available', e.target.checked)} />
                <span>Solo disponibles</span>
              </label>
            </details>
            <details className="source-accordion">
              <summary>DescuentosRata</summary>
              <div className="grid">
                <label>
                  Limite
                  <input type="number" min="1" max="10000" value={globalForm.descuentosrata_limit} onChange={(e) => onGlobalChange('descuentosrata_limit', Number(e.target.value || 1))} />
                </label>
              </div>
              <label className="source-check standalone">
                <input
                  type="checkbox"
                  checked={globalForm.descuentosrata_all}
                  onChange={(e) => onGlobalChange('descuentosrata_all', e.target.checked)}
                />
                <span>Traer todas sus ofertas disponibles</span>
              </label>
            </details>
          </div>
          <div className="actions compact-actions">
            <button className="btn warn" disabled={!canGlobalSubmit || globalLoading} onClick={runGlobalSearch}>
              {globalLoading ? (
                <span className="btn-content"><span className="loader" />Ejecutando... {(globalRunMs / 1000).toFixed(1)}s</span>
              ) : (
                <span className="btn-content"><Search size={16} />Ejecutar todas</span>
              )}
            </button>
            <button className="btn outline" disabled={!canGlobalSubmit || globalLoading} onClick={downloadGlobalJson}>
              <span className="btn-content"><FileJson size={16} />Descargar combinado</span>
            </button>
          </div>
          {globalStatus && <div className="status status-pulse">{globalStatus}</div>}
          {globalResult && (
            <div className="global-summary">
              <div className="global-files">
                <strong>Combinado:</strong> {globalResult.all_results_file}
              </div>
              <div className="source-results">
                {(globalResult.runs || []).map((run) => (
                  <div className={`source-result ${run.ok ? 'ok' : 'fail'}`} key={run.source}>
                    <span>{run.source}</span>
                    <strong>{run.count}</strong>
                    <small>{run.warning || run.output_file || run.error}</small>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

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
          <label className="switch-card highlight">
            <span title="Busca palabras exactas en lugar de fragmentos">Coincidencia estricta</span>
            <input
              type="checkbox"
              checked={form.strict_mode}
              onChange={(e) => onChange('strict_mode', e.target.checked)}
            />
            <span className="switch">
              <span className="switch-knob" />
            </span>
          </label>
          <label className="switch-card highlight">
            <span title="Elimina automaticamente accesorios si no los estas buscando">Filtro anti-basura</span>
            <input
              type="checkbox"
              checked={form.smart_filter}
              onChange={(e) => onChange('smart_filter', e.target.checked)}
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
              <span className="btn-content"><FileJson size={16} />Exportar JSON</span>
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
              Proceso activo: {loadingExactCount ? 'calculo exacto' : loadingPreview ? 'previsualizacion' : 'exportacion JSON'}
            </div>
          )}
        </div>
        <footer className="foot">MercadoLibre Export Tool v2.0 - Datos para uso personal.</footer>
      </section>

      {cookieModalOpen && (
        <div className="modal-overlay" onClick={() => setCookieModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2><Cookie size={20} /> Gestionar Cookies</h2>
              <button className="modal-close" onClick={() => setCookieModalOpen(false)}>×</button>
            </div>

            <div className="cookie-info">
              {cookieStatus && cookieStatus.exists ? (
                <div className={`cookie-badge cookie-badge-${cookieHealth.color}`}>
                  {cookieHealth.icon === 'ok' && <ShieldCheck size={16} />}
                  {cookieHealth.icon === 'warn' && <ShieldAlert size={16} />}
                  {cookieHealth.icon === 'x' && <ShieldX size={16} />}
                  <div>
                    <div className="cookie-badge-title">{cookieStatus.cookie_count} cookies guardadas</div>
                    <div className="cookie-badge-sub">
                      Ultima actualizacion: {cookieStatus.age_minutes != null ? `hace ${Math.round(cookieStatus.age_minutes)} min` : 'desconocida'}
                    </div>
                    {cookieStatus.essential_found && (
                      <div className="cookie-badge-sub">
                        Esenciales: {cookieStatus.essential_found.join(', ') || 'ninguna'}
                        {cookieStatus.essential_missing?.length > 0 && (
                          <span className="cookie-missing"> | Faltan: {cookieStatus.essential_missing.join(', ')}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="cookie-badge cookie-badge-red">
                  <ShieldX size={16} />
                  <div>
                    <div className="cookie-badge-title">No hay cookies guardadas</div>
                    <div className="cookie-badge-sub">Pega las cookies de MercadoLibre abajo</div>
                  </div>
                </div>
              )}
            </div>

            <div className="cookie-instructions">
              <p><strong>Como obtener cookies:</strong></p>
              <ol>
                <li>Abre <a href="https://www.mercadolibre.cl" target="_blank" rel="noreferrer">mercadolibre.cl</a> e inicia sesion</li>
                <li>Presiona <code>F12</code> → pestaña <strong>Application</strong> → <strong>Cookies</strong></li>
                <li>Selecciona todas las filas (<code>Ctrl+A</code>) and copia (<code>Ctrl+C</code>)</li>
                <li>Pega aqui abajo</li>
              </ol>
            </div>

            <textarea
              className="cookie-textarea"
              placeholder={'Pega las cookies aqui...\n\nFormato aceptado:\n_csrf\tPQa_QjypzV5eo7Td...\twww.mercadolibre.cl\t/\t...\n_d2id\tedd0f3e4-dfd4...\t.mercadoclics.com\t/\t...'}
              value={cookieRawText}
              onChange={(e) => setCookieRawText(e.target.value)}
              rows={10}
            />

            {cookieMsg && <div className="cookie-feedback">{cookieMsg}</div>}

            <div className="cookie-info">
              <div className={`cookie-badge cookie-badge-${facebookCookieHealth.color}`}>
                {facebookCookieHealth.icon === 'ok' && <ShieldCheck size={16} />}
                {facebookCookieHealth.icon === 'warn' && <ShieldAlert size={16} />}
                {facebookCookieHealth.icon === 'x' && <ShieldX size={16} />}
                <div>
                  <div className="cookie-badge-title">Facebook Marketplace</div>
                  <div className="cookie-badge-sub">
                    Curico: {facebookCookieStatus?.profiles?.curico?.valid ? 'OK' : 'pendiente'} | Talca: {facebookCookieStatus?.profiles?.talca?.valid ? 'OK' : 'pendiente'}
                  </div>
                  {facebookCookieStatus?.message && (
                    <div className="cookie-badge-sub">{facebookCookieStatus.message}</div>
                  )}
                </div>
              </div>
            </div>

            <div className="cookie-instructions">
              <p><strong>Cookies de Facebook Marketplace:</strong></p>
              <ol>
                <li>Abre Marketplace con la cuenta/perfil correspondiente</li>
                <li>Fija la ubicacion en Curico o Talca antes de copiar</li>
                <li>Copia todas las filas desde Application Cookies facebook.com</li>
                <li>Elige el perfil y pega el texto abajo</li>
              </ol>
            </div>

            <label>
              Perfil Facebook
              <select value={facebookCookieProfile} onChange={(e) => setFacebookCookieProfile(e.target.value)}>
                <option value="curico">Curico</option>
                <option value="talca">Talca</option>
              </select>
            </label>

            <textarea
              className="cookie-textarea"
              placeholder={'Pega cookies de Facebook aqui...\n\nFormato aceptado:\nc_user\t100...\t.facebook.com\t/\t...\nxs\t...\t.facebook.com\t/\t...'}
              value={facebookCookieRawText}
              onChange={(e) => setFacebookCookieRawText(e.target.value)}
              rows={8}
            />

            {facebookCookieMsg && <div className="cookie-feedback">{facebookCookieMsg}</div>}

            <div className="modal-actions">
              <button
                className="btn warn"
                disabled={!facebookCookieRawText.trim() || facebookCookieSaving}
                onClick={saveFacebookCookies}
              >
                <span className="btn-content">
                  {facebookCookieSaving ? <><span className="loader" /> Guardando...</> : <><Cookie size={16} /> Guardar Facebook</>}
                </span>
              </button>
            </div>

            <div className="modal-actions">
              <button
                className="btn warn"
                disabled={!cookieRawText.trim() || cookieSaving}
                onClick={saveCookies}
              >
                <span className="btn-content">
                  {cookieSaving ? <><span className="loader" /> Guardando...</> : <><Cookie size={16} /> Guardar Cookies</>}
                </span>
              </button>
              <button className="btn ghost" onClick={() => setCookieModalOpen(false)}>
                <span className="btn-content">Cerrar</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

export default App
