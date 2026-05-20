import { Search } from 'lucide-react'
import GlobalSearchNodeIcon from './GlobalSearchNodeIcon'
import { getRunForNode, isNodeActive } from './globalSearchNodes'
import { soundService } from './soundService'

function Field({ label, children }) {
  return (
    <label className="space-y-1">
      <span className="block text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">{label}</span>
      {children}
    </label>
  )
}

function MatrixInput(props) {
  return <input {...props} className="w-full bg-black border-2 border-matrix-green p-2 text-sm font-black text-matrix-green outline-none focus:bg-matrix-green/10" />
}

export default function GlobalSearchMatrix({ nodes, globalForm, onGlobalChange, toggleGlobalSource, onStartProcess, globalResult, canGlobalSubmit, globalLoading }) {
  const runs = globalResult?.runs || []

  return (
    <div className="flex flex-col gap-8 w-full pb-20">
      <section className="border-2 border-matrix-green bg-black">
        <div className="bg-matrix-green/20 text-matrix-green px-2 py-0.5 text-[9px] font-black uppercase tracking-widest border-b-2 border-matrix-green">TARGET_NODE_SELECTION</div>
        <div className="p-3 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
          {nodes.map((node) => {
            const active = isNodeActive(node, globalForm.sources)
            const run = getRunForNode(node, runs)
            return (
              <button
                type="button"
                key={node.id}
                onClick={() => {
                  soundService.playClick()
                  toggleGlobalSource(node.sourceKey)
                }}
                className={`flex flex-col items-center justify-center gap-2 p-3 border-2 cursor-pointer transition-all relative overflow-hidden group ${active ? 'border-matrix-green bg-matrix-green/10 text-matrix-green font-black shadow-[inset_0_0_10px_rgba(51,255,102,0.1)]' : 'border-matrix-green/10 bg-black text-matrix-green/30 hover:bg-matrix-green/5 hover:border-matrix-green/30'}`}
              >
                <div className="relative">
                  <GlobalSearchNodeIcon name={node.icon} size={24} strokeWidth={2.5} />
                  <div className={`absolute -top-1 -right-1 w-3 h-3 border-2 flex items-center justify-center transition-all ${active ? 'border-matrix-green bg-matrix-green' : 'border-matrix-green/20 bg-black'}`}>{active && <div className="w-1 h-1 bg-black" />}</div>
                </div>
                <span className="text-[9px] font-black uppercase truncate tracking-wider leading-none text-center">{node.name}</span>
                {run && <div className="absolute top-1 left-1 bg-black text-matrix-green text-[7px] font-black px-1 border border-matrix-green/40">{run.count ?? 0}</div>}
              </button>
            )
          })}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6">
        <div className="border-2 border-matrix-green bg-black relative shadow-[0_0_20px_rgba(51,255,102,0.05)]">
          <div className="bg-matrix-green text-black px-4 py-1 flex items-center justify-between">
            <h3 className="text-[10px] font-black uppercase tracking-[0.3em]">GLOBAL_PARAMETERS</h3>
          </div>
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <Field label="Busqueda unica">
              <MatrixInput value={globalForm.query} onChange={(e) => onGlobalChange('query', e.target.value)} />
            </Field>
            <Field label="Alcance">
              <select value={globalForm.scan_scope} onChange={(e) => onGlobalChange('scan_scope', e.target.value)} className="w-full bg-black border-2 border-matrix-green p-2 text-sm font-black text-matrix-green outline-none italic uppercase">
                <option value="fast">Rapido</option>
                <option value="complete">Completo</option>
              </select>
            </Field>
            <Field label="Tope por fuente">
              <MatrixInput type="number" min="1" max="10000" value={globalForm.max_items_per_source} onChange={(e) => onGlobalChange('max_items_per_source', Number(e.target.value || 1))} />
            </Field>
            <Field label="Precio minimo">
              <MatrixInput type="number" value={globalForm.min_price} onChange={(e) => onGlobalChange('min_price', Number(e.target.value || 0))} />
            </Field>
            <Field label="Precio maximo">
              <MatrixInput type="number" value={globalForm.max_price} onChange={(e) => onGlobalChange('max_price', Number(e.target.value || 0))} />
            </Field>
            <Field label="Descuento minimo">
              <MatrixInput type="number" min="0" max="100" value={globalForm.min_discount} onChange={(e) => onGlobalChange('min_discount', Number(e.target.value || 0))} />
            </Field>
            <Field label="Incluir palabras">
              <MatrixInput placeholder="gamer, ips" value={globalForm.include_words_text} onChange={(e) => onGlobalChange('include_words_text', e.target.value)} />
            </Field>
            <Field label="Excluir palabras">
              <MatrixInput placeholder="repuesto, carcasa" value={globalForm.exclude_words_text} onChange={(e) => onGlobalChange('exclude_words_text', e.target.value)} />
            </Field>
          </div>
          <div className="flex flex-col sm:flex-row gap-4 sm:gap-8 px-4 pb-4">
            <button type="button" onClick={() => { soundService.playClick(); onGlobalChange('strict_mode', !globalForm.strict_mode) }} className="flex items-center gap-3 cursor-pointer group outline-none">
              <div className={`w-4 h-4 border-2 flex items-center justify-center transition-all ${globalForm.strict_mode ? 'border-matrix-green bg-matrix-green' : 'border-matrix-green/30 bg-black'}`}>{globalForm.strict_mode && <div className="w-1.5 h-1.5 bg-black" />}</div>
              <span className={`text-[10px] font-black transition-all uppercase tracking-widest ${globalForm.strict_mode ? 'text-matrix-green glow-matrix' : 'text-matrix-green/40'}`}>Modo estricto</span>
            </button>
            <button type="button" onClick={() => { soundService.playClick(); onGlobalChange('smart_filter', !globalForm.smart_filter) }} className="flex items-center gap-3 cursor-pointer group outline-none">
              <div className={`w-4 h-4 border-2 flex items-center justify-center transition-all ${globalForm.smart_filter ? 'border-matrix-green bg-matrix-green' : 'border-matrix-green/30 bg-black'}`}>{globalForm.smart_filter && <div className="w-1.5 h-1.5 bg-black" />}</div>
              <span className={`text-[10px] font-black transition-all uppercase tracking-widest ${globalForm.smart_filter ? 'text-matrix-green glow-matrix' : 'text-matrix-green/40'}`}>Filtro anti-basura</span>
            </button>
          </div>
          <div className="p-4 border-t border-matrix-green/20 flex justify-end">
            <button type="button" disabled={!canGlobalSubmit || globalLoading} onClick={onStartProcess} className="px-8 py-3 bg-matrix-green text-black font-black uppercase text-xs hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2 shadow-[0_0_15px_rgba(51,255,102,0.3)]">
              <Search size={16} strokeWidth={3} />
              {globalLoading ? 'ESCANEANDO...' : 'EJECUTAR_TODAS'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
