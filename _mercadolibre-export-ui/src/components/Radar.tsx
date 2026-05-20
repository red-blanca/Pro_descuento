import { motion, AnimatePresence } from 'motion/react';
import { useState, useEffect } from 'react';
import { soundService } from '../services/soundService';

export default function Radar() {
  const [dots, setDots] = useState<{ id: number; x: number; y: number }[]>([]);

  useEffect(() => {
    const interval = setInterval(() => {
      const newDot = {
        id: Date.now(),
        x: Math.random() * 80 + 10, // 10% to 90%
        y: Math.random() * 80 + 10,
      };
      setDots(prev => [...prev.slice(-15), newDot]);
      soundService.playRadarBeep();
    }, 400);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative w-80 h-80 flex items-center justify-center">
      {/* Radar Background */}
      <div className="absolute inset-0 rounded-full border-4 border-matrix-green shadow-[0_0_30px_rgba(51,255,102,0.2)] bg-black overflow-hidden">
        {/* Grid Lines */}
        <div className="absolute inset-0 grid grid-cols-4 grid-rows-4 opacity-10">
          {[...Array(4)].map((_, i) => (
            <div key={`v-${i}`} className="border-r border-matrix-green" />
          ))}
          {[...Array(4)].map((_, i) => (
            <div key={`h-${i}`} className="border-b border-matrix-green" />
          ))}
        </div>
        
        {/* Concentric Circles */}
        <div className="absolute inset-[25%] border border-matrix-green/20 rounded-full" />
        <div className="absolute inset-[50%] border border-matrix-green/20 rounded-full" />
        <div className="absolute inset-[75%] border border-matrix-green/20 rounded-full" />

        {/* Sweep Animation */}
        <motion.div 
          className="absolute inset-[-50%] origin-center bg-[conic-gradient(from_0deg,_transparent_0deg,_rgba(51,255,102,0.3)_90deg,_transparent_90deg)]"
          animate={{ rotate: 360 }}
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
        />

        {/* Detected Dots */}
        <AnimatePresence>
          {dots.map(dot => (
            <motion.div
              key={dot.id}
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: [0, 1, 0], scale: [0.5, 1.2, 0.5] }}
              exit={{ opacity: 0 }}
              transition={{ duration: 2 }}
              className="absolute w-2 h-2 bg-matrix-green rounded-full glow-matrix"
              style={{ left: `${dot.x}%`, top: `${dot.y}%` }}
            >
              <div className="absolute -inset-2 border border-matrix-green/30 rounded-full animate-ping" />
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Radar Overlay Label */}
        <div className="absolute top-4 left-0 right-0 text-center">
          <span className="text-[10px] font-black text-matrix-green animate-pulse uppercase tracking-[0.2em]">RADAR_SCAN_ACTIVE</span>
        </div>
        
        <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-4 text-[8px] font-black text-matrix-green/40">
          <span>LAT: 43.123</span>
          <span>LNG: 12.456</span>
          <span>OBJ: {dots.length}</span>
        </div>
      </div>
    </div>
  );
}
