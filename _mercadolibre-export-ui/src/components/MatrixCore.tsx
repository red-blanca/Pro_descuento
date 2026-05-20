import React from 'react';
import { Search } from 'lucide-react';
import { Node } from '../constants';
import NodeIcon from './NodeIcon';
import { soundService } from '../services/soundService';

interface MatrixCoreProps {
  nodes: Node[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  onStartProcess: () => void;
  strictMode: boolean;
  setStrictMode: (val: boolean) => void;
  antiNoise: boolean;
  setAntiNoise: (val: boolean) => void;
  scanResults: Record<string, number>;
}

export default function MatrixCore({ 
  nodes,
  setNodes,
  onStartProcess,
  strictMode,
  setStrictMode,
  antiNoise,
  setAntiNoise,
  scanResults
}: MatrixCoreProps) {

  const toggleNode = (nodeId: string) => {
    setNodes(prev => prev.map(node => 
      node.id === nodeId ? { ...node, active: !node.active } : node
    ));
  };

  const hasResults = Object.keys(scanResults).length > 0;

  return (
    <div className="flex flex-col gap-8 w-full pb-20">
      {/* Target Nodes Grid */}
      <section className="border-2 border-matrix-green bg-black">
        <div className="bg-matrix-green/20 text-matrix-green px-2 py-0.5 text-[9px] font-black uppercase tracking-widest border-b-2 border-matrix-green">TARGET_NODE_SELECTION</div>
        <div className="p-3 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
          {nodes.map(node => {
            const count = scanResults[node.id];
            return (
              <div 
                key={node.id} 
                onClick={() => {
                  soundService.playClick();
                  toggleNode(node.id);
                }}
                className={`flex flex-col items-center justify-center gap-2 p-3 border-2 cursor-pointer transition-all relative overflow-hidden group
                  ${node.active 
                    ? 'border-matrix-green bg-matrix-green/10 text-matrix-green font-black shadow-[inset_0_0_10px_rgba(51,255,102,0.1)]' 
                    : 'border-matrix-green/10 bg-black text-matrix-green/30 hover:bg-matrix-green/5 hover:border-matrix-green/30'}`}
              >
                <div className="relative">
                  <NodeIcon name={node.icon} size={24} strokeWidth={2.5} />
                  <div className={`absolute -top-1 -right-1 w-3 h-3 border-2 flex items-center justify-center transition-all ${node.active ? 'border-matrix-green bg-matrix-green' : 'border-matrix-green/20 bg-black'}`}>
                     {node.active && <div className="w-1 h-1 bg-black" />}
                  </div>
                </div>
                <span className="text-[9px] font-black uppercase truncate tracking-wider leading-none text-center">
                  {node.name}
                </span>

                {count !== undefined && (
                  <div className="absolute top-1 left-1 bg-black text-matrix-green text-[7px] font-black px-1 border border-matrix-green/40">
                    {count}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Top HUD Stats (Parameters) */}
      <div className="grid grid-cols-1 gap-6">
        <div className="border-2 border-matrix-green bg-black relative shadow-[0_0_20px_rgba(51,255,102,0.05)]">
          <div className="bg-matrix-green text-black px-4 py-1 flex items-center justify-between">
            <h3 className="text-[10px] font-black uppercase tracking-[0.3em]">GLOBAL_PARAMETERS</h3>
          </div>
          <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Busqueda única (ej: notebook)', value: 'notebook' },
              { label: 'Alcance', type: 'select', options: ['Completo', 'Sector 07'] },
              { label: 'Tope por fuente', value: '10000', type: 'number' },
              { label: 'Precio mínimo', value: '0', type: 'number' },
              { label: 'Precio máximo', value: '0', type: 'number' },
              { label: 'Descuento mínimo', value: '0', type: 'number' },
              { label: 'Incluir palabras (ej: tarjetas)', value: 'gamer, ips' },
              { label: 'Excluir palabras', value: 'repuesto, carcasa' },
            ].map((field, i) => (
              <div key={i} className="space-y-1">
                <label className="text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">{field.label}</label>
                {field.type === 'select' ? (
                  <select className="w-full bg-black border-2 border-matrix-green p-2 text-sm font-black text-matrix-green outline-none italic uppercase">
                    {field.options?.map(o => <option key={o}>{o}</option>)}
                  </select>
                ) : (
                  <input 
                    type={field.type || 'text'} 
                    defaultValue={field.value}
                    className="w-full bg-black border-2 border-matrix-green p-2 text-sm font-black text-matrix-green outline-none focus:bg-matrix-green/10"
                  />
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-8 px-4 pb-4">
            <button 
              onClick={() => {
                soundService.playClick();
                setStrictMode(!strictMode);
              }}
              className="flex items-center gap-3 cursor-pointer group outline-none"
            >
              <div className={`w-4 h-4 border-2 flex items-center justify-center transition-all ${strictMode ? 'border-matrix-green bg-matrix-green' : 'border-matrix-green/30 bg-black'}`}>
                {strictMode && <div className="w-1.5 h-1.5 bg-black" />}
              </div>
              <span className={`text-[10px] font-black transition-all uppercase tracking-widest ${strictMode ? 'text-matrix-green glow-matrix' : 'text-matrix-green/40'}`}>Modo estricto</span>
            </button>
            <button 
              onClick={() => {
                soundService.playClick();
                setAntiNoise(!antiNoise);
              }}
              className="flex items-center gap-3 cursor-pointer group outline-none"
            >
              <div className={`w-4 h-4 border-2 flex items-center justify-center transition-all ${antiNoise ? 'border-matrix-green bg-matrix-green' : 'border-matrix-green/30 bg-black'}`}>
                {antiNoise && <div className="w-1.5 h-1.5 bg-black" />}
              </div>
              <span className={`text-[10px] font-black transition-all uppercase tracking-widest ${antiNoise ? 'text-matrix-green glow-matrix' : 'text-matrix-green/40'}`}>Filtro anti-basura</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
