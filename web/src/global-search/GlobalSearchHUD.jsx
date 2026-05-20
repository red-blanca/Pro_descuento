import { AnimatePresence, motion } from 'motion/react'
import { Search, Settings, Settings2, Volume2, VolumeX } from 'lucide-react'
import { useState } from 'react'
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
  onStartProcess,
  onConfigClick,
  isProcessing,
  isSoundEnabled,
  setIsSoundEnabled,
  globalResult,
}) {
  const [selectedNodeForConfig, setSelectedNodeForConfig] = useState(null)
  const runs = globalResult?.runs || []

  return (
    <motion.div className="relative flex min-h-[calc(100dvh-8rem)] flex-col items-center justify-center pt-12 pb-20">
      <AnimatePresence>
        {selectedNodeForConfig && (
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
      <div className="relative w-[340px] h-[340px] md:w-[600px] md:h-[600px] flex items-center justify-center">
        <motion.div className="absolute inset-0 border-2 border-matrix-green/10 rounded-full" animate={{ rotate: 360 }} transition={{ duration: 150, repeat: Infinity, ease: 'linear' }} />
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
                onClick={(event) => {
                  event.stopPropagation()
                  if (active) {
                    soundService.playOpen()
                    setSelectedNodeForConfig(node)
                  }
                }}
                disabled={!active}
                className={`absolute -top-3 -right-3 z-20 w-7 h-7 font-black text-[8px] border-2 transition-all flex items-center justify-center ${active ? 'bg-matrix-green text-black border-black cursor-pointer hover:scale-110 active:scale-95 shadow-[0_0_10px_rgba(51,255,102,0.5)]' : 'bg-black text-matrix-green/20 border-matrix-green/20 cursor-not-allowed opacity-0 group-hover:opacity-100'}`}
              >
                <Settings size={14} strokeWidth={3} />
              </button>
              <motion.button
                onClick={() => {
                  soundService.playClick()
                  toggleGlobalSource(node.sourceKey)
                }}
                className={`p-2 md:p-3 border-2 font-mono transition-all hover:scale-105 active:scale-95 flex items-center gap-2 md:gap-4 relative overflow-hidden ${active ? 'bg-matrix-green text-black border-matrix-green font-black glow-matrix shadow-[0_0_15px_rgba(51,255,102,0.4)]' : 'bg-black text-matrix-green/60 border-matrix-green/20 hover:border-matrix-green hover:text-matrix-green'}`}
              >
                <div className="relative">
                  <GlobalSearchNodeIcon name={node.icon} size={24} strokeWidth={2.5} />
                  <div className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full border-2 ${active ? 'bg-black border-black' : 'bg-black border-matrix-green/40'}`} />
                </div>
                <div className="hidden md:flex flex-col items-start leading-tight">
                  <span className="text-xs font-black uppercase tracking-widest">{node.name}</span>
                  <span className="text-[8px] opacity-60">ID_{100 + index}</span>
                </div>
                {run && (
                  <motion.div initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="absolute bottom-1 right-1 bg-black text-matrix-green border border-matrix-green px-1 text-[8px] font-black">
                    {run.count ?? 0} PCS
                  </motion.div>
                )}
              </motion.button>
            </div>
          )
        })}
        <AnimatePresence mode="wait">
          {!isProcessing ? (
            <motion.div
              key="config-core"
              className="relative flex flex-col items-center justify-center p-5 md:p-8 text-center border-4 border-matrix-green bg-black w-64 h-64 md:w-80 md:h-80 shadow-[0_0_50px_rgba(51,255,102,0.1)] group"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 1.2, opacity: 0, filter: 'blur(10px)' }}
              transition={{ duration: 0.5, type: 'spring', damping: 15 }}
            >
              <div className="absolute top-2 left-0 right-0 h-4 bg-matrix-green text-black text-[9px] font-black flex items-center px-2">RADAR COMERCIAL</div>
              <motion.div className="relative mb-4 md:mb-6 cursor-pointer group/search" onClick={onStartProcess} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9, rotate: -10 }}>
                <div className="absolute inset-0 bg-matrix-green/20 rounded-full blur-xl scale-150 opacity-0 group-hover/search:opacity-100 transition-opacity" />
                <Search className="text-matrix-green glow-matrix relative z-10 p-4 border-4 border-matrix-green/40 rounded-full bg-black hover:border-matrix-green transition-colors" size={76} strokeWidth={2.5} />
                <motion.div className="absolute -inset-4 border-2 border-matrix-green rounded-full opacity-20" animate={{ scale: [1, 1.2, 1], opacity: [0.2, 0.4, 0.2] }} transition={{ duration: 3, repeat: Infinity }} />
              </motion.div>
              <h2 className="text-lg md:text-xl font-black italic tracking-tighter text-matrix-green glow-matrix mb-4 uppercase">BUSQUEDA PRODUCTOS</h2>
              <div className="grid grid-cols-2 gap-3 md:gap-4 w-full h-20 md:h-24">
                <button onClick={(event) => { event.stopPropagation(); soundService.playClick(); onGlobalChange('strict_mode', !globalForm.strict_mode) }} className={`flex flex-col items-center justify-center border-2 p-2 transition-all group ${globalForm.strict_mode ? 'bg-matrix-green text-black border-matrix-green' : 'bg-black text-matrix-green border-matrix-green/30 hover:border-matrix-green'}`}>
                  <div className={`w-4 h-4 rounded-full border-2 mb-1 flex items-center justify-center ${globalForm.strict_mode ? 'bg-black border-black' : 'border-matrix-green'}`}>{globalForm.strict_mode && <div className="w-1.5 h-1.5 bg-matrix-green rounded-full" />}</div>
                  <span className="text-[8px] font-black uppercase text-center leading-none">MODO_ESTRICTO</span>
                </button>
                <button onClick={(event) => { event.stopPropagation(); soundService.playClick(); onGlobalChange('smart_filter', !globalForm.smart_filter) }} className={`flex flex-col items-center justify-center border-2 p-2 transition-all group ${globalForm.smart_filter ? 'bg-matrix-green text-black border-matrix-green' : 'bg-black text-matrix-green border-matrix-green/30 hover:border-matrix-green'}`}>
                  <div className={`w-4 h-4 rounded-full border-2 mb-1 flex items-center justify-center ${globalForm.smart_filter ? 'bg-black border-black' : 'border-matrix-green'}`}>{globalForm.smart_filter && <div className="w-1.5 h-1.5 bg-matrix-green rounded-full" />}</div>
                  <span className="text-[8px] font-black uppercase text-center leading-none">ANTI_RUIDO</span>
                </button>
              </div>
              <button onClick={onConfigClick} className="mt-4 w-full py-2 bg-matrix-green text-black font-black text-xs uppercase hover:bg-white transition-all shadow-[0_0_15px_rgba(51,255,102,0.3)] flex items-center justify-center gap-2">
                <Settings2 size={14} strokeWidth={3} />
                MODIFICAR_FILTROS
              </button>
            </motion.div>
          ) : (
            <motion.div key="radar-mode" initial={{ scale: 0.5, opacity: 0, rotate: -45 }} animate={{ scale: 1, opacity: 1, rotate: 0 }} exit={{ scale: 0.5, opacity: 0, rotate: 45 }} transition={{ duration: 0.6, type: 'spring' }}>
              <GlobalSearchRadar />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <div className="absolute top-4 md:top-10 right-4 md:right-10 z-50">
        <button onClick={() => { soundService.playClick(); setIsSoundEnabled(!isSoundEnabled) }} className={`flex items-center gap-2 px-3 py-1.5 border-2 transition-all font-black text-[10px] uppercase ${isSoundEnabled ? 'bg-matrix-green text-black border-matrix-green shadow-[0_0_15px_rgba(51,255,102,0.3)]' : 'bg-black text-matrix-green/40 border-matrix-green/20 hover:border-matrix-green hover:text-matrix-green'}`}>
          {isSoundEnabled ? <Volume2 size={14} strokeWidth={3} /> : <VolumeX size={14} strokeWidth={3} />}
          {isSoundEnabled ? 'AUDIO_ON' : 'AUDIO_OFF'}
        </button>
      </div>
    </motion.div>
  )
}
