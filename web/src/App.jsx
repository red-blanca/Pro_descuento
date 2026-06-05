import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion as Motion } from 'motion/react'
import { Cookie, ShieldCheck, ShieldAlert, ShieldX, X } from 'lucide-react'
import './App.css'
import GlobalSearchView from './global-search/GlobalSearchView.jsx'
import { soundService } from './global-search/soundService.js'

function App() {
  const globalAbortRef = useRef(false)
  const [globalForm, setGlobalForm] = useState({
    query: '',
    scan_scope: 'complete',
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
      'pcfactory',
      'aliexpress',
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
    knasta_category: '',
    knasta_retails_text: '',
    knasta_knastaday: 0,
    solotodo_category_id: 0,
    solotodo_country_id: 1,
    solotodo_ordering: 'offer_price_usd',
    travel_category_id: '',
    travel_ordering: 'relevance',
    tuganga_mode: 'search',
    tuganga_stores_text: '',
    tuganga_category: '',
    tuganga_only_available: false,
    tuganga_sort: '',
    pcfactory_word: '',
    aliexpress_word: '',
    aliexpress_price_includes_chile_vat: true,
    descuentosrata_all: true,
    descuentosrata_limit: 10000,
    strict_mode: false,
    smart_filter: true,
    auto_categories: true,
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
  const [categorySuggestion, setCategorySuggestion] = useState(null)
  const lastAppliedQueryRef = useRef('')
  const [cookieModalOpen, setCookieModalOpen] = useState(false)
  const [cookieTab, setCookieTab] = useState('mercadolibre')
  const [cookieRawText, setCookieRawText] = useState('')
  const [cookieStatus, setCookieStatus] = useState(null)
  const [cookieSaving, setCookieSaving] = useState(false)
  const [cookieMsg, setCookieMsg] = useState('')
  const [facebookCookieStatus, setFacebookCookieStatus] = useState(null)
  const [facebookCookieProfile, setFacebookCookieProfile] = useState('curico')
  const [facebookCookieRawText, setFacebookCookieRawText] = useState('')
  const [facebookCookieSaving, setFacebookCookieSaving] = useState(false)
  const [facebookCookieMsg, setFacebookCookieMsg] = useState('')
  const [aliexpressCookieStatus, setAliexpressCookieStatus] = useState(null)
  const [aliexpressCookieRawText, setAliexpressCookieRawText] = useState('')
  const [aliexpressCookieSaving, setAliexpressCookieSaving] = useState(false)
  const [aliexpressCookieMsg, setAliexpressCookieMsg] = useState('')

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

  const fetchAliexpressCookieStatus = async () => {
    try {
      const res = await fetch('/api/aliexpress-cookies/status')
      if (res.ok) setAliexpressCookieStatus(await res.json())
    } catch {
      // optional
    }
  }

  useEffect(() => {
    fetchCookieStatus()
    fetchFacebookCookieStatus()
    fetchAliexpressCookieStatus()
  }, [])

  const applySuggestedCategories = useCallback((suggested, query) => {
    if (!suggested || !query.trim()) return
    setGlobalForm((prev) => {
      const next = { ...prev }
      if (suggested.pulga_category !== undefined) next.pulga_category = suggested.pulga_category || ''
      if (suggested.knasta_category !== undefined) next.knasta_category = suggested.knasta_category || ''
      if (suggested.solotodo_category_id !== undefined) next.solotodo_category_id = Number(suggested.solotodo_category_id || 0)
      if (suggested.travel_category_id !== undefined) next.travel_category_id = suggested.travel_category_id || ''
      if (suggested.tuganga_category !== undefined) next.tuganga_category = suggested.tuganga_category || ''
      if (suggested.tuganga_mode && query.trim()) next.tuganga_mode = suggested.tuganga_mode
      return next
    })
    lastAppliedQueryRef.current = query.trim()
  }, [])

  const reapplyCategorySuggestions = useCallback(() => {
    if (!categorySuggestion || !globalForm.query.trim()) return
    lastAppliedQueryRef.current = ''
    applySuggestedCategories(categorySuggestion, globalForm.query)
  }, [applySuggestedCategories, categorySuggestion, globalForm.query])

  const resetAllCategories = useCallback(() => {
    setGlobalForm((prev) => ({
      ...prev,
      pulga_category: '',
      knasta_category: '',
      solotodo_category_id: 0,
      travel_category_id: '',
      tuganga_category: '',
      tuganga_mode: prev.query.trim() ? 'search' : prev.tuganga_mode,
    }))
    setCategorySuggestion(null)
    lastAppliedQueryRef.current = ''
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      const query = globalForm.query.trim()
      setGlobalCategoriesLoading(true)
      try {
        const params = new URLSearchParams({
          query,
          knasta_knastaday: String(globalForm.knasta_knastaday || 0),
          knasta_retails: globalForm.knasta_retails_text,
          tuganga_mode: query ? 'search' : globalForm.tuganga_mode,
        })
        const res = await fetch(`/api/global-categories?${params.toString()}`, { signal: controller.signal })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'No se pudieron cargar categorias')
        if (controller.signal.aborted) return
        setGlobalCategories(data.categories || {})
        const suggested = data.suggested || {}
        setCategorySuggestion(query ? suggested : null)
        if (globalForm.auto_categories && query && lastAppliedQueryRef.current !== query) {
          applySuggestedCategories(suggested, query)
        }
        if (!query) {
          lastAppliedQueryRef.current = ''
          setCategorySuggestion(null)
        }
      } catch (err) {
        if (err.name !== 'AbortError') setGlobalCategories((prev) => prev)
      } finally {
        if (!controller.signal.aborted) setGlobalCategoriesLoading(false)
      }
    }, 500)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [
    globalForm.query,
    globalForm.knasta_knastaday,
    globalForm.knasta_retails_text,
    globalForm.tuganga_mode,
    globalForm.auto_categories,
    applySuggestedCategories,
  ])

  useEffect(() => {
    if (!globalForm.auto_categories || !globalForm.query.trim() || !categorySuggestion) return
    if (lastAppliedQueryRef.current === globalForm.query.trim()) return
    applySuggestedCategories(categorySuggestion, globalForm.query)
  }, [globalForm.auto_categories, categorySuggestion, globalForm.query, applySuggestedCategories])

  const onGlobalChange = (key, value) => {
    const categoryKeys = new Set(['pulga_category', 'knasta_category', 'solotodo_category_id', 'travel_category_id', 'tuganga_category'])
    setGlobalForm((prev) => {
      const next = { ...prev, [key]: value }
      if (categoryKeys.has(key) && prev.auto_categories) {
        next.auto_categories = false
      }
      return next
    })
  }

  const saveCookies = async () => {
    if (!cookieRawText.trim()) return
    soundService.playAction()
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
    soundService.playAction()
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

  const saveAliexpressCookies = async () => {
    if (!aliexpressCookieRawText.trim()) return
    soundService.playAction()
    setAliexpressCookieSaving(true)
    setAliexpressCookieMsg('')
    try {
      const res = await fetch('/api/aliexpress-cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: aliexpressCookieRawText }),
      })
      if (!res.ok) {
        let errorMsg = 'Error guardando cookies de AliExpress'
        try {
          const data = await res.json()
          errorMsg = data.detail || errorMsg
        } catch {
          // ignore
        }
        throw new Error(errorMsg)
      }
      const data = await res.json()
      setAliexpressCookieMsg(`${data.cookie_count} cookies guardadas para AliExpress`)
      setAliexpressCookieRawText('')
      await fetchAliexpressCookieStatus()
    } catch (err) {
      setAliexpressCookieMsg(err.message)
    } finally {
      setAliexpressCookieSaving(false)
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

  const aliexpressCookieHealth = useMemo(() => {
    if (!aliexpressCookieStatus || !aliexpressCookieStatus.exists || aliexpressCookieStatus.cookie_count === 0) {
      return { color: 'red', label: 'AliExpress sin cookies', icon: 'x' }
    }
    const age = aliexpressCookieStatus.age_minutes ?? 9999
    if (!aliexpressCookieStatus.valid || age > 180) {
      return { color: 'yellow', label: `AliExpress ${Math.round(age)}min - revisar`, icon: 'warn' }
    }
    return { color: 'green', label: `AliExpress ${Math.round(age)}min - listo`, icon: 'ok' }
  }, [aliexpressCookieStatus])

  const canGlobalSubmit = useMemo(() => {
    const hasQuery = Boolean(globalForm.query.trim())
    const onlyRata = globalForm.sources.length === 1 && globalForm.sources[0] === 'descuentosrata'
    const hasCategory = Boolean(
      globalForm.pulga_category ||
      globalForm.knasta_category ||
      globalForm.solotodo_category_id ||
      globalForm.travel_category_id ||
      globalForm.tuganga_category
    )
    return hasQuery || onlyRata || hasCategory
  }, [
    globalForm.query,
    globalForm.sources,
    globalForm.pulga_category,
    globalForm.knasta_category,
    globalForm.solotodo_category_id,
    globalForm.travel_category_id,
    globalForm.tuganga_category,
  ])

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
      if (!text.trim() && [502, 503, 504].includes(res.status)) {
        throw new Error(
          'Render reinicio el servidor durante la busqueda por limite de recursos. Intenta nuevamente con menos fuentes o menor limite por fuente.',
        )
      }
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
    let attempts = 0
    while (true) {
      // Progressive polling: check quickly at first, then slow down.
      let delay = 2000
      if (attempts === 0) {
        delay = 200
      } else if (attempts < 6) {
        delay = 500
      } else if (attempts < 13) {
        delay = 1000
      } else {
        delay = 2000
      }

      await new Promise((r) => setTimeout(r, delay))
      attempts++

      if (globalAbortRef.current) throw new Error('Escaneo abortado por el usuario')
      const res = await fetch(`/api/global-search/${jobId}`)
      const data = await safeJson(res)
      if (!res.ok) throw new Error(data.detail || 'Error consultando estado del job')
      if (data.status === 'error') throw new Error(data.error || 'Error en busqueda conjunta')

      if (data.status === 'running') {
        setGlobalResult(data)
        setGlobalStatus(`Buscando... ${data.elapsed_seconds}s`)
      }

      if (data.status === 'done') return data
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
      soundService.stopRadarLoop()
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
        soundService.stopRadarLoop()
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
    soundService.stopRadarLoop()
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
        categorySuggestion={categorySuggestion}
        onResetAllCategories={resetAllCategories}
        onReapplyCategorySuggestions={reapplyCategorySuggestions}
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
          setAliexpressCookieMsg('')
          setCookieModalOpen(true)
          fetchCookieStatus()
          fetchFacebookCookieStatus()
          fetchAliexpressCookieStatus()
        }}
      />

      {cookieModalOpen && (
        <Motion.div className="gs-matrix-root fixed inset-0 z-[300] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm font-mono text-matrix-green" onClick={() => { soundService.playCancel(); setCookieModalOpen(false) }}>
          <div className="w-full max-w-3xl border-4 border-matrix-green bg-black shadow-[0_0_50px_rgba(51,255,102,0.2)] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <Motion.div className="bg-matrix-green text-black px-4 py-2 flex items-center justify-between font-black uppercase tracking-widest">
              <h2 className="flex items-center gap-3 text-sm font-black uppercase"><Cookie size={18} strokeWidth={3} /> GESTION_COOKIES_PROTOCOL</h2>
              <button type="button" className="hover:bg-black hover:text-matrix-green p-1 transition-all" onClick={() => { soundService.playCancel(); setCookieModalOpen(false) }}><X size={20} strokeWidth={3} /></button>
            </Motion.div>

            <div className="flex border-b-2 border-matrix-green">
              {[
                ['mercadolibre', 'MercadoLibre'],
                ['facebook', 'Facebook'],
                ['aliexpress', 'AliExpress'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`flex-1 px-3 py-2 text-[10px] font-black uppercase tracking-widest border-r border-matrix-green/40 transition-all ${cookieTab === id ? 'bg-matrix-green text-black' : 'bg-black text-matrix-green/60 hover:text-matrix-green hover:bg-matrix-green/10'}`}
                  onClick={() => { soundService.playClick(); setCookieTab(id) }}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="p-8 max-h-[76vh] overflow-y-auto space-y-6">
              {cookieTab === 'mercadolibre' && (
                <>
                  <div className={`flex items-start gap-3 p-3 border-2 bg-black text-[10px] uppercase ${cookieHealth.color === 'green' ? 'border-matrix-green text-matrix-green' : cookieHealth.color === 'yellow' ? 'border-yellow-300 text-yellow-300' : 'border-[#ff3333] text-[#ff3333]'}`}>
                    {cookieHealth.icon === 'ok' && <ShieldCheck size={16} />}
                    {cookieHealth.icon === 'warn' && <ShieldAlert size={16} />}
                    {cookieHealth.icon === 'x' && <ShieldX size={16} />}
                    <div>
                      <div className="font-black tracking-widest">{cookieStatus?.cookie_count || 0} cookies MercadoLibre</div>
                      <div className="opacity-70">Actualizacion: {cookieStatus?.age_minutes != null ? `hace ${Math.round(cookieStatus.age_minutes)} min` : 'desconocida'}</div>
                    </div>
                  </div>
                  <div className="border-2 border-matrix-green/30 bg-matrix-green/5 p-4 text-[10px] uppercase leading-relaxed text-matrix-green/60">
                    <p className="mb-2 font-black text-matrix-green">Como obtener cookies:</p>
                    <ol className="list-decimal pl-5 space-y-1">
                      <li>Abre mercadolibre.cl e inicia sesion</li>
                      <li>Presiona F12 - Application - Cookies</li>
                      <li>Selecciona las filas y copia</li>
                      <li>Pega aqui abajo</li>
                    </ol>
                  </div>
                  <textarea className="block w-full min-h-[170px] bg-black border-2 border-matrix-green p-3 text-xs font-black text-matrix-green outline-none resize-y focus:bg-matrix-green/10" placeholder="Pega las cookies de MercadoLibre aqui..." value={cookieRawText} onChange={(e) => setCookieRawText(e.target.value)} rows={10} />
                  {cookieMsg && <div className="border border-matrix-green/30 bg-matrix-green/5 p-2 text-[10px] font-black uppercase text-matrix-green">{cookieMsg}</div>}
                  <div className="flex justify-end">
                    <button type="button" className="px-8 py-2 bg-matrix-green text-black font-black uppercase text-xs hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_15px_rgba(51,255,102,0.3)]" disabled={!cookieRawText.trim() || cookieSaving} onClick={saveCookies}>
                      {cookieSaving ? 'Guardando...' : 'Guardar MercadoLibre'}
                    </button>
                  </div>
                </>
              )}

              {cookieTab === 'facebook' && (
                <>
                  <div className={`flex items-start gap-3 p-3 border-2 bg-black text-[10px] uppercase ${facebookCookieHealth.color === 'green' ? 'border-matrix-green text-matrix-green' : facebookCookieHealth.color === 'yellow' ? 'border-yellow-300 text-yellow-300' : 'border-[#ff3333] text-[#ff3333]'}`}>
                    {facebookCookieHealth.icon === 'ok' && <ShieldCheck size={16} />}
                    {facebookCookieHealth.icon === 'warn' && <ShieldAlert size={16} />}
                    {facebookCookieHealth.icon === 'x' && <ShieldX size={16} />}
                    <div>
                      <div className="font-black tracking-widest">Facebook Marketplace</div>
                      <div className="opacity-70">Curico: {facebookCookieStatus?.profiles?.curico?.valid ? 'OK' : 'pendiente'} | Talca: {facebookCookieStatus?.profiles?.talca?.valid ? 'OK' : 'pendiente'}</div>
                    </div>
                  </div>
                  <label className="block space-y-1">
                    <span className="block text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Perfil Facebook</span>
                    <select className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none uppercase" value={facebookCookieProfile} onChange={(e) => setFacebookCookieProfile(e.target.value)}>
                      <option value="curico">Curico</option>
                      <option value="talca">Talca</option>
                    </select>
                  </label>
                  <textarea className="block w-full min-h-[170px] bg-black border-2 border-matrix-green p-3 text-xs font-black text-matrix-green outline-none resize-y focus:bg-matrix-green/10" placeholder="Pega cookies de Facebook aqui..." value={facebookCookieRawText} onChange={(e) => setFacebookCookieRawText(e.target.value)} rows={10} />
                  {facebookCookieMsg && <div className="border border-matrix-green/30 bg-matrix-green/5 p-2 text-[10px] font-black uppercase text-matrix-green">{facebookCookieMsg}</div>}
                  <div className="flex justify-end">
                    <button type="button" className="px-8 py-2 bg-matrix-green text-black font-black uppercase text-xs hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_15px_rgba(51,255,102,0.3)]" disabled={!facebookCookieRawText.trim() || facebookCookieSaving} onClick={saveFacebookCookies}>
                      {facebookCookieSaving ? 'Guardando...' : 'Guardar Facebook'}
                    </button>
                  </div>
                </>
              )}

              {cookieTab === 'aliexpress' && (
                <>
                  <div className={`flex items-start gap-3 p-3 border-2 bg-black text-[10px] uppercase ${aliexpressCookieHealth.color === 'green' ? 'border-matrix-green text-matrix-green' : aliexpressCookieHealth.color === 'yellow' ? 'border-yellow-300 text-yellow-300' : 'border-[#ff3333] text-[#ff3333]'}`}>
                    {aliexpressCookieHealth.icon === 'ok' && <ShieldCheck size={16} />}
                    {aliexpressCookieHealth.icon === 'warn' && <ShieldAlert size={16} />}
                    {aliexpressCookieHealth.icon === 'x' && <ShieldX size={16} />}
                    <div>
                      <div className="font-black tracking-widest">{aliexpressCookieStatus?.cookie_count || 0} cookies AliExpress</div>
                      <div className="opacity-70">Criticas: {(aliexpressCookieStatus?.essential_found || []).join(', ') || 'ninguna'}</div>
                    </div>
                  </div>
                  <div className="border-2 border-matrix-green/30 bg-matrix-green/5 p-4 text-[10px] uppercase leading-relaxed text-matrix-green/60">
                    <p className="mb-2 font-black text-matrix-green">Como obtener cookies AliExpress:</p>
                    <ol className="list-decimal pl-5 space-y-1">
                      <li>Abre es.aliexpress.com y realiza una busqueda real</li>
                      <li>Si aparece verificacion, resuelvela en el navegador</li>
                      <li>Copia las cookies desde Application - Cookies</li>
                      <li>Pega aqui el formato tabla de DevTools</li>
                    </ol>
                  </div>
                  <textarea className="block w-full min-h-[170px] bg-black border-2 border-matrix-green p-3 text-xs font-black text-matrix-green outline-none resize-y focus:bg-matrix-green/10" placeholder="Pega cookies de AliExpress aqui..." value={aliexpressCookieRawText} onChange={(e) => setAliexpressCookieRawText(e.target.value)} rows={10} />
                  {aliexpressCookieMsg && <div className="border border-matrix-green/30 bg-matrix-green/5 p-2 text-[10px] font-black uppercase text-matrix-green">{aliexpressCookieMsg}</div>}
                  <div className="flex justify-end">
                    <button type="button" className="px-8 py-2 bg-matrix-green text-black font-black uppercase text-xs hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-[0_0_15px_rgba(51,255,102,0.3)]" disabled={!aliexpressCookieRawText.trim() || aliexpressCookieSaving} onClick={saveAliexpressCookies}>
                      {aliexpressCookieSaving ? 'Guardando...' : 'Guardar AliExpress'}
                    </button>
                  </div>
                </>
              )}

              <div className="flex justify-end pt-4 border-t border-matrix-green/20">
              <button type="button" className="px-6 py-2 border-2 border-matrix-green/30 text-matrix-green/50 font-black uppercase text-xs hover:border-matrix-green hover:text-matrix-green transition-all" onClick={() => { soundService.playCancel(); setCookieModalOpen(false) }}>
                Cerrar
              </button>
              </div>
            </div>
          </div>
        </Motion.div>
      )}
    </>
  )
}

export default App

