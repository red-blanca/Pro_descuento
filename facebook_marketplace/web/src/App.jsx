import { useMemo, useState, useEffect } from 'react'
import {
  ArrowLeft, Clock3, Cookie, FileSpreadsheet, Hash,
  Search, SlidersHorizontal, Store, AlertTriangle, CheckCircle2, Settings
} from 'lucide-react'
import './App.css'

const API = ''
const defaultColumns = ['Posicion', 'Titulo', 'Precio', 'Ubicacion', 'OrigenBusqueda', 'ZonaBusqueda', 'Publicado', 'Descripcion', 'Link', 'Imagen']
const cookieProfiles = ['curico', 'talca']
const cookieProfileLabels = { curico: 'Curicó', talca: 'Talca' }

const emptyProfileStatus = {
  valid: false,
  message: 'No hay cookies configuradas.',
  keys: [],
  has_c_user: false,
  has_xs: false,
}

const normalizeCookieStatus = (raw) => {
  const profiles = {
    curico: { ...emptyProfileStatus },
    talca: { ...emptyProfileStatus },
  }

  if (raw?.profiles && typeof raw.profiles === 'object') {
    cookieProfiles.forEach((profile) => {
      const src = raw.profiles[profile] || {}
      profiles[profile] = {
        valid: Boolean(src.valid),
        message: src.message || (src.valid ? 'Cookies OK' : 'No hay cookies configuradas.'),
        keys: Array.isArray(src.keys) ? src.keys : [],
        has_c_user: Boolean(src.has_c_user),
        has_xs: Boolean(src.has_xs),
      }
    })
  } else {
    profiles.curico = {
      valid: Boolean(raw?.valid),
      message: raw?.message || (raw?.valid ? 'Cookies OK' : 'No hay cookies configuradas.'),
      keys: Array.isArray(raw?.keys) ? raw.keys : [],
      has_c_user: Boolean(raw?.has_c_user),
      has_xs: Boolean(raw?.has_xs),
    }
  }

  const allValid = cookieProfiles.every((profile) => profiles[profile].valid)
  const anyValid = cookieProfiles.some((profile) => profiles[profile].valid)

  return {
    valid: allValid,
    any_valid: anyValid,
    message: raw?.message || (allValid ? 'Perfiles listos.' : 'Faltan cookies en uno o más perfiles.'),
    profiles,
  }
}

function App() {
  const [form, setForm] = useState({
    query: 'notebook gamer',
    marketplace_path: 'curico',
    limit: 40,
    max_pages: 3,
    min_price: 0,
    max_price: 0,
    location_query: 'Curico, Maule, Chile',
    latitude: '-34.98749193781055',
    longitude: '-71.24675716218236',
    radius_km: 12,
    include_talca: false,
    country_code: 'CL',
    word: '',
    include_words: [],
    exclude_words: [],
    preview_limit: 40,
  })
  const [status, setStatus] = useState('')
  const [count, setCount] = useState(null)
  const [elapsed, setElapsed] = useState(null)
  const [filterBreakdown, setFilterBreakdown] = useState(null)
  const [previewRows, setPreviewRows] = useState([])
  const [previewColumns, setPreviewColumns] = useState(defaultColumns)
  const [previewElapsed, setPreviewElapsed] = useState(null)
  const [previewTotalCount, setPreviewTotalCount] = useState(null)
  const [includeDraft, setIncludeDraft] = useState('')
  const [excludeDraft, setExcludeDraft] = useState('')
  const [view, setView] = useState('main')
  const [loadingCount, setLoadingCount] = useState(false)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [loadingExport, setLoadingExport] = useState(false)
  const [countRunMs, setCountRunMs] = useState(0)
  const [previewRunMs, setPreviewRunMs] = useState(0)
  const [exportRunMs, setExportRunMs] = useState(0)
  const [columnFilters, setColumnFilters] = useState(
    Object.fromEntries(defaultColumns.map((c) => [c, ''])),
  )

  // Cookie state
  const [cookieStatus, setCookieStatus] = useState(() => normalizeCookieStatus(null))
  const [cookieInputs, setCookieInputs] = useState({ curico: '', talca: '' })
  const [savingProfile, setSavingProfile] = useState('')
  const [showCookiePanel, setShowCookiePanel] = useState(false)

  const canSubmit = useMemo(
    () => Boolean(form.query.trim()),
    [form.query],
  )

  const resolvedColumns = previewColumns.length ? previewColumns : defaultColumns

  const filteredPreviewRows = useMemo(() => {
    if (!previewRows.length) return []
    return previewRows.filter((row) =>
      resolvedColumns.every((col) => {
        const val = String(row[col] ?? '').toLowerCase()
        const f = String(columnFilters[col] ?? '').trim().toLowerCase()
        return !f || val.includes(f)
      }),
    )
  }, [previewRows, resolvedColumns, columnFilters])

  const refreshCookieStatus = async () => {
    try {
      const res = await fetch(`${API}/api/cookies/status`)
      const data = await res.json()
      setCookieStatus(normalizeCookieStatus(data))
    } catch {
      setCookieStatus(normalizeCookieStatus({ valid: false, message: 'No se pudo verificar cookies' }))
    }
  }

  // Check cookie status on mount
  useEffect(() => {
    refreshCookieStatus()
  }, [])

  const onChange = (key, value) => setForm((p) => ({ ...p, [key]: value }))

  const setCuricoBase = () => {
    setForm((p) => ({
      ...p,
      marketplace_path: 'curico',
      location_query: 'Curico, Maule, Chile',
      latitude: '-34.98749193781055',
      longitude: '-71.24675716218236',
      radius_km: 12,
    }))
  }

  const buildPayload = () => ({
    ...form,
    latitude: String(form.latitude).trim() === '' ? null : Number(form.latitude),
    longitude: String(form.longitude).trim() === '' ? null : Number(form.longitude),
  })

  const runWithTimer = async (setLoading, setMs, task) => {
    setLoading(true)
    setMs(0)
    const t0 = performance.now()
    const tick = setInterval(() => setMs(performance.now() - t0), 120)
    try { await task() }
    finally { clearInterval(tick); setMs(performance.now() - t0); setLoading(false) }
  }

  const addIncludeWord = () => {
    const v = includeDraft.trim()
    if (!v) return
    setForm((p) => p.include_words.includes(v) ? p : { ...p, include_words: [...p.include_words, v] })
    setIncludeDraft('')
  }
  const addExcludeWord = () => {
    const v = excludeDraft.trim()
    if (!v) return
    setForm((p) => p.exclude_words.includes(v) ? p : { ...p, exclude_words: [...p.exclude_words, v] })
    setExcludeDraft('')
  }
  const removeIncludeWord = (w) => setForm((p) => ({ ...p, include_words: p.include_words.filter((i) => i !== w) }))
  const removeExcludeWord = (w) => setForm((p) => ({ ...p, exclude_words: p.exclude_words.filter((i) => i !== w) }))

  const saveCookies = async (profile) => {
    const raw = String(cookieInputs[profile] || '').trim()
    if (!raw) return
    setSavingProfile(profile)
    try {
      const res = await fetch(`${API}/api/cookies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile, cookie_string: raw }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Error guardando cookies')
      setCookieInputs((prev) => ({ ...prev, [profile]: '' }))
      await refreshCookieStatus()
      setStatus(`Cookies guardadas para ${cookieProfileLabels[profile]} ✓`)
    } catch (err) {
      setStatus(err.message)
    } finally {
      setSavingProfile('')
    }
  }

  const baseUsesTalca = useMemo(() => {
    const path = String(form.marketplace_path || '').toLowerCase()
    const location = String(form.location_query || '').toLowerCase()
    return path.includes('talca') || location.includes('talca')
  }, [form.marketplace_path, form.location_query])

  const needsCuricoProfile = form.include_talca || !baseUsesTalca
  const needsTalcaProfile = form.include_talca || baseUsesTalca
  const curicoReady = Boolean(cookieStatus?.profiles?.curico?.valid)
  const talcaReady = Boolean(cookieStatus?.profiles?.talca?.valid)
  const cookiesReadyForSearch = (!needsCuricoProfile || curicoReady) && (!needsTalcaProfile || talcaReady)
  const missingProfilesText = [
    needsCuricoProfile && !curicoReady ? 'Curicó' : '',
    needsTalcaProfile && !talcaReady ? 'Talca' : '',
  ].filter(Boolean).join(', ')

  const runCount = async () => {
    if (!canSubmit) return
    setCount(null); setElapsed(null); setFilterBreakdown(null)
    await runWithTimer(setLoadingCount, setCountRunMs, async () => {
      try {
        const res = await fetch(`${API}/api/count-exact`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload()),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Error en conteo')
        setCount(data.count)
        setElapsed(data.elapsed_seconds)
        setFilterBreakdown(data.filter_breakdown ?? null)
      } catch (err) { setStatus(err.message) }
    })
  }

  const runPreview = async () => {
    if (!canSubmit) return
    await runWithTimer(setLoadingPreview, setPreviewRunMs, async () => {
      try {
        const res = await fetch(`${API}/api/preview`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload()),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Error en preview')
        setPreviewColumns(data.columns || defaultColumns)
        setPreviewRows(data.rows || [])
        setPreviewElapsed(data.elapsed_seconds ?? null)
        setPreviewTotalCount(data.total_count ?? data.count ?? null)
        setFilterBreakdown(data.filter_breakdown ?? null)
        setView('preview')
      } catch (err) { setStatus(err.message) }
    })
  }

  const runExport = async () => {
    if (!canSubmit) return
    await runWithTimer(setLoadingExport, setExportRunMs, async () => {
      try {
        const res = await fetch(`${API}/api/export`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildPayload()),
        })
        if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Error exportando') }
        const blob = await res.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `facebook_marketplace_${Date.now()}.xlsx`
        document.body.appendChild(a); a.click(); a.remove()
        window.URL.revokeObjectURL(url)
        setStatus('Excel exportado correctamente ✓')
      } catch (err) { setStatus(err.message) }
    })
  }

  // -----------------------------------------------------------------------
  // Preview view
  // -----------------------------------------------------------------------
  if (view === 'preview') {
    return (
      <main className="page">
        <section className="panel panel-wide">
          <div className="hero">
            <div>
              <div className="eyebrow">Facebook Marketplace</div>
              <h1>Preview de resultados</h1>
            </div>
            <button className="btn ghost" type="button" onClick={() => setView('main')}>
              <span className="btn-content"><ArrowLeft size={16} />Volver</span>
            </button>
          </div>

          <div className="preview-meta">
            <span>Filas: {filteredPreviewRows.length} / {previewRows.length}{previewTotalCount != null ? ` de ${previewTotalCount} totales` : ''}</span>
            <span>Tiempo: {previewElapsed != null ? `${previewElapsed}s` : '-'}</span>
          </div>

          <div className="table-wrap">
            <table className="preview-table">
              <thead>
                <tr>
                  {resolvedColumns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
                <tr className="filter-row">
                  {resolvedColumns.map((col) => (
                    <th key={`${col}-f`}>
                      <input
                        className="col-filter-input"
                        placeholder={`Filtrar`}
                        value={columnFilters[col] || ''}
                        onChange={(e) => setColumnFilters((p) => ({ ...p, [col]: e.target.value }))}
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredPreviewRows.map((row, i) => (
                  <tr key={`${row.Link}-${i}`}>
                    {resolvedColumns.map((col) => (
                      <td key={col}>
                        {col === 'Link' && row.Link ? (
                          <a href={row.Link} target="_blank" rel="noreferrer">abrir</a>
                        ) : col === 'Imagen' && row.Imagen ? (
                          <img src={row.Imagen} alt="" style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 6 }} />
                        ) : (
                          row[col] ?? '-'
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
                {!filteredPreviewRows.length && (
                  <tr><td colSpan={resolvedColumns.length}>Sin datos con los filtros actuales.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    )
  }

  // -----------------------------------------------------------------------
  // Main view
  // -----------------------------------------------------------------------
  return (
    <main className="page">
      <section className="panel">
        <div className="hero">
          <div>
            <div className="eyebrow">Pro Descuento</div>
            <h1>Facebook Marketplace</h1>
          </div>
          <span className="badge"><Store size={13} />HTTP Scraper</span>
        </div>
        <p className="hint">
          Base Curicó por defecto. Si activas Talca, el scraper hace una búsqueda real adicional en Talca y luego mezcla ambos resultados.
        </p>

        {/* Cookie status banner */}
        <div className={`cookie-banner ${cookieStatus?.any_valid ? 'valid' : 'invalid'}`}>
          <div className="cookie-banner-content">
            {cookieStatus?.any_valid
              ? <><CheckCircle2 size={16} /> Curicó: {curicoReady ? 'OK' : 'Falta'} | Talca: {talcaReady ? 'OK' : 'Falta'}</>
              : <><AlertTriangle size={16} /> {cookieStatus?.message || 'Sin cookies configuradas'}</>
            }
          </div>
          <button className="btn ghost sm" onClick={() => setShowCookiePanel(!showCookiePanel)}>
            <span className="btn-content"><Settings size={14} />{showCookiePanel ? 'Cerrar' : 'Configurar'}</span>
          </button>
        </div>

        {/* Cookie config panel */}
        {showCookiePanel && (
          <div className="section cookie-section">
            <div className="section-title"><Cookie size={14} /> Configurar Cookies de Facebook</div>
            <p className="hint">
              <strong>Método 1:</strong> En Facebook → F12 → Consola → escribe <code>allow pasting</code> + Enter → luego <code>document.cookie</code> + Enter → copia el resultado.<br/>
              <strong>Método 2:</strong> En Facebook → F12 → pestaña <strong>Application</strong> → Cookies → facebook.com → copia al menos <code>c_user</code> y <code>xs</code> en formato: <code>c_user=123; xs=abc</code>
            </p>
            <div className="cookie-profiles-grid">
              {cookieProfiles.map((profile) => {
                const profileState = cookieStatus?.profiles?.[profile] || emptyProfileStatus
                const isSaving = savingProfile === profile
                const value = cookieInputs[profile] || ''
                return (
                  <div className="cookie-profile-card" key={profile}>
                    <div className="cookie-profile-header">
                      <strong>Perfil {cookieProfileLabels[profile]}</strong>
                      <span className={`cookie-profile-state ${profileState.valid ? 'ok' : 'warn'}`}>
                        {profileState.valid ? 'OK' : 'Pendiente'}
                      </span>
                    </div>
                    <textarea
                      className="cookie-input"
                      rows={4}
                      placeholder={`Pega aquí cookies para ${cookieProfileLabels[profile]}: c_user=123; xs=abc; ...`}
                      value={value}
                      onChange={(e) => setCookieInputs((prev) => ({ ...prev, [profile]: e.target.value }))}
                    />
                    <button
                      className="btn warn"
                      disabled={!value.trim() || Boolean(savingProfile)}
                      onClick={() => saveCookies(profile)}
                    >
                      <span className="btn-content">
                        {isSaving ? <><span className="loader" /> Guardando...</> : `Guardar ${cookieProfileLabels[profile]}`}
                      </span>
                    </button>
                    {!profileState.valid && profileState.message && (
                      <div className="cookie-profile-note">{profileState.message}</div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Search config */}
        <div className="section">
          <div className="section-title"><Search size={14} /> Búsqueda</div>
          <div className="grid">
            <label>
              Búsqueda
              <input value={form.query} onChange={(e) => onChange('query', e.target.value)} />
            </label>
            <label>
              Marketplace path
              <input placeholder="curico" value={form.marketplace_path} onChange={(e) => onChange('marketplace_path', e.target.value)} />
            </label>
            <label>
              Límite de items
              <input type="number" min="1" value={form.limit} onChange={(e) => onChange('limit', Number(e.target.value || 1))} />
            </label>
            <label>
              Precio mínimo
              <input type="number" min="0" value={form.min_price} onChange={(e) => onChange('min_price', Number(e.target.value || 0))} />
            </label>
            <label>
              Precio máximo
              <input type="number" min="0" value={form.max_price} onChange={(e) => onChange('max_price', Number(e.target.value || 0))} />
            </label>
            <label>
              Ubicación base
              <input placeholder="Curico, Maule, Chile" value={form.location_query} onChange={(e) => onChange('location_query', e.target.value)} />
            </label>
            <label>
              Radio km
              <input type="number" min="0" value={form.radius_km} onChange={(e) => onChange('radius_km', Number(e.target.value || 0))} />
            </label>
            <label>
              País
              <input placeholder="CL" value={form.country_code} onChange={(e) => onChange('country_code', e.target.value.toUpperCase())} />
            </label>
            <label>
              Latitud
              <input placeholder="-34.98279" value={form.latitude} onChange={(e) => onChange('latitude', e.target.value)} />
            </label>
            <label>
              Longitud
              <input placeholder="-71.23943" value={form.longitude} onChange={(e) => onChange('longitude', e.target.value)} />
            </label>
            <label>
              Límite preview
              <input type="number" min="1" max="500" value={form.preview_limit} onChange={(e) => onChange('preview_limit', Number(e.target.value || 1))} />
            </label>
            <label>
              Páginas extra
              <input type="number" min="0" max="5" value={form.max_pages} onChange={(e) => onChange('max_pages', Number(e.target.value || 0))} />
            </label>
            <div className="full location-tools">
              <button type="button" className="btn ghost sm" onClick={setCuricoBase}>
                Usar Curicó base
              </button>
              <label className="switch-card">
                <span>Agregar Talca como opción cercana</span>
                <input
                  type="checkbox"
                  checked={form.include_talca}
                  onChange={(e) => onChange('include_talca', e.target.checked)}
                />
                <span className="switch"><span className="switch-knob" /></span>
              </label>
            </div>
            <label className="full">
              Palabra exacta obligatoria
              <input value={form.word} onChange={(e) => onChange('word', e.target.value)} />
            </label>
            <label className="full">
              Palabras a incluir
              <div className="word-editor">
                <input placeholder="ej: gamer" value={includeDraft} onChange={(e) => setIncludeDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addIncludeWord() } }} />
                <button type="button" onClick={addIncludeWord}>Agregar</button>
              </div>
              <div className="chips">
                {form.include_words.map((w) => (
                  <button key={w} type="button" className="chip include" onClick={() => removeIncludeWord(w)}>{w} ×</button>
                ))}
              </div>
            </label>
            <label className="full">
              Palabras a excluir
              <div className="word-editor">
                <input placeholder="ej: repuesto" value={excludeDraft} onChange={(e) => setExcludeDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addExcludeWord() } }} />
                <button type="button" onClick={addExcludeWord}>Agregar</button>
              </div>
              <div className="chips">
                {form.exclude_words.map((w) => (
                  <button key={w} type="button" className="chip exclude" onClick={() => removeExcludeWord(w)}>{w} ×</button>
                ))}
              </div>
            </label>
          </div>
        </div>

        {/* Actions */}
        <div className="actions">
          <button className="btn warn" disabled={!canSubmit || loadingCount || !cookiesReadyForSearch} onClick={runCount}>
            {loadingCount ? (
              <span className="btn-content"><span className="loader" /> Calculando... {(countRunMs / 1000).toFixed(1)}s</span>
            ) : (
              <span className="btn-content"><Hash size={16} />Calcular cantidad</span>
            )}
          </button>
          <button className="btn info" disabled={!canSubmit || loadingPreview || !cookiesReadyForSearch} onClick={runPreview}>
            {loadingPreview ? (
              <span className="btn-content"><span className="loader" /> Cargando... {(previewRunMs / 1000).toFixed(1)}s</span>
            ) : (
              <span className="btn-content"><SlidersHorizontal size={16} />Previsualizar</span>
            )}
          </button>
          <button className="btn outline" disabled={!canSubmit || loadingExport || !cookiesReadyForSearch} onClick={runExport}>
            {loadingExport ? (
              <span className="btn-content"><span className="loader" /> Exportando... {(exportRunMs / 1000).toFixed(1)}s</span>
            ) : (
              <span className="btn-content"><FileSpreadsheet size={16} />Exportar Excel</span>
            )}
          </button>
        </div>
        {!cookiesReadyForSearch && (
          <div className="status">
            Faltan perfiles de cookies requeridos para esta búsqueda: {missingProfilesText}.
          </div>
        )}

        {/* Results */}
        <div className="results">
          <div className="section-title"><Clock3 size={14} /> Resumen</div>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Resultados</div>
              <div className="kpi-value">{count ?? '-'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Capturados</div>
              <div className="kpi-value">{filterBreakdown?.captured_raw ?? '-'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Tras filtros</div>
              <div className="kpi-value">{filterBreakdown?.after_text_price_filters ?? '-'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Tras ubicación</div>
              <div className="kpi-value">{filterBreakdown?.after_location_filter ?? '-'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Tiempo</div>
              <div className="kpi-value">{elapsed != null ? `${elapsed}s` : '-'}</div>
            </div>
          </div>
          {status && <div className="status">{status}</div>}
          {(loadingCount || loadingPreview || loadingExport) && (
            <div className="running-hint">
              Proceso activo: {loadingCount ? 'conteo' : loadingPreview ? 'preview' : 'exportación'}
            </div>
          )}
        </div>
      </section>
    </main>
  )
}

export default App
