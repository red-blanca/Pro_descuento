import { motion, AnimatePresence } from 'motion/react';
import { Database, Search, Settings2, Volume2, VolumeX, Settings } from 'lucide-react';
import { Node } from '../constants';
import NodeIcon from './NodeIcon';
import Radar from './Radar';
import FilterModal from './FilterModal';
import { soundService } from '../services/soundService';
import { useState } from 'react';

interface HUDProps {
  nodes: Node[];
  onSelectNode: (nodeId: string) => void;
  onStartProcess: () => void;
  onConfigClick: () => void;
  isProcessing: boolean;
  strictMode: boolean;
  setStrictMode: (val: boolean) => void;
  antiNoise: boolean;
  setAntiNoise: (val: boolean) => void;
  isSoundEnabled: boolean;
  setIsSoundEnabled: (val: boolean) => void;
  scanResults: Record<string, number>;
}

export default function HUD({ 
  nodes,
  onSelectNode, 
  onStartProcess,
  onConfigClick,
  isProcessing,
  strictMode,
  setStrictMode,
  antiNoise,
  setAntiNoise,
  isSoundEnabled,
  setIsSoundEnabled,
  scanResults
}: HUDProps) {
  const [selectedNodeForConfig, setSelectedNodeForConfig] = useState<Node | null>(null);

  const hasResults = Object.keys(scanResults).length > 0;

  return (
    <div className="relative flex flex-col items-center justify-center min-h-[calc(100vh-200px)] pt-12 pb-20">
      <AnimatePresence>
        {selectedNodeForConfig && (
          <FilterModal 
            node={selectedNodeForConfig} 
            onClose={() => setSelectedNodeForConfig(null)} 
          />
        )}
      </AnimatePresence>
      {/* Orbital Ring System */}
      <div className="relative w-[500px] h-[500px] md:w-[600px] md:h-[600px] flex items-center justify-center">
        <motion.div 
          className="absolute inset-0 border-2 border-matrix-green/10 rounded-full"
          animate={{ rotate: 360 }}
          transition={{ duration: 150, repeat: Infinity, ease: "linear" }}
        />
        <div className="absolute inset-[10%] border border-matrix-green/5 rounded-full border-dashed animate-[spin_100s_reverse_linear_infinite]" />
        
        {/* Nodes around the orbit */}
        {nodes.map((node, index) => {
          const angle = (index / nodes.length) * 360;
          const resultCount = scanResults[node.id];
          
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
              {/* Config Button (Corner) */}
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  if (node.active) {
                    soundService.playOpen();
                    setSelectedNodeForConfig(node);
                  }
                }}
                disabled={!node.active}
                className={`absolute -top-3 -right-3 z-20 w-7 h-7 font-black text-[8px] border-2 transition-all flex items-center justify-center
                  ${node.active 
                    ? 'bg-matrix-green text-black border-black cursor-pointer hover:scale-110 active:scale-95 shadow-[0_0_10px_rgba(51,255,102,0.5)]' 
                    : 'bg-black text-matrix-green/20 border-matrix-green/20 cursor-not-allowed opacity-0 group-hover:opacity-100'}`}
              >
                <Settings size={14} strokeWidth={3} />
              </button>

              <motion.button
                onClick={() => {
                  soundService.playClick();
                  onSelectNode(node.id);
                }}
                className={`p-3 border-2 font-mono transition-all hover:scale-105 active:scale-95 flex items-center gap-4 relative overflow-hidden
                  ${node.active 
                    ? 'bg-matrix-green text-black border-matrix-green font-black glow-matrix shadow-[0_0_15px_rgba(51,255,102,0.4)]' 
                    : 'bg-black text-matrix-green/60 border-matrix-green/20 hover:border-matrix-green hover:text-matrix-green'}`}
              >
                {/* Logo / Icon */}
                <div className="relative">
                  <NodeIcon name={node.icon} size={24} strokeWidth={2.5} />
                  <div className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full border-2 ${node.active ? 'bg-black border-black' : 'bg-black border-matrix-green/40'}`} />
                </div>
                <div className="flex flex-col items-start leading-tight">
                  <span className="text-xs font-black uppercase tracking-widest">{node.name}</span>
                  <span className="text-[8px] opacity-60">ID_{100 + index}</span>
                </div>

                {/* Result Indicator Badge */}
                {resultCount !== undefined && (
                  <motion.div 
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="absolute bottom-1 right-1 bg-black text-matrix-green border border-matrix-green px-1 text-[8px] font-black"
                  >
                    {resultCount} PCS
                  </motion.div>
                )}
              </motion.button>
            </div>
          );
        })}

        {/* Central Component Switcher */}
        <AnimatePresence mode="wait">
          {!isProcessing ? (
            <motion.div 
              key="config-core"
              className="relative flex flex-col items-center justify-center p-8 text-center border-4 border-matrix-green bg-black w-80 h-80 shadow-[0_0_50px_rgba(51,255,102,0.1)] group"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 1.2, opacity: 0, filter: 'blur(10px)' }}
              transition={{ duration: 0.5, type: "spring", damping: 15 }}
            >
              <div className="absolute top-2 left-0 right-0 h-4 bg-matrix-green text-black text-[9px] font-black flex items-center px-2">RADAR COMERCIAL</div>
              
              {/* Logo / Interaction Area */}
              <motion.div 
                className="relative mb-6 cursor-pointer group/search" 
                onClick={onStartProcess}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9, rotate: -10 }}
              >
                <div className="absolute inset-0 bg-matrix-green/20 rounded-full blur-xl scale-150 opacity-0 group-hover/search:opacity-100 transition-opacity" />
                <Search className="text-matrix-green glow-matrix relative z-10 p-4 border-4 border-matrix-green/40 rounded-full bg-black hover:border-matrix-green transition-colors" size={84} strokeWidth={2.5} />
                <motion.div 
                  className="absolute -inset-4 border-2 border-matrix-green rounded-full opacity-20"
                  animate={{ scale: [1, 1.2, 1], opacity: [0.2, 0.4, 0.2] }}
                  transition={{ duration: 3, repeat: Infinity }}
                />
              </motion.div>

              <h2 className="text-xl font-black italic tracking-tighter text-matrix-green glow-matrix mb-4 uppercase">BUSQUEDA PRODUCTOS</h2>
              
              {/* Central "things to click" - Global Toggles */}
              <div className="grid grid-cols-2 gap-4 w-full h-24">
                 <button 
                    onClick={(e) => { 
                      e.stopPropagation(); 
                      soundService.playClick();
                      setStrictMode(!strictMode); 
                    }}
                    className={`flex flex-col items-center justify-center border-2 p-2 transition-all group
                      ${strictMode ? 'bg-matrix-green text-black border-matrix-green' : 'bg-black text-matrix-green border-matrix-green/30 hover:border-matrix-green'}`}
                 >
                    <div className={`w-4 h-4 rounded-full border-2 mb-1 flex items-center justify-center ${strictMode ? 'bg-black border-black' : 'border-matrix-green'}`}>
                      {strictMode && <div className="w-1.5 h-1.5 bg-matrix-green rounded-full" />}
                    </div>
                    <span className="text-[8px] font-black uppercase text-center leading-none">MODO_ESTRICTO</span>
                 </button>

                 <button 
                    onClick={(e) => { 
                      e.stopPropagation(); 
                      soundService.playClick();
                      setAntiNoise(!antiNoise); 
                    }}
                    className={`flex flex-col items-center justify-center border-2 p-2 transition-all group
                      ${antiNoise ? 'bg-matrix-green text-black border-matrix-green' : 'bg-black text-matrix-green border-matrix-green/30 hover:border-matrix-green'}`}
                 >
                    <div className={`w-4 h-4 rounded-full border-2 mb-1 flex items-center justify-center ${antiNoise ? 'bg-black border-black' : 'border-matrix-green'}`}>
                      {antiNoise && <div className="w-1.5 h-1.5 bg-matrix-green rounded-full" />}
                    </div>
                    <span className="text-[8px] font-black uppercase text-center leading-none">ANTI_RUIDO</span>
                 </button>
              </div>

              <button 
                onClick={onConfigClick}
                className="mt-4 w-full py-2 bg-matrix-green text-black font-black text-xs uppercase hover:bg-white transition-all shadow-[0_0_15px_rgba(51,255,102,0.3)] flex items-center justify-center gap-2"
              >
                <Settings2 size={14} strokeWidth={3} />
                MODIFICAR_FILTROS
              </button>
            </motion.div>
          ) : (
            <motion.div
              key="radar-mode"
              initial={{ scale: 0.5, opacity: 0, rotate: -45 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ scale: 0.5, opacity: 0, rotate: 45 }}
              transition={{ duration: 0.6, type: "spring" }}
            >
              <Radar />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Sound Toggle Button */}
      <div className="absolute top-10 right-10 z-50">
        <button 
          onClick={() => {
            soundService.playClick();
            setIsSoundEnabled(!isSoundEnabled);
          }}
          className={`flex items-center gap-2 px-3 py-1.5 border-2 transition-all font-black text-[10px] uppercase
            ${isSoundEnabled 
              ? 'bg-matrix-green text-black border-matrix-green shadow-[0_0_15px_rgba(51,255,102,0.3)]' 
              : 'bg-black text-matrix-green/40 border-matrix-green/20 hover:border-matrix-green hover:text-matrix-green'}`}
        >
          {isSoundEnabled ? <Volume2 size={14} strokeWidth={3} /> : <VolumeX size={14} strokeWidth={3} />}
          {isSoundEnabled ? 'AUDIO_ON' : 'AUDIO_OFF'}
        </button>
      </div>
    </div>
  );
}
