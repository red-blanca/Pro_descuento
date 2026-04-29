# Knasta Scraper

Este es un scraper rápido y moderno para [Knasta.cl](https://knasta.cl/), que utiliza peticiones HTTP directas para interceptar los datos de React/NextJS sin necesidad de usar un navegador virtual, lo que lo hace 100 veces más rápido y menos propenso a bloqueos.

## Características
- **Búsqueda General**: Busca cualquier producto.
- **Búsqueda por Tienda**: Filtra por tiendas (ej. lider, falabella, pcfactory).
- **Ofertas de Hoy**: Encuentra los productos que bajaron de precio en las últimas 24 horas (`knastaday=1`).
- **Ofertas Tecno**: Busca en la categoría completa de tecnología (`category=20000`).
- **Paginación Automática**: Soporta buscar de 40 en 40 o más resultados automáticamente.
- **Exportación Excel**: Guarda los resultados.

## Cómo correrlo
```bash
python run_dev.py
```
Esto levantará el backend en el puerto `8020` y el frontend en el puerto `5185`, abriendo tu navegador automáticamente.
