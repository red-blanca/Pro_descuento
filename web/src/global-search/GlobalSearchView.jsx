import './matrix-theme.css'
import { AnimatePresence, motion as Motion } from 'motion/react'
import { ChevronLeft, Database, Download } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import GlobalSearchHUD from './GlobalSearchHUD'
import GlobalSearchMatrix from './GlobalSearchMatrix'
import GlobalSearchNavbar from './GlobalSearchNavbar'
import GlobalSearchResultsModal from './GlobalSearchResultsModal'
import { GLOBAL_NODES } from './globalSearchNodes'
import { soundService } from './soundService'

const HISTORY_KEY = 'gs_session_history'

export default function GlobalSearchView({
  globalForm,
  onGlobalChange,
  toggleGlobalSource,
  globalCategories,
  globalCategoriesLoading,
  categorySuggestion,
  onResetAllCategories,
  onReapplyCategorySuggestions,
  globalResult,
  globalStatus,
  globalLoading,
  globalRunMs,
  canGlobalSubmit,
  onRun,
  onDownload,
  cookieHealth,
  facebookCookieHealth,
  onOpenCookieModal,
}) {
  const [viewMode, setViewMode] = useState('HUD')
  const [isSoundEnabled, setIsSoundEnabled] = useState(soundService.enabled)
  const [showResultsModal, setShowResultsModal] = useState(false)
  const [modalResult, setModalResult] = useState(null)
  const [modalSessionId, setModalSessionId] = useState('')
  const lastStoredResultRef = useRef(null)
  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]')
    } catch {
      return []
    }
  })
  const elapsedSeconds = Math.floor((globalRunMs || 0) / 1000)

  useEffect(() => {
    soundService.setEnabled(isSoundEnabled)
  }, [isSoundEnabled])

  useEffect(() => {
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 10)))
  }, [history])

  useEffect(() => {
    if (!globalLoading && globalResult?.status === 'done' && lastStoredResultRef.current !== globalResult) {
      lastStoredResultRef.current = globalResult
      const entry = {
        id: `SCAN_${Date.now()}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        totalItems: globalResult.total_count,
        elapsed_seconds: globalResult.elapsed_seconds,
        results: Object.fromEntries((globalResult.runs || []).map((run) => [run.source, run.count])),
        selectedNodesCount: (globalResult.runs || []).filter((run) => run.ok).length,
        strictMode: globalForm.strict_mode,
        antiNoise: globalForm.smart_filter,
        runs: globalResult.runs || [],
        result: globalResult,
      }
      queueMicrotask(() => {
        setHistory((prev) => {
          if (prev[0]?.id === entry.id) return prev
          return [entry, ...prev].slice(0, 10)
        })
        setModalResult(globalResult)
        setModalSessionId(entry.id)
        setShowResultsModal(true)
        soundService.playSuccess()
      })
    }
  }, [globalLoading, globalResult, globalForm.strict_mode, globalForm.smart_filter])

  const handleRun = () => {
    soundService.playScan()
    setShowResultsModal(false)
    setModalResult(null)
    onRun()
  }

  const handleClearHistory = () => {
    soundService.playClick()
    setHistory([])
  }

  const handleViewHistoryItem = (entry) => {
    soundService.playOpen()
    setModalResult(entry.result || { status: 'done', total_count: entry.totalItems, elapsed_seconds: entry.elapsed_seconds, runs: entry.runs || [] })
    setModalSessionId(entry.id)
    setShowResultsModal(true)
  }

  const handleExportEntry = (entry) => {
    soundService.playClick()
    const blob = new Blob([JSON.stringify(entry.result || entry, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `RADAR_GLOBAL_EXPORT_${entry.id}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const handleModalDownload = () => {
    if (modalResult?.items?.length && modalResult !== globalResult) {
      const blob = new Blob([JSON.stringify(modalResult.items, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `global_search_${Date.now()}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      return
    }
    onDownload()
  }

  return (
    <div className="gs-matrix-root min-h-screen bg-[#020502] flex items-center justify-center">
      <div className="crt-screen w-full h-screen flex flex-col relative overflow-hidden">
          <div className="scanline-anim" />
          <div className="screen-container flex-1 flex flex-col relative z-20">
            <GlobalSearchNavbar cookieHealth={cookieHealth} facebookCookieHealth={facebookCookieHealth} onOpenCookieModal={onOpenCookieModal} />
            <main className="relative z-10 flex-1 flex flex-col lg:flex-row overflow-hidden pb-16">
              <div className="w-full lg:w-80 shrink-0 border-b-2 lg:border-b-0 lg:border-r-2 border-matrix-green/20 bg-black/40 backdrop-blur-md p-4 flex flex-col gap-4 font-mono overflow-y-auto max-h-[35vh] lg:max-h-full">
                <div className="flex items-center justify-between border-b border-matrix-green/30 pb-2 shrink-0">
                  <div className="flex items-center gap-2 text-matrix-green text-[10px] font-black uppercase tracking-widest">
                    <Database size={12} />
                    <span>HISTORIAL_SESION</span>
                  </div>
                  <span className="text-[8px] bg-matrix-green/10 text-matrix-green px-1 border border-matrix-green/30 uppercase font-black animate-pulse">SESION_OK</span>
                </div>
                {history.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-matrix-green/10 text-matrix-green/30 self-center w-full min-h-[100px]">
                    <span className="text-[9px] uppercase font-black tracking-widest leading-relaxed text-matrix-green/40">SIN REGISTROS</span>
                    <span className="text-[8px] mt-1 text-center opacity-60">realice un escaneo para almacenar resultados</span>
                  </div>
                ) : (
                  <>
                    <div className="flex-1 space-y-3 overflow-y-auto pr-1">
                      {history.map((entry, index) => (
                        <div key={entry.id} className="border border-matrix-green/20 p-2.5 flex flex-col gap-1.5 hover:bg-matrix-green/5 transition-all group relative cursor-pointer" onClick={() => handleViewHistoryItem(entry)}>
                          <div className="flex items-center justify-between text-[9px] font-black">
                            <span className="text-matrix-green uppercase">LOG_#{history.length - index}</span>
                            <span className="text-matrix-green/40">{entry.timestamp}</span>
                          </div>
                          <div className="grid grid-cols-2 gap-1 text-[9px] tracking-tight">
                            <div><span className="text-matrix-green/40">TIENDAS:</span> <span className="font-black text-matrix-green">{entry.selectedNodesCount}</span></div>
                            <div><span className="text-matrix-green/40">TOTAL:</span> <span className="font-black text-matrix-green">{entry.totalItems}</span></div>
                            <div className="col-span-2"><span className="text-matrix-green/40">SEGUNDOS:</span> <span className="font-black text-matrix-green tabular-nums">{entry.elapsed_seconds ?? 0}s</span></div>
                          </div>
                          <div className="flex gap-2 text-[8px] font-bold text-matrix-green/30 uppercase leading-none">
                            <span>{entry.strictMode ? 'ESTRICTO' : 'NORMAL'}</span>
                            <span>•</span>
                            <span>{entry.antiNoise ? 'ANTI-RUIDO' : 'SIN FILTRO'}</span>
                          </div>
                          <div className="flex gap-1.5 mt-1 pt-1.5 border-t border-matrix-green/10">
                            <button type="button" onClick={(event) => { event.stopPropagation(); handleViewHistoryItem(entry) }} className="flex-1 py-1 border border-matrix-green/40 text-matrix-green bg-black hover:bg-matrix-green hover:text-black font-black text-[8px] uppercase tracking-widest transition-all text-center">VER_LOG</button>
                            <button type="button" onClick={(event) => { event.stopPropagation(); handleExportEntry(entry) }} className="px-2 py-1 border border-matrix-green/30 text-matrix-green/60 hover:text-matrix-green hover:border-matrix-green hover:bg-matrix-green/5 font-black text-[8px] uppercase transition-all flex items-center justify-center" title="Exportar JSON">
                              <Download size={10} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                    <button type="button" onClick={handleClearHistory} className="w-full py-2 bg-red-950/20 text-red-500 hover:bg-red-500 hover:text-black border border-red-500/30 hover:border-red-500 transition-all text-[9.5px] font-black uppercase tracking-widest shrink-0">LIMPIAR HISTORIAL</button>
                  </>
                )}
              </div>
              <div className="flex-1 overflow-y-auto">
                <AnimatePresence mode="wait">
                  {viewMode === 'HUD' ? (
                    <Motion.div key="hud" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
                      <GlobalSearchHUD
                        nodes={GLOBAL_NODES}
                        globalForm={globalForm}
                        onGlobalChange={onGlobalChange}
                        toggleGlobalSource={toggleGlobalSource}
                        globalCategories={globalCategories}
                        globalCategoriesLoading={globalCategoriesLoading}
                        categorySuggestion={categorySuggestion}
                        onResetAllCategories={onResetAllCategories}
                        onReapplyCategorySuggestions={onReapplyCategorySuggestions}
                        onStartProcess={handleRun}
                        onConfigClick={() => { soundService.playOpen(); setViewMode('MATRIX') }}
                        isProcessing={globalLoading}
                        canGlobalSubmit={canGlobalSubmit}
                        elapsedSeconds={elapsedSeconds}
                        isSoundEnabled={isSoundEnabled}
                        setIsSoundEnabled={setIsSoundEnabled}
                        globalResult={globalResult}
                      />
                    </Motion.div>
                  ) : (
                    <Motion.div key="matrix" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }} className="relative p-4 md:p-6">
                      <div className="max-w-[1400px] mx-auto mb-6 flex items-center justify-between bg-matrix-green px-4 py-1 text-black font-bold">
                        <button type="button" onClick={() => { soundService.playClick(); setViewMode('HUD') }} className="flex items-center gap-2 text-xs font-mono tracking-widest uppercase hover:opacity-80 transition-all font-black">
                          <ChevronLeft size={16} strokeWidth={3} />
                          RETORNO_A_HUB
                        </button>
                        {globalStatus && <span className="text-[10px] uppercase truncate max-w-[55%]">{globalStatus}</span>}
                      </div>
                      <GlobalSearchMatrix
                        nodes={GLOBAL_NODES}
                        globalForm={globalForm}
                        onGlobalChange={onGlobalChange}
                        toggleGlobalSource={toggleGlobalSource}
                        categorySuggestion={categorySuggestion}
                        onResetAllCategories={onResetAllCategories}
                        onReapplyCategorySuggestions={onReapplyCategorySuggestions}
                        globalCategoriesLoading={globalCategoriesLoading}
                        onStartProcess={handleRun}
                        globalResult={globalResult}
                        canGlobalSubmit={canGlobalSubmit}
                        globalLoading={globalLoading}
                      />
                    </Motion.div>
                  )}
                </AnimatePresence>
              </div>
            </main>
            <AnimatePresence>
              {showResultsModal && modalResult && (
                <GlobalSearchResultsModal
                  globalResult={modalResult}
                  sessionId={modalSessionId}
                  onClose={() => setShowResultsModal(false)}
                  onDownload={handleModalDownload}
                />
              )}
            </AnimatePresence>
          </div>
          <div className="pointer-events-none absolute inset-0 z-[110] bg-[radial-gradient(circle_at_center,_rgba(51,255,102,0.05)_0%,_transparent_70%)]" />
      </div>
    </div>
  )
}

