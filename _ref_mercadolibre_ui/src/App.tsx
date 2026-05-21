import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import Navbar from './components/Navbar';
import HUD from './components/HUD';
import MatrixCore from './components/MatrixCore';
import Terminal from './components/Terminal';
import ResultsModal from './components/ResultsModal';
import { ChevronLeft, Play, Download, Settings2, Database } from 'lucide-react';
import { NODES as INITIAL_NODES } from './constants';
import { soundService } from './services/soundService';

type ViewMode = 'HUD' | 'MATRIX';

export interface HistoryEntry {
  id: string;
  timestamp: string;
  results: Record<string, number>;
  totalItems: number;
  selectedNodesCount: number;
  strictMode: boolean;
  antiNoise: boolean;
}

export default function App() {
  const [view, setView] = useState<ViewMode>('HUD');
  const [nodes, setNodes] = useState(INITIAL_NODES);
  const [isProcessing, setIsProcessing] = useState(false);
  const [useStrictMode, setUseStrictMode] = useState(false);
  const [useAntiNoise, setUseAntiNoise] = useState(true);
  const [progress, setProgress] = useState(0);
  const [isSoundEnabled, setIsSoundEnabled] = useState(soundService.enabled);
  const [scanResults, setScanResults] = useState<Record<string, number>>({});
  const [showResultsModal, setShowResultsModal] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    soundService.setEnabled(isSoundEnabled);
  }, [isSoundEnabled]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isProcessing && progress < 100) {
      interval = setInterval(() => {
        setProgress(prev => {
          const next = prev + Math.random() * 5;
          return next >= 100 ? 100 : next;
        });
      }, 300);
    } else if (isProcessing && progress >= 100) {
      // Simulation: generate results for active nodes
      const results: Record<string, number> = {};
      nodes.forEach(node => {
        if (node.active) {
          results[node.id] = Math.floor(Math.random() * 150) + 10;
        }
      });
      setScanResults(results);
      setShowResultsModal(true);

      // Save to Active Session History
      const totalItems = Object.values(results).reduce((a, b) => a + b, 0);
      const newEntry: HistoryEntry = {
        id: `SCAN_${Math.random().toString(36).substring(7).toUpperCase()}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        results,
        totalItems,
        selectedNodesCount: Object.keys(results).length,
        strictMode: useStrictMode,
        antiNoise: useAntiNoise
      };
      setHistory(prev => [newEntry, ...prev]);

      // Complete scanning state transition safely
      setIsProcessing(false);
      setProgress(0);
    }
    return () => clearInterval(interval);
  }, [isProcessing, progress, nodes, useStrictMode, useAntiNoise]);

  const toggleNode = (nodeId: string) => {
    soundService.playClick();
    setNodes(prev => prev.map(node => 
      node.id === nodeId ? { ...node, active: !node.active } : node
    ));
  };

  const handleStartProcess = () => {
    soundService.playScan();
    setScanResults({});
    setProgress(0);
    setIsProcessing(true);
  };

  const handleStopProcess = () => {
    soundService.playError();
    setIsProcessing(false);
    setProgress(0);
  };

  const handleClearHistory = () => {
    soundService.playClick();
    setHistory([]);
  };

  const handleViewHistoryItem = (entry: HistoryEntry) => {
    soundService.playOpen();
    setScanResults(entry.results);
    setShowResultsModal(true);
  };

  const handleExportEntry = (entry: HistoryEntry) => {
    soundService.playClick();
    const activeNodesWithResults = nodes.filter(n => entry.results[n.id] !== undefined);
    const exportData = {
      timestamp: new Date().toISOString(),
      summary: {
        total_stores_scanned: activeNodesWithResults.length,
        total_items_found: entry.totalItems
      },
      results: activeNodesWithResults.map(node => ({
        store_id: node.id,
        store_name: node.name,
        quantity: entry.results[node.id],
        simulated_products: Array.from({ length: 3 }, (_, i) => ({
          sku: `${node.id.toUpperCase()}_${i}`,
          label: `Product Alpha ${i} - ${node.name}`,
          price: Math.floor(Math.random() * 800000)
        }))
      }))
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `RADAR_GLOBAL_EXPORT_${entry.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-[#020502] flex items-center justify-center">
      <div className="crt-screen w-full h-screen flex flex-col relative overflow-hidden">
        <div className="scanline-anim" />
        
        <div className="screen-container flex-1 flex flex-col relative z-20">
          <Navbar />

          <main className="relative z-10 flex-1 flex flex-col lg:flex-row overflow-hidden pb-16">
            {/* History Panel */}
            <div className="w-full lg:w-80 shrink-0 border-b-2 lg:border-b-0 lg:border-r-2 border-matrix-green/20 bg-black/40 backdrop-blur-md p-4 flex flex-col gap-4 font-mono overflow-y-auto max-h-[35vh] lg:max-h-full">
              <div className="flex items-center justify-between border-b border-matrix-green/30 pb-2 shrink-0">
                <div className="flex items-center gap-2 text-matrix-green text-[10px] font-black uppercase tracking-widest">
                  <Database size={12} />
                  <span>HISTORIAL_SESION</span>
                </div>
                <span className="text-[8px] bg-matrix-green/10 text-matrix-green px-1 border border-matrix-green/30 uppercase font-black animate-pulse">SESION_OK</span>
              </div>

              {history.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-matrix-green/10 text-matrix-green/30 self-center w-full min-h-[100px] justify-center">
                  <span className="text-[9px] uppercase font-black tracking-widest leading-relaxed text-matrix-green/40">SIN REGISTROS</span>
                  <span className="text-[8px] mt-1 text-center opacity-60">realice un escaneo para almacenar resultados</span>
                </div>
              ) : (
                <>
                  <div className="flex-1 space-y-3 overflow-y-auto pr-1">
                    {history.map((entry, idx) => (
                      <div 
                        key={entry.id}
                        className="border border-matrix-green/20 p-2.5 flex flex-col gap-1.5 hover:bg-matrix-green/5 transition-all group relative cursor-pointer"
                        onClick={() => handleViewHistoryItem(entry)}
                      >
                        <div className="flex items-center justify-between text-[9px] font-black">
                          <span className="text-matrix-green uppercase">LOG_#{history.length - idx}</span>
                          <span className="text-matrix-green/40">{entry.timestamp}</span>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-1 text-[9px] tracking-tight">
                          <div>
                            <span className="text-matrix-green/40">TIENDAS:</span>{' '}
                            <span className="font-black text-matrix-green">{entry.selectedNodesCount}</span>
                          </div>
                          <div>
                            <span className="text-matrix-green/40">TOTAL:</span>{' '}
                            <span className="font-black text-matrix-green">{entry.totalItems}</span>
                          </div>
                        </div>

                        <div className="flex gap-2 text-[8px] font-bold text-matrix-green/30 uppercase leading-none">
                          <span>{entry.strictMode ? 'ESTRICTO' : 'NORMAL'}</span>
                          <span>•</span>
                          <span>{entry.antiNoise ? 'ANTI-RUIDO' : 'SIN FILTRO'}</span>
                        </div>

                        <div className="flex gap-1.5 mt-1 pt-1.5 border-t border-matrix-green/10">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleViewHistoryItem(entry);
                            }}
                            className="flex-1 py-1 border border-matrix-green/40 text-matrix-green bg-black hover:bg-matrix-green hover:text-black font-black text-[8px] uppercase tracking-widest transition-all text-center"
                          >
                            VER_LOG
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExportEntry(entry);
                            }}
                            className="px-2 py-1 border border-matrix-green/30 text-matrix-green/60 hover:text-matrix-green hover:border-matrix-green hover:bg-matrix-green/5 font-black text-[8px] uppercase transition-all flex items-center justify-center"
                            title="Exportar JSON"
                          >
                            <Download size={10} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={handleClearHistory}
                    className="w-full py-2 bg-red-950/20 text-red-500 hover:bg-red-500 hover:text-black border border-red-500/30 hover:border-red-500 transition-all text-[9.5px] font-black uppercase tracking-widest shrink-0"
                  >
                    LIMPIAR HISTORIAL
                  </button>
                </>
              )}
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-y-auto">
              <AnimatePresence mode="wait">
                {view === 'HUD' ? (
                  <motion.div
                    key="hud"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    <HUD 
                      nodes={nodes}
                      onSelectNode={toggleNode} 
                      onStartProcess={handleStartProcess}
                      onConfigClick={() => {
                        soundService.playOpen();
                        setView('MATRIX');
                      }}
                      isProcessing={isProcessing}
                      strictMode={useStrictMode}
                      setStrictMode={setUseStrictMode}
                      antiNoise={useAntiNoise}
                      setAntiNoise={setUseAntiNoise}
                      isSoundEnabled={isSoundEnabled}
                      setIsSoundEnabled={setIsSoundEnabled}
                      scanResults={scanResults}
                    />
                  </motion.div>
                ) : (
                  <motion.div
                    key="matrix"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="relative p-6"
                  >
                    <div className="max-w-[1400px] mx-auto mb-6 flex items-center justify-between bg-matrix-green px-4 py-1 text-black font-bold">
                      <button 
                        onClick={() => {
                          soundService.playClick();
                          setView('HUD');
                        }}
                        className="flex items-center gap-2 text-xs font-mono tracking-widest uppercase hover:opacity-80 transition-all font-black"
                      >
                        <ChevronLeft size={16} strokeWidth={3} />
                        RETORNO_A_HUB
                      </button>
                    </div>
                    <MatrixCore 
                      nodes={nodes}
                      setNodes={setNodes}
                      onStartProcess={handleStartProcess}
                      strictMode={useStrictMode}
                      setStrictMode={setUseStrictMode}
                      antiNoise={useAntiNoise}
                      setAntiNoise={setUseAntiNoise}
                      scanResults={scanResults}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </main>

          {isProcessing && (
            <Terminal progress={progress} onStop={handleStopProcess} />
          )}

          <AnimatePresence>
            {showResultsModal && (
              <ResultsModal 
                nodes={nodes}
                scanResults={scanResults}
                onClose={() => {
                  setShowResultsModal(false);
                  setScanResults({});
                }}
              />
            )}
          </AnimatePresence>
        </div>
        
        {/* Subtle Glow Overlay */}
        <div className="absolute inset-0 pointer-events-none z-[110] bg-[radial-gradient(circle_at_center,_rgba(51,255,102,0.05)_0%,_transparent_70%)]" />
      </div>
    </div>
  );
}
