import { AnimatePresence, motion as Motion } from 'motion/react'
import { CheckSquare, Search, Settings, Settings2, Square, Volume2, VolumeX } from 'lucide-react'
import { useState } from 'react'
import GlobalSearchCategoryControls from './GlobalSearchCategoryControls'
import GlobalSearchFilterModal from './GlobalSearchFilterModal'
import GlobalSearchNodeIcon from './GlobalSearchNodeIcon'
import GlobalSearchRadar from './GlobalSearchRadar'
import { getRunForNode, isNodeActive } from './globalSearchNodes'
import { soundService } from './soundService'

export default function GlobalSearchHUD({
  nodes,
  globalForm,
  onGlobalChange,
  toggleGlobalSource,
  globalCategories,
  globalCategoriesLoading,
  categorySuggestion,
  onResetAllCategories,
  onReapplyCategorySuggestions,
  onStartProcess,
  onAbort,
  onConfigClick,
  isProcessing,
  canGlobalSubmit,
  elapsedSeconds,
  isSoundEnabled,
  setIsSoundEnabled,
  globalResult,
}) {
  const [selectedNodeForConfig, setSelectedNodeForConfig] = useState(null)
  const runs = globalResult?.runs || []
  const activeCount = nodes.filter((node) => isNodeActive(node, globalForm.sources)).length
  const allSelected = nodes.length > 0 && activeCount === nodes.length

  const handleToggleAllStores = () => {
    soundService.playClick()
    onGlobalChange('sources', allSelected ? [] : nodes.map((node) => node.sourceKey))
  }

  return (
    <div className="relative flex flex-col items-center justify-center min-h-[calc(100vh-200px)] pt-12 pb-20">
      <AnimatePresence>
        {selectedNodeForConfig && isNodeActive(selectedNodeForConfig, globalForm.sources) && (
          <GlobalSearchFilterModal
            node={selectedNodeForConfig}
            globalForm={globalForm}
            onGlobalChange={onGlobalChange}
            globalCategories={globalCategories}
            globalCategoriesLoading={globalCategoriesLoading}
            onClose={() => setSelectedNodeForConfig(null)}
          />
        )}
      </AnimatePresence>
      <div className="relative w-[500px] h-[500px] md:w-[600px] md:h-[600px] flex items-center justify-center">
        <Motion.div className="absolute inset-0 border-2 border-matrix-green/10 rounded-full" animate={{ rotate: 360 }} transition={{ duration: 150, repeat: Infinity, ease: 'linear' }} />
        <div className="absolute inset-[10%] border border-matrix-green/5 rounded-full border-dashed animate-[spin_100s_reverse_linear_infinite]" />
        {nodes.map((node, index) => {
          const angle = (index / nodes.length) * 360
          const active = isNodeActive(node, globalForm.sources)
          const run = getRunForNode(node, runs)
          return (
            <div
              key={node.id}
              className="absolute group z-10"
              style={{
                left: `calc(50% + ${Math.cos((angle * Math.PI) / 180) * 45}%)`,
                top: `calc(50% + ${Math.sin((angle * Math.PI) / 180) * 45}%)`,
                transform: 'translate(-50%, -50%)',
              }}
            >
              <button
                type="button"
                disabled={!active}
                onClick={(event) => {
                  event.stopPropagation()
                  if (!active) return
                  soundService.playOpen()
                  setSelectedNodeForConfig(node)
                }}
                className={`absolute -top-3 -right-3 z-20 w-7 h-7 font-black text-[8px] border-2 transition-all flex items-center justify-center ${active ? 'bg-matrix-green text-black border-black cursor-pointer hover:scale-110 active:scale-95 shadow-[0_0_10px_rgba(51,255,102,0.5)]' : 'bg-black text-matrix-green/20 border-matrix-green/20 cursor-not-allowed opacity-40'}`}
                title={active ? `Configurar ${node.name}` : `Activa ${node.name} para configurar`}
              >
                <Settings size={14} strokeWidth={3} />
              </button>
              <Motion.button
                onClick={() => {
                  soundService.playClick()
                  toggleGlobalSource(node.sourceKey)
                }}
                className={`p-3 border-2 font-mono transition-all hover:scale-105 active:scale-95 flex items-center gap-4 relative overflow-hidden ${active ? 'bg-matrix-green text-black border-matrix-green font-black glow-matrix shadow-[0_0_15px_rgba(51,255,102,0.4)]' : 'bg-black text-matrix-green/60 border-matrix-green/20 hover:border-matrix-green hover:text-matrix-green'}`}
              >
                <div className="relative">
                  <GlobalSearchNodeIcon name={node.icon} size={24} strokeWidth={2.5} />
                  <div className={`absolute -top-1 -right-1 w-2.5 h-2.5 border-2 ${active ? 'bg-black border-black' : 'bg-black border-matrix-green/40'}`} />
                </div>
                <div className="flex flex-col items-start leading-tight">
                  <span className="text-xs font-black uppercase tracking-widest">{node.name}</span>
                  <span className="text-[8px] opacity-60">ID_{100 + index}</span>
                </div>
                {run && (
                  <Motion.div initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="absolute bottom-1 right-1 bg-black text-matrix-green border border-matrix-green px-1 text-[8px] font-black">
                    {run.count ?? 0} PCS
                  </Motion.div>
                )}
              </Motion.button>
            </div>
          )
        })}
        <AnimatePresence mode="wait">
          {isProcessing ? (
            <Motion.div
              key="radar-mode"
              initial={{ scale: 0.5, opacity: 0, rotate: -45 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ scale: 0.5, opacity: 0, rotate: 45 }}
              transition={{ duration: 0.6, type: 'spring' }}
            >
              <GlobalSearchRadar elapsedSeconds={elapsedSeconds} onStop={onAbort} />
            </Motion.div>
          ) : (
            <Motion.div
              key="config-core"
              className="relative flex flex-col overflow-hidden border-4 border-matrix-green bg-black w-80 h-80 shadow-[0_0_50px_rgba(51,255,102,0.1)] group"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 1.2, opacity: 0, filter: 'blur(10px)' }}
              transition={{ duration: 0.5, type: 'spring', damping: 15 }}
            >
              <div className="shrink-0 h-6 bg-matrix-green text-black text-[9px] font-black flex items-center px-2 tracking-widest">RADAR COMERCIAL</div>
              <div className="flex flex-1 flex-col items-center text-center px-6 pt-3 pb-5 gap-3 min-h-0">
                <Motion.div
                  className="relative shrink-0 cursor-pointer group/search"
                  onClick={() => !isProcessing && canGlobalSubmit && onStartProcess()}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95, rotate: -8 }}
                >
                  <div className="absolute inset-0 bg-matrix-green/20 blur-xl scale-125 opacity-0 group-hover/search:opacity-100 transition-opacity pointer-events-none" />
                  <Search className="text-matrix-green glow-matrix relative z-10 p-3 border-4 border-matrix-green/40 bg-black hover:border-matrix-green transition-colors" size={64} strokeWidth={2.5} />
                  <Motion.div
                    className="absolute -inset-2 border-2 border-matrix-green opacity-20 pointer-events-none"
                    animate={{ scale: [1, 1.12, 1], opacity: [0.2, 0.35, 0.2] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  />
                </Motion.div>

                <div className="w-full relative flex flex-col justify-center gap-1.5">
                  <input
                    id="hud-search-input"
                    type="text"
                    value={globalForm.query}
                    onChange={(event) => onGlobalChange('query', event.target.value)}
                    placeholder="DIGITAR TERMINO..."
                    disabled={isProcessing}
                    autoComplete="off"
                    spellCheck={false}
                    onKeyDown={(event) => {
                      const isCharacterKey = event.key.length === 1 || event.key === 'Backspace' || event.key === 'Delete'
                      if (isCharacterKey && !event.ctrlKey && !event.metaKey && !event.altKey) {
                        soundService.playKey()
                      }
                      if (event.key === 'Enter' && canGlobalSubmit && !isProcessing) {
                        soundService.playClick()
                        onStartProcess()
                      }
                    }}
                    className="w-full bg-black border-2 border-matrix-green py-2.5 px-4 text-base font-mono font-bold text-matrix-green outline-none text-center placeholder-matrix-green/30 uppercase focus:border-matrix-green focus:bg-matrix-green/10 transition-all glow-matrix tracking-widest shadow-[inset_0_0_15px_rgba(51,255,102,0.15)] focus:shadow-[0_0_20px_rgba(51,255,102,0.25)] disabled:opacity-70"
                  />
                  <span className="text-[8.5px] font-mono text-matrix-green/45 uppercase text-center tracking-wider block">
                    Presione ENTER para comenzar escaneo
                  </span>
                  <GlobalSearchCategoryControls
                    globalForm={globalForm}
                    onGlobalChange={onGlobalChange}
                    categorySuggestion={categorySuggestion}
                    globalCategoriesLoading={globalCategoriesLoading}
                    onResetAllCategories={onResetAllCategories}
                    onReapplyCategorySuggestions={onReapplyCategorySuggestions}
                    compact
                  />
                </div>

                <button
                  type="button"
                  onClick={onConfigClick}
                  className="shrink-0 w-full py-2 bg-matrix-green text-black font-black text-xs uppercase hover:bg-white transition-all shadow-[0_0_15px_rgba(51,255,102,0.3)] flex items-center justify-center gap-2"
                >
                  <Settings2 size={14} strokeWidth={3} />
                  MODIFICAR_FILTROS
                </button>
              </div>
            </Motion.div>
          )}
        </AnimatePresence>
      </div>
      <div className="absolute top-10 left-10 z-50">
        <button
          type="button"
          disabled={isProcessing}
          onClick={handleToggleAllStores}
          title={allSelected ? 'Deseleccionar todas las tiendas' : 'Seleccionar todas las tiendas'}
          className={`flex items-center gap-2 px-3 py-1.5 border-2 transition-all font-black text-[10px] uppercase disabled:opacity-50 disabled:cursor-not-allowed ${allSelected ? 'bg-matrix-green text-black border-matrix-green shadow-[0_0_15px_rgba(51,255,102,0.3)]' : 'bg-black text-matrix-green/60 border-matrix-green/30 hover:border-matrix-green hover:text-matrix-green'}`}
        >
          {allSelected ? <CheckSquare size={14} strokeWidth={3} /> : <Square size={14} strokeWidth={3} />}
          {allSelected ? 'DESELECCIONAR_TODAS' : 'SELECCIONAR_TODAS'}
          <span className="text-[8px] opacity-70">({activeCount}/{nodes.length})</span>
        </button>
      </div>
      <div className="absolute top-10 right-10 z-50">
        <button onClick={() => { soundService.playClick(); setIsSoundEnabled(!isSoundEnabled) }} className={`flex items-center gap-2 px-3 py-1.5 border-2 transition-all font-black text-[10px] uppercase ${isSoundEnabled ? 'bg-matrix-green text-black border-matrix-green shadow-[0_0_15px_rgba(51,255,102,0.3)]' : 'bg-black text-matrix-green/40 border-matrix-green/20 hover:border-matrix-green hover:text-matrix-green'}`}>
          {isSoundEnabled ? <Volume2 size={14} strokeWidth={3} /> : <VolumeX size={14} strokeWidth={3} />}
          {isSoundEnabled ? 'AUDIO_ON' : 'AUDIO_OFF'}
        </button>
      </div>
    </div>
  )
}
