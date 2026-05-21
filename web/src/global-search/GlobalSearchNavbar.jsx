import { CheckCircle2, Cookie, Terminal as TerminalIcon } from 'lucide-react'
import { soundService } from './soundService'

function MercadoLibreBadge({ health }) {
  const ok = health?.color === 'green'
  return (
    <div className={`flex items-center gap-2 px-3 py-1 bg-black border ${ok ? 'text-matrix-green border-matrix-green shadow-[0_0_10px_rgba(51,255,102,0.2)]' : 'text-[#ff3333] border-[#ff3333] shadow-[0_0_10px_rgba(255,51,51,0.2)]'}`}>
      {ok ? <CheckCircle2 size={12} /> : <span className="w-1.5 h-1.5 bg-[#ff3333] animate-pulse shadow-[0_0_5px_#ff3333]" />}
      {ok ? 'COOKIES OK (ML)' : 'SIN COOKIES (ML)'}
    </div>
  )
}

export default function GlobalSearchNavbar({ cookieHealth, facebookCookieHealth, onOpenCookieModal }) {
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between w-full px-6 py-2 bg-matrix-green text-black font-bold border-b-4 border-black box-border">
      <div className="flex gap-6 items-center">
        <div className="flex items-center gap-2">
          <TerminalIcon size={18} strokeWidth={3} />
          <h1 className="text-lg font-black tracking-tighter uppercase">RADAR COMERCIAL</h1>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="hidden md:flex gap-3 text-[10px] font-black uppercase">
          <MercadoLibreBadge health={cookieHealth} />
          <div className="flex items-center gap-2 px-3 py-1 bg-black text-matrix-green border border-matrix-green shadow-[0_0_10px_rgba(51,255,102,0.2)]">
            <CheckCircle2 size={12} />
            TARJETAS (FB)
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            soundService.playClick()
            onOpenCookieModal()
          }}
          className="flex items-center justify-center w-8 h-8 bg-black text-matrix-green border border-black hover:bg-matrix-green hover:text-black transition-all"
          title={`Cookies ML: ${cookieHealth?.label || 'sin estado'} / FB: ${facebookCookieHealth?.label || 'sin estado'}`}
        >
          <Cookie size={15} strokeWidth={3} />
        </button>
      </div>
    </header>
  )
}
