# 🚴 Pedaleo.cl — Calendario de Carreras de Ciclismo en Chile

**Pedaleo.cl** es una plataforma web estática, rápida y ultra liviana diseñada para compilar todas las carreras y eventos de ciclismo que se realizan a lo largo de Chile (MTB, Ruta, Gravel, Ultraciclismo, Enduro y Descenso). 

Inspirado directamente en la simplicidad, velocidad y funcionalidad de **corre.cl**, entrega a los ciclistas un calendario claro con filtros avanzados y un planificador de temporada personalizable con exportación directa a Google Calendar y Apple Calendar (.ics).

---

## 🌟 Características Principales

1. **Inspiración Corre.cl**:
   - Diseño limpio, enfocado 100% en la legibilidad y rapidez sin elementos distractores.
   - Vista de **Agenda cronológica** agrupada por mes y día.
   - Acceso inmediato a links de bases oficiales e inscripción.

2. **Filtros Avanzados para Ciclistas**:
   - **Por Región**: Cobertura de las 16 regiones de Chile (Arica a Magallanes).
   - **Por Disciplina**: Mountain Bike (XCM, XCO), Ruta y Gran Fondo, Gravel, Ultraciclismo / Bikepacking, Enduro y Descenso.
   - **Por Mes** (multi-selección) y opción para incluir carreras pasadas (por defecto solo se muestran las próximas).
   - **Búsqueda en tiempo real**: Por nombre, comuna o productora, sin distinguir tildes.
   - **Enlaces compartibles**: El estado de los filtros se sincroniza con los parámetros URL (`?region=VI&disciplina=gravel`) y cada carrera tiene enlace directo (`#carrera=<id>`) con botón "Compartir".

3. **Agendamiento Directo por Carrera**:
   - Cada carrera cuenta con botones directos para agendarla en **Google Calendar** (enlace con detalles prellenados) o descargar el archivo **Apple Calendar / Outlook (.ics)** con alarmas recordatorias.

4. **Vistas Múltiples y Equilibradas**:
   - **Vista Lista (simplificada y ágil)**: Lista ordenada por mes con chip de fecha, badges sobrios de disciplina, datos de comuna, distancia y altimetría.
   - **Vista Mapa de Chile**: Mapa interactivo (Leaflet + OpenStreetMap) con pines por localidad coloreados por disciplina, popups interactivos y auto-zoom automático adaptado a los filtros del ciclista.
   - **Vista Calendario Mensual (CSS Grid Equitativo)**: Grilla visual con 7 columnas idénticas y botón "+X más" para días con múltiples carreras.

5. **Alojamiento Ultra Liviano y Económico**:
   - 100% estático (HTML5, CSS moderno y JavaScript modular sin frameworks pesados).
   - Carga instantánea (< 50 KB de transferencia total).
   - Alojable de forma gratuita en **GitHub Pages**, **Cloudflare Pages**, **Netlify**, **Vercel** o cualquier servidor web.

6. **Mantenimiento y Automatización Continua**:
   - Base de datos centralizada en `data/events.json`.
   - Pipeline de sincronización y scrapers en Python (`scripts/`).
   - Automatización mediante **GitHub Actions** (`.github/workflows/deploy.yml`) que ejecuta las pruebas, consulta cada día las fuentes chilenas (Bicineta, GUCA, Ridechile, Tusdesafios, CiclismoChile, TicketSport), valida los datos y despliega sin intervención manual.
   - Las carreras cuyo sitio web ya no funciona, las canceladas y las que ninguna fuente lista hace semanas se omiten automáticamente.
   - Los pines del mapa se ubican por comuna, geocodificación en caché o (si no hay otra opción) como referencia regional aproximada.
   - Se descartan carreras de running, triatlón y de otros países; las que no tienen ubicación confirmada se guardan aparte y se pueden mostrar con el botón **Incluir sin ubicación confirmada**.
   - Asistente CLI interactivo (`scripts/add_event.py`) para registrar nuevas carreras en segundos.

---

## 🔍 Panorama de Sitios Existentes en Chile

| Plataforma | Enfoque | Limitación que resuelve Pedaleo.cl |
|---|---|---|
| **Corre.cl** | Running, maratones y trail | Excelente UI, pero enfocado exclusivamente en pedestrismo, no en ciclismo. |
| **Ridechile.cl** | Medio de comunicación y noticias | Portal editorial con calendario secundario, sin filtros ágiles de planificación ni exportación .ics. |
| **Bicineta.cl** | Ciclismo urbano y ciclovías | Portal comunitario general; no enfocado como agenda deportiva de carreras y tiempos. |
| **GUCA / TicketSport / Welcu** | Ticketeras de inscripción | Sitios separados por productora; el atleta debe revisar múltiples webs para enterarse de las fechas. |
| **Pedaleo.cl** | **Agregador unificado de ciclismo** | **Centraliza todas las carreras en un solo lugar con filtros por región/disciplina, planificador personal y exportación a calendario.** |

---

## 📂 Estructura del Proyecto

```
Pedaleo.cl/
├── index.html                       # Página principal interactiva
├── .gitignore                       # Ignora temporales, entornos y previene archivos > 100MB
├── README.md                        # Documentación completa del proyecto
├── .github/
│   └── workflows/
│       └── deploy.yml               # Workflow de GitHub Actions (pruebas, scraping diario y despliegue)
├── assets/
│   ├── css/
│   │   └── style.css                # Estilos responsive y de alto contraste inspirados en corre.cl
│   ├── js/
│   │   ├── utils.js                 # Helpers compartidos (escape HTML, fechas, búsqueda sin tildes)
│   │   ├── app.js                   # Controlador principal (filtros, vistas, modales, URL params)
│   │   ├── calendar-exporter.js     # Exportación a Google Calendar y .ics
│   │   ├── calendar-view.js         # Vista de grilla mensual
│   │   └── map-view.js              # Mapa interactivo de Chile
│   └── img/
│       └── logo.svg                 # Isotipo y logotipo oficial de Pedaleo.cl
├── data/
│   ├── events.json                  # Base de datos JSON de todas las carreras de Chile
│   ├── regions.json                 # Catálogo oficial de las 16 regiones de Chile
│   ├── communes_regions.json        # Comuna -> región (resolución geográfica de los scrapers)
│   ├── communes_coords.json         # Coordenadas por comuna y región
│   └── excluded_events.json         # IDs que los scrapers no deben re-agregar
└── scripts/
    ├── requirements.txt             # Dependencias Python (requests, beautifulsoup4, etc.)
    ├── sync_events.py               # Orquestador de sincronización, deduplicación y guardado
    ├── validate_events.py           # Validador de esquemas e integridad de datos
    ├── add_event.py                 # Asistente CLI interactivo para agregar carreras
    └── scrapers/
        ├── base_scraper.py          # Clase base con resolución de regiones y disciplinas
        ├── bicineta_scraper.py      # Scraper para Bicineta.cl
        ├── guca_scraper.py          # Scraper para GUCA.cl
        ├── ridechile_scraper.py     # Scraper para el calendario de Ridechile.cl
        ├── tusdesafios_scraper.py   # Scraper para Tusdesafios.com
        ├── ciclismochile_scraper.py # Agregador CiclismoChile.cl
        └── ticketsport_scraper.py   # Scraper para TicketSport.cl
tests/
├── test_pipeline.py                 # Pruebas unitarias del pipeline de datos
├── test_sources.py                  # Pruebas de cobertura de fuentes, ubicaciones sin confirmar y fusión
├── test_new_sources.py              # Pruebas de Tusdesafios, CiclismoChile, enlaces, estados y distancias
├── test_welcu_links.py              # Pruebas de enlaces de Welcu
├── test_health.py                   # Pruebas de salud de fuentes y carreras desaparecidas
└── test_geo.py                      # Pruebas de geocodificación y precisión de pines
```

---

## 💻 Uso y Ejecución Local

### 1. Visualizar el sitio web
Dado que el sitio es estático, basta con abrir `index.html` en cualquier navegador web o iniciar un servidor local:

```powershell
# En PowerShell (puerto 8080 en localhost)
python -m http.server 8080 --bind 127.0.0.1
```
Luego visita `http://localhost:8080` en tu navegador.

### 2. Ejecutar la sincronización y scrapers (Entorno `py313`)
Para ejecutar los scripts de actualización en tu terminal local, activa primero el entorno `py313`:

```powershell
# Activar entorno conda py313
conda activate py313

# Ejecutar las pruebas automáticas
python -m unittest discover -s tests

# Validar integridad de las carreras
python scripts/validate_events.py

# Ejecutar sincronización con ticketeras chilenas
python scripts/sync_events.py

# Agregar manualmente una nueva carrera vía asistente interactivo
python scripts/add_event.py
```

---

## 🚀 Despliegue en Producción

### Opción A: GitHub Pages (Recomendada y 100% Gratuita)
1. Crea un repositorio en GitHub y sube este proyecto (`git remote add origin ...`, `git push -u origin main`).
2. En GitHub ve a **Settings** > **Pages**.
3. En **Source** selecciona `Deploy from a branch` y escoge la rama `main` en la carpeta `/ (root)`.
4. ¡Listo! Tu sitio estará activo en `https://<usuario>.github.io/<repo>/` y el workflow de GitHub Actions mantendrá el calendario actualizado automáticamente todos los días.

### Opción B: Cloudflare Pages / Vercel / Netlify
- Conecta el repositorio de GitHub; como es un sitio estático puro, se desplegará instantáneamente sin requerir paso de build.

---

## 🤝 Mantenimiento y Aportes
- Si organizas una carrera o detectas una fecha que no figura, utiliza el botón **Publicar Carrera** dentro de la web o envía un Pull Request modificando `data/events.json`.
