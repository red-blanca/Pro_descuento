import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { Cookie, ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react'
import './App.css'
import GlobalSearchView from './global-search/GlobalSearchView.jsx'

function App() {
  const globalAbortRef = useRef(false)
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
    country: 'cl',
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

  const fetchCookieStatus = async () => {
    try {
      const res = await fetch('/api/cookies/status')
      if (res.ok) setCookieStatus(await res.json())
    } catch {
      // optional
    }
  }

  const fetchFacebookCookieStatus = async () => {
    try {
      const res = await fetch('/api/facebook-cookies/status')
      if (res.ok) setFacebookCookieStatus(await res.json())
    } catch {
      // optional
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
        if (err.name !== 'AbortError') setGlobalCategories((prev) => prev)
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
          // ignore
        }
        throw new Error(errorMsg)
      }
      const data = await res.json()
      setCookieMsg(`${data.cookie_count} cookies guardadas correctamente`)
      setCookieRawText('')
      await fetchCookieStatus()
    } catch (err) {
      setCookieMsg(err.message)
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
          // ignore
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

  const canGlobalSubmit = useMemo(
    () => Boolean(globalForm.query.trim() || (globalForm.sources.length === 1 && globalForm.sources[0] === 'descuentosrata')),
    [globalForm.query, globalForm.sources],
  )

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

  const safeJson = async (res) => {
    const text = await res.text()
    try {
      return JSON.parse(text)
    } catch {
      if (text.trimStart().startsWith('<')) {
        throw new Error(
          res.status === 502
            ? 'Timeout del servidor (502). Intenta con menos fuentes o modo rapido.'
            : `El servidor respondio con HTML en vez de JSON (status ${res.status})`,
        )
      }
      throw new Error(`Respuesta invalida del servidor (status ${res.status})`)
    }
  }

  const pollGlobalJob = async (jobId) => {
    while (true) {
      await new Promise((r) => setTimeout(r, 2000))
      if (globalAbortRef.current) throw new Error('Escaneo abortado por el usuario')
      const res = await fetch(`/api/global-search/${jobId}`)
      const data = await safeJson(res)
      if (!res.ok) throw new Error(data.detail || 'Error consultando estado del job')
      if (data.status === 'error') throw new Error(data.error || 'Error en busqueda conjunta')
      if (data.status === 'done') return data
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
    globalAbortRef.current = false
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
    globalAbortRef.current = false
    setGlobalStatus('')

    let data = globalResult
    if (!data || !data.items || !data.items.length) {
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

  const abortGlobalSearch = () => {
    globalAbortRef.current = true
    setGlobalLoading(false)
    setGlobalStatus('Escaneo abortado por el usuario')
  }

  return (
    <>
      <GlobalSearchView
        globalForm={globalForm}
        onGlobalChange={onGlobalChange}
        toggleGlobalSource={toggleGlobalSource}
        globalCategories={globalCategories}
        globalCategoriesLoading={globalCategoriesLoading}
        globalResult={globalResult}
        globalStatus={globalStatus}
        globalLoading={globalLoading}
        globalRunMs={globalRunMs}
        canGlobalSubmit={canGlobalSubmit}
        onRun={runGlobalSearch}
        onAbort={abortGlobalSearch}
        onDownload={downloadGlobalJson}
        cookieHealth={cookieHealth}
        facebookCookieHealth={facebookCookieHealth}
        onOpenCookieModal={() => {
          setCookieMsg('')
          setFacebookCookieMsg('')
          setCookieModalOpen(true)
        }}
      />

      {cookieModalOpen && (
        <motion.div className="modal-overlay" onClick={() => setCookieModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <motion.div className="modal-header">
              <h2><Cookie size={20} /> Gestionar Cookies</h2>
              <button type="button" className="modal-close" onClick={() => setCookieModalOpen(false)}>×</button>
            </motion.div>

            <motion.div className="cookie-info">
              {cookieStatus && cookieStatus.exists ? (
                <motion.div className={`cookie-badge cookie-badge-${cookieHealth.color}`}>
                  {cookieHealth.icon === 'ok' && <ShieldCheck size={16} />}
                  {cookieHealth.icon === 'warn' && <ShieldAlert size={16} />}
                  {cookieHealth.icon === 'x' && <ShieldX size={16} />}
                  <motion.div>
                    <motion.div className="cookie-badge-title">{cookieStatus.cookie_count} cookies guardadas</motion.div>
                    <motion.div className="cookie-badge-sub">
                      Ultima actualizacion: {cookieStatus.age_minutes != null ? `hace ${Math.round(cookieStatus.age_minutes)} min` : 'desconocida'}
                    </motion.div>
                  </motion.div>
                </motion.div>
              ) : (
                <motion.div className="cookie-badge cookie-badge-red">
                  <ShieldX size={16} />
                  <motion.div>
                    <motion.div className="cookie-badge-title">No hay cookies guardadas</motion.div>
                    <motion.div className="cookie-badge-sub">Pega las cookies de MercadoLibre abajo</motion.div>
                  </motion.div>
                </motion.div>
              )}
            </motion.div>

            <motion.div className="cookie-instructions">
              <p><strong>Como obtener cookies:</strong></p>
              <ol>
                <li>Abre <a href="https://www.mercadolibre.cl" target="_blank" rel="noreferrer">mercadolibre.cl</a> e inicia sesion</li>
                <li>Presiona F12 → Application → Cookies</li>
                <li>Selecciona todas las filas (Ctrl+A) y copia (Ctrl+C)</li>
                <li>Pega aqui abajo</li>
              </ol>
            </motion.div>

            <textarea
              className="cookie-textarea"
              placeholder="Pega las cookies de MercadoLibre aqui..."
              value={cookieRawText}
              onChange={(e) => setCookieRawText(e.target.value)}
              rows={10}
            />

            {cookieMsg && <motion.div className="cookie-feedback">{cookieMsg}</motion.div>}

            <motion.div className="cookie-info">
              <motion.div className={`cookie-badge cookie-badge-${facebookCookieHealth.color}`}>
                {facebookCookieHealth.icon === 'ok' && <ShieldCheck size={16} />}
                {facebookCookieHealth.icon === 'warn' && <ShieldAlert size={16} />}
                {facebookCookieHealth.icon === 'x' && <ShieldX size={16} />}
                <motion.div>
                  <motion.div className="cookie-badge-title">Facebook Marketplace</motion.div>
                  <motion.div className="cookie-badge-sub">
                    Curico: {facebookCookieStatus?.profiles?.curico?.valid ? 'OK' : 'pendiente'} | Talca:{' '}
                    {facebookCookieStatus?.profiles?.talca?.valid ? 'OK' : 'pendiente'}
                  </motion.div>
                </motion.div>
              </motion.div>
            </motion.div>

            <label>
              Perfil Facebook
              <select value={facebookCookieProfile} onChange={(e) => setFacebookCookieProfile(e.target.value)}>
                <option value="curico">Curico</option>
                <option value="talca">Talca</option>
              </select>
            </label>

            <textarea
              className="cookie-textarea"
              placeholder="Pega cookies de Facebook aqui..."
              value={facebookCookieRawText}
              onChange={(e) => setFacebookCookieRawText(e.target.value)}
              rows={8}
            />

            {facebookCookieMsg && <motion.div className="cookie-feedback">{facebookCookieMsg}</motion.div>}

            <motion.div className="modal-actions">
              <button type="button" className="btn warn" disabled={!facebookCookieRawText.trim() || facebookCookieSaving} onClick={saveFacebookCookies}>
                {facebookCookieSaving ? 'Guardando...' : 'Guardar Facebook'}
              </button>
              <button type="button" className="btn warn" disabled={!cookieRawText.trim() || cookieSaving} onClick={saveCookies}>
                {cookieSaving ? 'Guardando...' : 'Guardar MercadoLibre'}
              </button>
              <button type="button" className="btn ghost" onClick={() => setCookieModalOpen(false)}>
                Cerrar
              </button>
            </motion.div>
          </div>
        </motion.div>
      )}
    </>
  )
}

export default App
