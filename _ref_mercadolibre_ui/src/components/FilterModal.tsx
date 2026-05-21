import { motion, AnimatePresence } from 'motion/react';
import { X, Terminal as TerminalIcon, Save } from 'lucide-react';
import { Node } from '../constants';
import NodeIcon from './NodeIcon';
import { soundService } from '../services/soundService';

interface FilterModalProps {
  node: Node;
  onClose: () => void;
}

export default function FilterModal({ node, onClose }: FilterModalProps) {
  return (
    <motion.div 
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div 
        className="w-full max-w-2xl border-4 border-matrix-green bg-black shadow-[0_0_50px_rgba(51,255,102,0.2)] overflow-hidden"
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
      >
        {/* Modal Header */}
        <div className="bg-matrix-green text-black px-4 py-2 flex items-center justify-between font-black uppercase tracking-widest">
          <div className="flex items-center gap-3">
            <TerminalIcon size={18} strokeWidth={3} />
            <span>CONFIGURACION_PROTOCOL_{node.id}</span>
          </div>
          <button 
            onClick={() => {
              soundService.playClick();
              onClose();
            }}
            className="hover:bg-black hover:text-matrix-green p-1 transition-all"
          >
            <X size={20} strokeWidth={3} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-8">
          <div className="flex items-center gap-4 mb-8 border-b-2 border-matrix-green/20 pb-4">
            <div className="p-3 bg-matrix-green/10 border-2 border-matrix-green">
              <NodeIcon name={node.icon} size={32} strokeWidth={2.5} />
            </div>
            <div>
              <h2 className="text-2xl font-black text-matrix-green glow-matrix uppercase italic tracking-tighter">{node.name}</h2>
              <p className="text-[10px] text-matrix-green/40 font-black uppercase">LINK_STATUS: ENCRYPTED_STREAM</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {node.id === 'mercadolibre' && (
              <>
                <div className="space-y-1">
                  <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Pais</label>
                  <select className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none uppercase"><option>Chile</option></select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Estado</label>
                  <select className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none uppercase"><option>Nuevo</option></select>
                </div>
                <div className="md:col-span-2 space-y-1">
                  <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Palabra obligatoria</label>
                  <input type="text" className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none" />
                </div>
                <div className="flex gap-4 md:col-span-2 py-4">
                  <label className="flex items-center gap-2 border-2 border-matrix-green p-2 cursor-pointer text-[10px] font-black uppercase text-matrix-green select-none hover:bg-matrix-green/5 transition-all">
                    <input type="checkbox" className="hidden" />
                    <div className="w-4 h-4 border-2 border-matrix-green flex items-center justify-center"><div className="w-2 h-2 bg-matrix-green hidden" /></div>
                    ORDENAR_POR_PRECIO
                  </label>
                  <label className="flex items-center gap-2 border-2 border-matrix-green p-2 cursor-pointer text-[10px] font-black uppercase text-matrix-green select-none hover:bg-matrix-green/5 transition-all">
                    <input type="checkbox" className="hidden" />
                    <div className="w-4 h-4 border-2 border-matrix-green flex items-center justify-center"><div className="w-2 h-2 bg-matrix-green hidden" /></div>
                    INCLUIR_INTL
                  </label>
                </div>
              </>
            )}

            {node.id === 'pulga' && (
              <>
                <div className="space-y-1">
                  <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Categoria</label>
                  <select className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none uppercase"><option>Tecnologia</option></select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Condicion</label>
                  <select className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none uppercase"><option>Cualquiera</option></select>
                </div>
                <div className="md:col-span-2 space-y-1">
                  <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Ciudad</label>
                  <input type="text" className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none" />
                </div>
              </>
            )}

            {node.id === 'knasta' && (
              <>
                <div className="space-y-1 md:col-span-2">
                  <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Categoria</label>
                  <select className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none uppercase"><option>Tecnología (3.903)</option></select>
                </div>
                <div className="space-y-1 md:col-span-2">
                  <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">Retails (ej: paris, lider)</label>
                  <input type="text" className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none" />
                </div>
              </>
            )}

            {!(node.id === 'mercadolibre' || node.id === 'pulga' || node.id === 'knasta') && (
              <div className="md:col-span-2 p-12 text-center">
                <p className="text-matrix-green/20 font-black uppercase italic text-sm">NO_ADDITIONAL_FILTERS_REQUIRED_FOR_THIS_TERMINAL</p>
              </div>
            )}
          </div>

          {/* Footer Controls */}
          <div className="mt-12 flex justify-end gap-4">
            <button 
              onClick={onClose}
              className="px-6 py-2 border-2 border-matrix-green/30 text-matrix-green/50 font-black uppercase text-xs hover:border-matrix-green hover:text-matrix-green transition-all"
            >
              Cerrar
            </button>
            <button 
              onClick={() => {
                soundService.playClick();
                onClose();
              }}
              className="px-8 py-2 bg-matrix-green text-black font-black uppercase text-xs hover:bg-white transition-all flex items-center gap-2 shadow-[0_0_15px_rgba(51,255,102,0.3)]"
            >
              <Save size={14} strokeWidth={3} />
              Guardar Protocolo
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
