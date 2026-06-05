import { Bug, Cpu, Facebook, Globe, Handshake, Plane, ShoppingBasket, Store, TrendingDown, Zap } from 'lucide-react'

export default function GlobalSearchNodeIcon({ name, ...props }) {
  switch (name) {
    case 'Handshake': return <Handshake {...props} />
    case 'Facebook': return <Facebook {...props} />
    case 'Globe': return <Globe {...props} />
    case 'Bug': return <Bug {...props} />
    case 'ShoppingBasket': return <ShoppingBasket {...props} />
    case 'Store': return <Store {...props} />
    case 'Cpu': return <Cpu {...props} />
    case 'Plane': return <Plane {...props} />
    case 'Zap': return <Zap {...props} />
    case 'TrendingDown': return <TrendingDown {...props} />
    default: return <Cpu {...props} />
  }
}
