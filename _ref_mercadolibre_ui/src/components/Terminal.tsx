import { motion } from 'motion/react';
import { XCircle } from 'lucide-react';
import { soundService } from '../services/soundService';
import { useEffect } from 'react';

const LOGS = [
  "> INICIALIZANDO RADAR COMERCIAL...",
  "> FETCHING_ENCRYPTED_KEYS... DONE",
  "> ESTABLECIENDO RADAR COMERCIAL...",
  "> BYPASSING_CACHE_LAYERS... OK",
  "> FILTERING_MALFORMED_DATA_PACKETS...",
  "> RECONSTRUCTING_STREAM_BUFFER...",
  "> FINALIZING_PARSING_SEQUENCE...",
];

interface TerminalProps {
  progress: number;
  onStop: () => void;
}

export default function Terminal({ progress, onStop }: TerminalProps) {
  // Show more logs as progress increases
  const visibleLogsCount = Math.floor((progress / 100) * LOGS.length) + 1;
  const visibleLogs = LOGS.slice(0, visibleLogsCount);

  useEffect(() => {
    if (visibleLogsCount > 0 && progress < 100) {
      soundService.playBeep(800 + Math.random() * 200, 0.05);
    }
  }, [visibleLogsCount]);

  return (
    <footer className="fixed bottom-0 left-0 w-full z-[120] bg-black text-matrix-green border-t-4 border-matrix-green p-6 font-black shadow-[0_-15px_40px_rgba(51,255,102,0.15)] flex flex-col gap-4">
      <div className="flex justify-between items-center border-b border-matrix-green/30 pb-2 box-border px-2">
        <div className="flex gap-6 items-center">
          <span className="text-[12px] uppercase tracking-[0.3em] glow-matrix font-black">
            RADAR COMERCIAL ESCANER // NUCLEO ACTIVO
          </span>
          <div className="flex items-center gap-2">
             <div className="w-2.5 h-2.5 rounded-full bg-matrix-green animate-pulse shadow-[0_0_10px_rgba(51,255,102,0.8)]" />
             <span className="text-[10px] uppercase tracking-wider font-extrabold">LINK_ESTABLISHED</span>
          </div>
        </div>

        <button 
          onClick={onStop}
          className="flex items-center gap-2 text-[10px] uppercase tracking-widest border-2 border-matrix-green px-4 py-1.5 bg-matrix-green text-black hover:bg-black hover:text-matrix-green transition-all active:scale-95 font-black shrink-0"
        >
          <XCircle size={14} strokeWidth={3} />
          ABORTAR ESCANEO
        </button>
      </div>
      
      {/* Gigantic Progress and Percentage Row */}
      <div className="flex flex-col md:flex-row items-center gap-6 w-full px-2 my-2">
        <div className="flex-1 h-10 md:h-12 border-4 border-matrix-green bg-matrix-green/5 relative overflow-hidden shadow-[0_0_25px_rgba(51,255,102,0.1)] w-full">
           <motion.div 
             className="absolute inset-y-0 left-0 bg-matrix-green shadow-[0_0_30px_rgba(51,255,102,0.8)]"
             initial={{ width: 0 }}
             animate={{ width: `${progress}%` }}
             transition={{ type: "spring", damping: 20 }}
           />
        </div>
        <div className="text-4xl md:text-5xl font-mono font-black text-matrix-green tracking-widest bg-matrix-green/10 px-5 py-2 border-4 border-matrix-green min-w-[190px] text-center shrink-0 uppercase shadow-[0_0_20px_rgba(51,255,102,0.2)] glow-matrix">
          {Math.floor(progress)}%
        </div>
      </div>
      
      {/* Terminal Display */}
      <div className="h-24 md:h-28 overflow-hidden bg-black border-4 border-black p-4 font-mono text-xs text-matrix-green shadow-[inset_0_0_20px_rgba(0,0,0,0.8)]">
        <div className="space-y-1">
          {visibleLogs.map((log, i) => (
            <motion.p 
              key={`${log}-${i}`}
              initial={{ opacity: 0, x: -5 }}
              animate={{ opacity: 1, x: 0 }}
              className={`${i === visibleLogs.length - 1 ? "glow-matrix" : "opacity-60"} uppercase leading-none`}
            >
              {log}
            </motion.p>
          ))}
          {progress < 100 && (
            <motion.p 
              animate={{ opacity: [0, 1, 0] }}
              transition={{ repeat: Infinity, duration: 0.5 }}
              className="font-black"
            >
              &gt; PROCESSING_DATA_BIT_{Math.random().toString(16).slice(2, 6)}...
            </motion.p>
          )}
        </div>
      </div>
    </footer>
  );
}
