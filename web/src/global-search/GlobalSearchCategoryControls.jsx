import { soundService } from './soundService'

export default function GlobalSearchCategoryControls({
  globalForm,
  onGlobalChange,
  categorySuggestion,
  globalCategoriesLoading,
  onResetAllCategories,
  onReapplyCategorySuggestions,
  compact = false,
}) {
  const labels = categorySuggestion?.labels || {}
  const hasQuery = Boolean(globalForm.query?.trim())
  const labelEntries = Object.entries(labels).filter(([, name]) => name && name !== 'Todas')

  if (!hasQuery && !globalForm.auto_categories) return null

  return (
    <div className={`w-full flex flex-col gap-1.5 ${compact ? '' : 'mt-1'}`}>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          onClick={() => {
            soundService.playClick()
            const next = !globalForm.auto_categories
            onGlobalChange('auto_categories', next)
            if (next) onReapplyCategorySuggestions?.()
          }}
          className={`px-2 py-1 border text-[8px] font-black uppercase tracking-wider transition-all ${globalForm.auto_categories ? 'bg-matrix-green text-black border-matrix-green' : 'bg-black text-matrix-green/50 border-matrix-green/30 hover:border-matrix-green'}`}
        >
          AUTO_CATEGORIAS: {globalForm.auto_categories ? 'ON' : 'OFF'}
        </button>
        <button
          type="button"
          onClick={() => {
            soundService.playClick()
            onResetAllCategories?.()
          }}
          className="px-2 py-1 border border-matrix-green/30 text-matrix-green/60 hover:text-matrix-green hover:border-matrix-green text-[8px] font-black uppercase tracking-wider transition-all"
        >
          TODAS_LAS_CATEGORIAS
        </button>
      </div>
      {globalCategoriesLoading && hasQuery && (
        <span className="text-[8px] font-mono text-matrix-green/40 uppercase text-center tracking-wider">Calculando categorias...</span>
      )}
      {!globalCategoriesLoading && hasQuery && globalForm.auto_categories && labelEntries.length > 0 && (
        <span className="text-[7.5px] font-mono text-matrix-green/50 uppercase text-center tracking-wide leading-relaxed px-1">
          Sugerido: {labelEntries.map(([src, name]) => `${src}=${name}`).join(' · ')}
        </span>
      )}
      {!globalCategoriesLoading && hasQuery && globalForm.auto_categories && labelEntries.length === 0 && (
        <span className="text-[7.5px] font-mono text-matrix-green/40 uppercase text-center tracking-wide">
          Sin categoria especifica (maximo volumen)
        </span>
      )}
      {hasQuery && !globalForm.auto_categories && (
        <span className="text-[7.5px] font-mono text-matrix-green/35 uppercase text-center tracking-wide">
          Categorias manuales activas
        </span>
      )}
    </div>
  )
}
