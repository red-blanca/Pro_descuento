export const GLOBAL_NODES = [
  { id: 'mercadolibre', sourceKey: 'mercadolibre', name: 'MercadoLibre', icon: 'Handshake' },
  { id: 'facebook', sourceKey: 'facebook_marketplace', name: 'Facebook', icon: 'Facebook' },
  { id: 'pulga', sourceKey: 'pulga', name: 'Pulga', icon: 'Bug' },
  { id: 'knasta', sourceKey: 'knasta', name: 'Knasta', icon: 'ShoppingBasket' },
  { id: 'solotodo', sourceKey: 'solotodo', name: 'SoloTodo', icon: 'Cpu' },
  { id: 'travel', sourceKey: 'travel', name: 'Travel', icon: 'Plane' },
  { id: 'tuganga', sourceKey: 'tuganga', name: 'TuGanga', icon: 'Zap' },
  { id: 'pcfactory', sourceKey: 'pcfactory', name: 'PcFactory', icon: 'Monitor' },
  { id: 'rata', sourceKey: 'descuentosrata', name: 'DescuentosRata', icon: 'TrendingDown' },
]

export function isNodeActive(node, sources) {
  return sources.includes(node.sourceKey)
}

export function getRunForNode(node, runs = []) {
  return runs.find((run) => run.source === node.sourceKey)
}
