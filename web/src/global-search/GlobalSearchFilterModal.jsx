import { motion as Motion } from 'motion/react'
import { Save, Terminal as TerminalIcon, X } from 'lucide-react'
import GlobalSearchNodeIcon from './GlobalSearchNodeIcon'
import { soundService } from './soundService'

function Field({ label, children, wide = false }) {
  return (
    <label className={`${wide ? 'md:col-span-2' : ''} space-y-1`}>
      <span className="block text-[10px] font-black text-matrix-green/40 uppercase tracking-widest">{label}</span>
      {children}
    </label>
  )
}

function TextInput(props) {
  return <input {...props} className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none focus:bg-matrix-green/10" />
}

function SelectInput(props) {
  return <select {...props} className="w-full bg-black border-2 border-matrix-green p-2 text-xs font-black text-matrix-green outline-none uppercase" />
}

function Check({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 border-2 border-matrix-green p-2 cursor-pointer text-[10px] font-black uppercase text-matrix-green select-none hover:bg-matrix-green/5 transition-all">
      <input type="checkbox" className="hidden" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="w-4 h-4 border-2 border-matrix-green flex items-center justify-center">{checked && <span className="w-2 h-2 bg-matrix-green" />}</span>
      {label}
    </label>
  )
}

export default function GlobalSearchFilterModal({ node, globalForm, onGlobalChange, globalCategories, globalCategoriesLoading, onClose }) {
  const categories = globalCategories || {}
  const optionLabel = (category) => `${category.label}${category.count != null ? ` (${Number(category.count).toLocaleString('es-CL')})` : ''}`

  return (
    <Motion.div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <Motion.div
        className="w-full max-w-2xl border-4 border-matrix-green bg-black shadow-[0_0_50px_rgba(51,255,102,0.2)] overflow-hidden"
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        transition={{ type: 'spring', damping: 20 }}
      >
        <div className="bg-matrix-green text-black px-4 py-2 flex items-center justify-between font-black uppercase tracking-widest">
          <div className="flex items-center gap-3 min-w-0">
            <TerminalIcon size={18} strokeWidth={3} />
            <span className="truncate">CONFIGURACION_PROTOCOL_{node.id}</span>
          </div>
          <button onClick={() => { soundService.playClick(); onClose() }} className="hover:bg-black hover:text-matrix-green p-1 transition-all">
            <X size={20} strokeWidth={3} />
          </button>
        </div>
        <div className="p-8">
          <div className="flex items-center gap-4 mb-8 border-b-2 border-matrix-green/20 pb-4">
            <div className="p-3 bg-matrix-green/10 border-2 border-matrix-green">
              <GlobalSearchNodeIcon name={node.icon} size={32} strokeWidth={2.5} />
            </div>
            <div>
              <h2 className="text-2xl font-black text-matrix-green glow-matrix uppercase italic tracking-tighter">{node.name}</h2>
              <p className="text-[10px] text-matrix-green/40 font-black uppercase">LINK_STATUS: ENCRYPTED_STREAM</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {node.id === 'mercadolibre' && (
              <>
                <Field label="Pais">
                  <SelectInput value={globalForm.country} onChange={(e) => onGlobalChange('country', e.target.value)}>
                    <option value="cl">Chile</option><option value="ar">Argentina</option><option value="mx">Mexico</option><option value="co">Colombia</option><option value="pe">Peru</option>
                  </SelectInput>
                </Field>
                <Field label="Estado">
                  <SelectInput value={globalForm.mercadolibre_condition} onChange={(e) => onGlobalChange('mercadolibre_condition', e.target.value)}>
                    <option value="any">Cualquiera</option><option value="new">Nuevo</option><option value="used">Usado</option><option value="reconditioned">Reacondicionado</option>
                  </SelectInput>
                </Field>
                <Field label="Palabra obligatoria" wide><TextInput value={globalForm.mercadolibre_word} onChange={(e) => onGlobalChange('mercadolibre_word', e.target.value)} /></Field>
                <div className="flex flex-wrap gap-4 md:col-span-2 py-4">
                  <Check label="ORDENAR_POR_PRECIO" checked={globalForm.sort_price} onChange={(value) => onGlobalChange('sort_price', value)} />
                  <Check label="INCLUIR_INTL" checked={globalForm.include_international} onChange={(value) => onGlobalChange('include_international', value)} />
                </div>
                <details className="md:col-span-2 border-2 border-matrix-green p-3 text-matrix-green">
                  <summary className="cursor-pointer text-[10px] font-black uppercase tracking-widest">FILTROS_API_REALES</summary>
                  <div className="mt-4 grid grid-cols-1 gap-6">
                    <Field label="URL exacta" wide><TextInput value={globalForm.mercadolibre_search_url} onChange={(e) => onGlobalChange('mercadolibre_search_url', e.target.value)} /></Field>
                  </div>
                </details>
              </>
            )}
            {node.id === 'facebook' && (
              <>
                <Field label="Marketplace path"><TextInput value={globalForm.facebook_marketplace_path} onChange={(e) => onGlobalChange('facebook_marketplace_path', e.target.value)} /></Field>
                <Field label="Palabra obligatoria"><TextInput value={globalForm.facebook_word} onChange={(e) => onGlobalChange('facebook_word', e.target.value)} /></Field>
                <Field label="Ubicacion"><TextInput value={globalForm.facebook_location_query} onChange={(e) => onGlobalChange('facebook_location_query', e.target.value)} /></Field>
                <Field label="Radio km"><TextInput type="number" value={globalForm.facebook_radius_km} onChange={(e) => onGlobalChange('facebook_radius_km', Number(e.target.value || 1))} /></Field>
                <Field label="Latitud"><TextInput type="number" step="0.000001" value={globalForm.facebook_latitude ?? ''} onChange={(e) => onGlobalChange('facebook_latitude', Number(e.target.value || 0))} /></Field>
                <Field label="Longitud"><TextInput type="number" step="0.000001" value={globalForm.facebook_longitude ?? ''} onChange={(e) => onGlobalChange('facebook_longitude', Number(e.target.value || 0))} /></Field>
                <div className="md:col-span-2"><Check label="INCLUIR_TALCA" checked={globalForm.facebook_include_talca} onChange={(value) => onGlobalChange('facebook_include_talca', value)} /></div>
              </>
            )}
            {node.id === 'pulga' && (
              <>
                <Field label="Categoria">
                  <SelectInput value={globalForm.pulga_category} onChange={(e) => onGlobalChange('pulga_category', e.target.value)}>
                    <option value="">Todas las categorias</option>
                    {(categories.pulga || []).filter((c) => c.value).map((category) => <option key={category.value} value={category.value}>{category.label}</option>)}
                  </SelectInput>
                </Field>
                <Field label="Condicion">
                  <SelectInput value={globalForm.pulga_condition} onChange={(e) => onGlobalChange('pulga_condition', e.target.value)}>
                    <option value="any">Cualquiera</option><option value="new">Nuevo</option><option value="used">Usado</option>
                  </SelectInput>
                </Field>
                <Field label="Ciudad" wide><TextInput value={globalForm.pulga_city} onChange={(e) => onGlobalChange('pulga_city', e.target.value)} /></Field>
                <details className="md:col-span-2 border-2 border-matrix-green p-3 text-matrix-green">
                  <summary className="cursor-pointer text-[10px] font-black uppercase tracking-widest">FILTROS_API_REALES</summary>
                  <div className="mt-4 grid grid-cols-1 gap-6">
                    <Field label="Palabra obligatoria" wide><TextInput value={globalForm.pulga_word} onChange={(e) => onGlobalChange('pulga_word', e.target.value)} /></Field>
                  </div>
                </details>
              </>
            )}
            {node.id === 'knasta' && (
              <>
                <Field label="Categoria" wide>
                  <SelectInput value={globalForm.knasta_category} onChange={(e) => onGlobalChange('knasta_category', e.target.value)} disabled={globalCategoriesLoading}>
                    <option value="">{globalCategoriesLoading ? 'Cargando categorias...' : 'Todas las categorias'}</option>
                    {(categories.knasta || []).map((category) => <option key={category.value} value={category.value}>{optionLabel(category)}</option>)}
                  </SelectInput>
                </Field>
                <Field label="Retails (ej: paris, lider)" wide><TextInput placeholder="pcfactory, paris" value={globalForm.knasta_retails_text} onChange={(e) => onGlobalChange('knasta_retails_text', e.target.value)} /></Field>
                <details className="md:col-span-2 border-2 border-matrix-green p-3 text-matrix-green">
                  <summary className="cursor-pointer text-[10px] font-black uppercase tracking-widest">FILTROS_API_REALES</summary>
                  <div className="mt-4 grid grid-cols-1 gap-6">
                    <Field label="KnastaDay" wide><TextInput type="number" min="0" value={globalForm.knasta_knastaday} onChange={(e) => onGlobalChange('knasta_knastaday', Number(e.target.value || 0))} /></Field>
                  </div>
                </details>
              </>
            )}
            {node.id === 'solotodo' && (
              <>
                <Field label="Categoria ID">
                  <SelectInput value={String(globalForm.solotodo_category_id)} onChange={(e) => onGlobalChange('solotodo_category_id', Number(e.target.value || 0))} disabled={globalCategoriesLoading}>
                    <option value="0">{globalCategoriesLoading ? 'Cargando categorias...' : 'Todas'}</option>
                    {(categories.solotodo || []).map((category) => <option key={category.value} value={category.value}>{category.label}</option>)}
                  </SelectInput>
                </Field>
                <Field label="Pais ID"><TextInput type="number" value={globalForm.solotodo_country_id} onChange={(e) => onGlobalChange('solotodo_country_id', Number(e.target.value || 1))} /></Field>
                <Field label="Orden"><TextInput value={globalForm.solotodo_ordering} onChange={(e) => onGlobalChange('solotodo_ordering', e.target.value)} /></Field>
              </>
            )}
            {node.id === 'travel' && (
              <>
                <Field label="Categoria ID">
                  <SelectInput value={globalForm.travel_category_id} onChange={(e) => onGlobalChange('travel_category_id', e.target.value)} disabled={globalCategoriesLoading}>
                    <option value="">{globalCategoriesLoading ? 'Cargando categorias...' : 'Todas las categorias'}</option>
                    {(categories.travel || []).map((category) => <option key={category.value} value={category.value}>{'  '.repeat(Math.min(category.depth || 0, 4))}{category.label}</option>)}
                  </SelectInput>
                </Field>
                <Field label="Orden">
                  <SelectInput value={globalForm.travel_ordering} onChange={(e) => onGlobalChange('travel_ordering', e.target.value)}>
                    <option value="relevance">Relevancia</option><option value="price_asc">Precio ascendente</option><option value="price_desc">Precio descendente</option><option value="discount_desc">Descuento descendente</option><option value="name_asc">Nombre ascendente</option>
                  </SelectInput>
                </Field>
              </>
            )}
            {node.id === 'tuganga' && (
              <>
                <Field label="Modo">
                  <SelectInput value={globalForm.tuganga_mode} onChange={(e) => onGlobalChange('tuganga_mode', e.target.value)}>
                    <option value="search">Busqueda</option><option value="offers">Ofertas</option><option value="all_offers">Todas ofertas</option><option value="minimums">Minimos</option><option value="best">Mejores</option>
                  </SelectInput>
                </Field>
                <Field label="Tiendas"><TextInput placeholder="lider, ripley" value={globalForm.tuganga_stores_text} onChange={(e) => onGlobalChange('tuganga_stores_text', e.target.value)} /></Field>
                <Field label="Categoria" wide>
                  <SelectInput value={globalForm.tuganga_category} onChange={(e) => onGlobalChange('tuganga_category', e.target.value)} disabled={globalCategoriesLoading}>
                    <option value="">{globalCategoriesLoading ? 'Cargando categorias...' : 'Todas las categorias'}</option>
                    {(categories.tuganga || []).map((category) => <option key={category.value} value={category.value}>{optionLabel(category)}</option>)}
                  </SelectInput>
                </Field>
                <Field label="Orden"><TextInput value={globalForm.tuganga_sort} onChange={(e) => onGlobalChange('tuganga_sort', e.target.value)} /></Field>
                <div className="md:col-span-2"><Check label="SOLO_DISPONIBLES" checked={globalForm.tuganga_only_available} onChange={(value) => onGlobalChange('tuganga_only_available', value)} /></div>
              </>
            )}
            {node.id === 'rata' && (
              <>
                <Field label="Limite"><TextInput type="number" min="1" max="10000" value={globalForm.descuentosrata_limit} onChange={(e) => onGlobalChange('descuentosrata_limit', Number(e.target.value || 1))} /></Field>
                <div className="md:col-span-2"><Check label="TRAER_TODAS_OFERTAS" checked={globalForm.descuentosrata_all} onChange={(value) => onGlobalChange('descuentosrata_all', value)} /></div>
              </>
            )}
          </div>
          <div className="mt-12 flex justify-end gap-4">
            <button onClick={onClose} className="px-6 py-2 border-2 border-matrix-green/30 text-matrix-green/50 font-black uppercase text-xs hover:border-matrix-green hover:text-matrix-green transition-all">Cerrar</button>
            <button
              onClick={() => {
                soundService.playClick()
                onClose()
              }}
              className="px-8 py-2 bg-matrix-green text-black font-black uppercase text-xs hover:bg-white transition-all flex items-center gap-2 shadow-[0_0_15px_rgba(51,255,102,0.3)]"
            >
              <Save size={14} strokeWidth={3} />
              Guardar Protocolo
            </button>
          </div>
        </div>
      </Motion.div>
    </Motion.div>
  )
}

