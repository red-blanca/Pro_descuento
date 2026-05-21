import { Settings, Cookie, CheckCircle2, Terminal as TerminalIcon } from 'lucide-react';

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between w-full px-6 py-2 bg-matrix-green text-black font-bold border-b-4 border-black box-border">
      <div className="flex gap-6 items-center">
        <div className="flex items-center gap-2">
          <TerminalIcon size={18} strokeWidth={3} />
          <h1 className="text-lg font-black tracking-tighter uppercase">
            RADAR COMERCIAL
          </h1>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden md:flex gap-3 text-[10px] font-black uppercase">
          {/* Mercado Libre Cookie Indicator (Mock Not Updated) */}
          <div className="flex items-center gap-2 px-3 py-1 bg-black text-[#ff3333] border border-[#ff3333] shadow-[0_0_10px_rgba(255,51,51,0.2)]">
            <span className="w-1.5 h-1.5 bg-[#ff3333] rounded-full animate-pulse shadow-[0_0_5px_#ff3333]" />
            SIN COOKIES (ML)
          </div>
          
          {/* Facebook Cookie Indicator (Mock Updated) */}
          <div className="flex items-center gap-2 px-3 py-1 bg-black text-matrix-green border border-matrix-green shadow-[0_0_10px_rgba(51,255,102,0.2)]">
             <CheckCircle2 size={12} />
             TARJETAS (FB)
          </div>
        </div>
      </div>
    </header>
  );
}
