import { CheckCircle2, ShieldAlert, ShieldCheck, ShieldX, Terminal as TerminalIcon } from 'lucide-react'
import { soundService } from './soundService'

function CookieBadge({ health, prefix }) {
  const colorClass = health.color === 'green'
    ? 'text-matrix-green border-matrix-green shadow-[0_0_10px_rgba(51,255,102,0.2)]'
    : health.color === 'yellow'
      ? 'text-yellow-300 border-yellow-300 shadow-[0_0_10px_rgba(253,224,71,0.2)]'
      : 'text-[#ff3333] border-[#ff3333] shadow-[0_0_10px_rgba(255,51,51,0.2)]'

  return (
    <div className={`flex items-center gap-2 px-3 py-1 bg-black ${colorClass}`}>
      {health.icon === 'ok' && (prefix === 'FB' ? <CheckCircle2 size={12} /> : <ShieldCheck size={12} />)}
      {health.icon === 'warn' && <ShieldAlert size={12} />}
      {health.icon === 'x' && <ShieldX size={12} />}
      <span className="w-1.5 h-1.5 rounded-full animate-pulse bg-current shadow-[0_0_5px_currentColor]" />
      {prefix}: {health.label}
    </div>
  )
}

export default function GlobalSearchNavbar({ cookieHealth, facebookCookieHealth, onOpenCookieModal }) {
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between w-full px-4 md:px-6 py-2 bg-matrix-green text-black font-bold border-b-4 border-black box-border">
      <div className="flex gap-6 items-center min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <TerminalIcon size={18} strokeWidth={3} className="shrink-0" />
          <h1 className="text-base md:text-lg font-black tracking-tighter uppercase truncate">RADAR COMERCIAL</h1>
        </div>
      </div>
      <button
        type="button"
        onClick={() => {
          soundService.playClick()
          onOpenCookieModal()
        }}
        className="hidden md:flex gap-3 text-[10px] font-black uppercase"
      >
        <CookieBadge health={cookieHealth} prefix="ML" />
        <CookieBadge health={facebookCookieHealth} prefix="FB" />
      </button>
    </header>
  )
}
