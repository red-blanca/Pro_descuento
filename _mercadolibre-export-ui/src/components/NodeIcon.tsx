import { 
  Handshake, 
  Facebook, 
  Bug, 
  ShoppingBasket, 
  Cpu, 
  Plane, 
  Zap, 
  TrendingDown,
  LucideProps
} from 'lucide-react';

interface NodeIconProps {
  name: string;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export default function NodeIcon({ name, ...props }: NodeIconProps) {
  switch (name) {
    case 'Handshake': return <Handshake {...props} />;
    case 'Facebook': return <Facebook {...props} />;
    case 'Bug': return <Bug {...props} />;
    case 'ShoppingBasket': return <ShoppingBasket {...props} />;
    case 'Cpu': return <Cpu {...props} />;
    case 'Plane': return <Plane {...props} />;
    case 'Zap': return <Zap {...props} />;
    case 'TrendingDown': return <TrendingDown {...props} />;
    default: return <Cpu {...props} />;
  }
}
