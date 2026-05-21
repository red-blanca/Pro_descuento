export interface Node {
  id: string;
  name: string;
  active: boolean;
  icon: string;
}

export const NODES: Node[] = [
  { id: 'mercadolibre', name: 'MercadoLibre', active: true, icon: 'Handshake' },
  { id: 'facebook', name: 'Facebook', active: false, icon: 'Facebook' },
  { id: 'pulga', name: 'Pulga', active: false, icon: 'Bug' },
  { id: 'knasta', name: 'Knasta', active: true, icon: 'ShoppingBasket' },
  { id: 'solotodo', name: 'SoloTodo', active: true, icon: 'Cpu' },
  { id: 'travel', name: 'Travel', active: false, icon: 'Plane' },
  { id: 'tuganga', name: 'TuGanga', active: false, icon: 'Zap' },
  { id: 'rata', name: 'DescuentosRata', active: false, icon: 'TrendingDown' },
];
