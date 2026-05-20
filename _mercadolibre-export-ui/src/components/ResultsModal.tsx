import { motion, AnimatePresence } from 'motion/react';
import { X, Terminal as TerminalIcon, Download, Database, CheckCircle2 } from 'lucide-react';
import { Node } from '../constants';
import { soundService } from '../services/soundService';

interface ResultsModalProps {
  nodes: Node[];
  scanResults: Record<string, number>;
  onClose: () => void;
}

export default function ResultsModal({ nodes, scanResults, onClose }: ResultsModalProps) {
  const activeNodesWithResults = nodes.filter(n => scanResults[n.id] !== undefined);
  const totalFound = Object.values(scanResults).reduce((a, b) => a + b, 0);

  const handleGlobalExport = () => {
    soundService.playClick();
    const exportData = {
      timestamp: new Date().toISOString(),
      summary: {
        total_stores_scanned: activeNodesWithResults.length,
        total_items_found: totalFound
      },
      results: activeNodesWithResults.map(node => ({
        store_id: node.id,
        store_name: node.name,
        quantity: scanResults[node.id],
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
    a.download = `RADAR_GLOBAL_EXPORT_${new Date().getTime()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <motion.div 
      className="fixed inset-0 z-[300] flex items-center justify-center p-4 bg-black/90 backdrop-blur-md"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div 
        className="w-full max-w-4xl border-4 border-matrix-green bg-black shadow-[0_0_100px_rgba(51,255,102,0.3)] overflow-hidden flex flex-col max-h-[80vh]"
        initial={{ scale: 0.8, rotateX: 20 }}
        animate={{ scale: 1, rotateX: 0 }}
        exit={{ scale: 0.8, rotateX: 20 }}
        transition={{ type: "spring", damping: 20 }}
      >
        {/* Terminal Header */}
        <div className="bg-matrix-green text-black px-4 py-2 flex items-center justify-between font-black uppercase tracking-[0.2em] shrink-0">
          <div className="flex items-center gap-3">
            <TerminalIcon size={20} strokeWidth={3} />
            <span className="text-sm">REPORT_TERMINAL_OUT // SCAN_COMPLETE</span>
          </div>
          <button 
            onClick={() => {
              soundService.playClick();
              onClose();
            }}
            className="hover:bg-black hover:text-matrix-green p-1 transition-all"
          >
            <X size={24} strokeWidth={3} />
          </button>
        </div>

        {/* Terminal Body */}
        <div className="flex-1 overflow-y-auto p-8 font-mono space-y-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between border-b-2 border-matrix-green/30 pb-6 gap-4">
            <div>
              <h2 className="text-4xl font-black text-matrix-green glow-matrix uppercase italic tracking-tighter mb-2">RESULTADOS_ENCONTRADOS</h2>
              <div className="flex gap-4 text-[10px] font-black uppercase text-matrix-green/40">
                <span>SESION_ID: {Math.random().toString(36).substring(7).toUpperCase()}</span>
                <span>|</span>
                <span>STATUS: OPERATIVO</span>
              </div>
            </div>
            <div className="flex flex-col items-end">
              <span className="text-5xl font-black text-matrix-green tabular-nums">{totalFound}</span>
              <span className="text-[10px] font-black uppercase text-matrix-green/60 tracking-[0.3em]">TOTAL_ITEMS_DETECTADOS</span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-matrix-green border-collapse">
              <thead>
                <tr className="border-b border-matrix-green/20 text-[10px] font-black uppercase tracking-widest bg-matrix-green/5">
                  <th className="p-4">RECURSO_ORIGEN</th>
                  <th className="p-4">CAPACIDAD_CANAL</th>
                  <th className="p-4 text-right">ITEMS_LOCALIZADOS</th>
                  <th className="p-4 text-right">ESTADO_FLUJO</th>
                </tr>
              </thead>
              <tbody>
                {activeNodesWithResults.map((node) => (
                  <tr key={node.id} className="border-b border-matrix-green/10 hover:bg-matrix-green/5 transition-all text-sm group">
                    <td className="p-4 flex items-center gap-3">
                      <div className="w-8 h-8 border border-matrix-green/30 flex items-center justify-center bg-black">
                        <Database size={14} className="opacity-50" />
                      </div>
                      <span className="font-black uppercase tracking-tighter">{node.name}</span>
                    </td>
                    <td className="p-4 opacity-50 text-[10px]">98.2%_EFFICIENCY</td>
                    <td className="p-4 text-right text-xl font-black">{scanResults[node.id]}</td>
                    <td className="p-4 text-right">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 border border-matrix-green bg-matrix-green/10 text-[9px] font-black uppercase">
                        <span className="w-1.5 h-1.5 rounded-full bg-matrix-green animate-pulse" />
                        SYNCED
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-6 bg-matrix-green/5 border border-matrix-green/20 space-y-4">
             <p className="text-[10px] text-matrix-green/40 uppercase leading-relaxed">
               El motor de búsqueda ha finalizado la indexación de los nodos seleccionados. Se han filtrado los resultados según los parámetros globales establecidos en el núcleo del Radar Comercial. El paquete completo de datos está listo para ser extraído.
             </p>
             <div className="flex items-center gap-2 text-matrix-green">
               <CheckCircle2 size={14} />
               <span className="text-[10px] font-black uppercase tracking-widest">VERIFICACION_DE_INTEGRIDAD: PASADA</span>
             </div>
          </div>
        </div>

        {/* Terminal Footer */}
        <div className="p-8 border-t-2 border-matrix-green/20 shrink-0 flex flex-col sm:flex-row justify-end gap-4 bg-black/50">
          <button 
            onClick={() => {
              soundService.playClick();
              onClose();
            }}
            className="px-8 py-3 border-2 border-matrix-green/40 text-matrix-green/60 font-black uppercase tracking-widest hover:border-matrix-green hover:text-matrix-green transition-all"
          >
            Regresar_Al_Radar
          </button>
          <button 
            onClick={handleGlobalExport}
            className="px-10 py-3 bg-matrix-green text-black font-black uppercase tracking-widest hover:bg-white transition-all shadow-[0_0_30px_rgba(51,255,102,0.4)] flex items-center justify-center gap-3 scale-105"
          >
            <Download size={20} strokeWidth={3} />
            EXPORTAR_JSON_GLOBAL
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
