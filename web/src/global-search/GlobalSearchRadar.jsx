import { AnimatePresence, motion as Motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { soundService } from './soundService'

export default function GlobalSearchRadar({ elapsedSeconds = 0 }) {
  const [dots, setDots] = useState([])

  useEffect(() => {
    soundService.startRadarLoop()
    const interval = setInterval(() => {
      if (document.hidden) return // Pause generating dots if the tab is inactive
      const nextDot = {
        id: Date.now() + Math.random(),
        x: Math.random() * 80 + 10,
        y: Math.random() * 80 + 10,
      }
      setDots((prev) => [...prev.slice(-8), nextDot])
    }, 400)
    return () => {
      clearInterval(interval)
      soundService.stopRadarLoop()
    }
  }, [])

  return (
    <div className="relative w-80 h-80 flex items-center justify-center">
      <div className="absolute inset-0 rounded-full border-4 border-matrix-green shadow-[0_0_30px_rgba(51,255,102,0.2)] bg-black overflow-hidden">
        <div className="absolute inset-0 grid grid-cols-4 grid-rows-4 opacity-10">
          {[...Array(4)].map((_, index) => <div key={`v-${index}`} className="border-r border-matrix-green" />)}
          {[...Array(4)].map((_, index) => <div key={`h-${index}`} className="border-b border-matrix-green" />)}
        </div>
        <div className="absolute inset-[25%] border border-matrix-green/20 rounded-full" />
        <div className="absolute inset-[50%] border border-matrix-green/20 rounded-full" />
        <div className="absolute inset-[75%] border border-matrix-green/20 rounded-full" />
        <Motion.div
          className="absolute inset-[-50%] origin-center bg-[conic-gradient(from_0deg,_transparent_0deg,_rgba(51,255,102,0.3)_90deg,_transparent_90deg)]"
          animate={{ rotate: 360 }}
          transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
        />
        <AnimatePresence>
          {dots.map((dot) => (
            <Motion.div
              key={dot.id}
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: [0, 1, 0], scale: [0.5, 1.2, 0.5] }}
              exit={{ opacity: 0 }}
              transition={{ duration: 2 }}
              className="absolute w-2 h-2 bg-matrix-green rounded-full glow-matrix"
              style={{ left: `${dot.x}%`, top: `${dot.y}%` }}
            >
              <div className="absolute -inset-2 border border-matrix-green/30 rounded-full animate-ping" />
            </Motion.div>
          ))}
        </AnimatePresence>
        <div className="absolute top-4 left-0 right-0 text-center">
          <span className="text-[10px] font-black text-matrix-green animate-pulse uppercase tracking-[0.2em]">RADAR_SCAN_ACTIVE</span>
        </div>
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="bg-black/85 border-4 border-matrix-green px-5 py-3 text-center shadow-[0_0_30px_rgba(51,255,102,0.35)]">
            <div className="text-[8px] font-black uppercase tracking-[0.35em] text-matrix-green/55">TIEMPO_TRANSCURRIDO</div>
            <div className="text-5xl font-black tabular-nums text-matrix-green glow-matrix leading-none">{elapsedSeconds}s</div>
          </div>
        </div>
        <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-4 text-[8px] font-black text-matrix-green/40">
          <span>LAT: 43.123</span>
          <span>LNG: 12.456</span>
          <span>OBJ: {dots.length}</span>
        </div>
      </div>
    </div>
  )
}

