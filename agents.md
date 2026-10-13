# AGENTS.MD — Guía de Arquitectura, Operación y Reglas de Pedaleo.cl

Este documento describe la arquitectura, convenciones, reglas de ejecución y flujos de trabajo para agentes de inteligencia artificial y desarrolladores que interactúen con el repositorio **Pedaleo.cl**.

---

## 1. Propósito del Proyecto

**Pedaleo.cl** es una plataforma web estática, rápida y sobria que recopila todas las carreras y eventos de ciclismo en Chile (MTB, Ruta, Gravel, Ultraciclismo, Enduro y Descenso).
Proporciona a los ciclistas:
1. Una agenda cronológica clara de eventos en las 16 regiones de Chile.
2. Filtros avanzados por región, disciplina, distancia y texto.
3. Vista de calendario mensual visual equilibrada.
4. Exportación directa de cada carrera a **Google Calendar** y **Apple Calendar (.ics)**.
5. Un formulario "Publicar Carrera" que prepara un correo a `contacto@pedaleo.cl` para que el mantenedor revise y publique la carrera.

---

## 2. Reglas Críticas para Agentes

1. **Entorno Python Obligatorio (`py313`)**:
   - Siempre que se ejecute código Python en la terminal de este proyecto, se debe utilizar el entorno `py313` creado con Conda (`C:\ProgramData\miniforge3\envs\py313\python.exe` o `conda activate py313`).
   - Al ejecutar scripts con argumentos o caracteres especiales en Windows PowerShell, garantizar codificación UTF-8 (`$env:PYTHONIOENCODING = "utf-8"`).
2. **Modificación Directa de Archivos**:
   - Modificar los archivos del proyecto directamente en los scripts destino utilizando herramientas específicas de edición de código (ej. `replace_file_content` o `write_to_file`).
   - No crear scripts auxiliares temporales para reescribir archivos cuando se puedan editar directamente.
3. **Gestión de Archivos Grandes en Git**:
   - GitHub rechaza cualquier archivo individual superior a 100 MB (y genera advertencias con archivos superiores a 50 MB).
   - Siempre verificar que ningún archivo supere los 50 MB antes de hacer commits.
   - El archivo `.gitignore` debe excluir binarios pesados, volcados de base de datos o paquetes innecesarios.
4. **Sin Delimitadores LaTeX en Comunicación**:
   - No utilizar delimitadores matemáticos de LaTeX (como `$...$` o `$$...$$`) en los mensajes de chat. Expresar cantidades y fórmulas en texto plano.

---

## 3. Arquitectura del Repositorio

```
Pedaleo.cl/
├── index.html                       # Página principal (SPA estática ligera)
├── .nojekyll                        # Asegura que GitHub Pages sirva archivos estáticos puros
├── agents.md                        # Este documento de reglas y arquitectura
├── robots.txt / sitemap.xml         # SEO básico (la URL canónica es https://jqnmunozdiaz.github.io/pedaleo.cl/; si se configura un dominio propio, actualizar index.html, sitemap.xml, robots.txt y 404.html)
├── README.md                        # Documentación general de usuario y despliegue
├── .github/
│   └── workflows/
│       └── deploy.yml               # Workflow de GitHub Pages y scraping programado (06:00 UTC)
├── assets/
│   ├── css/
│   │   └── style.css                # Estilos sobrios, accesibles y CSS Grid para calendario
│   ├── js/
│   │   ├── utils.js                 # Helpers compartidos: escape HTML, URLs seguras, fechas locales, búsqueda sin tildes
│   │   ├── app.js                   # Controlador de la aplicación, filtros, modales accesibles, enlaces directos (#carrera=id)
│   │   ├── calendar-exporter.js     # Generador de enlaces a Google Calendar y archivos .ics
│   │   ├── calendar-view.js         # Vista de grilla mensual con columnas de ancho fijo (CSS Grid)
│   │   └── map-view.js              # Mapa interactivo de Chile con pines por disciplina y auto-zoom
│   └── img/
│       └── logo.svg                 # Identidad visual sobria de Pedaleo.cl
├── data/
│   ├── communes_coords.json         # Coordenadas geográficas de referencia por comuna y región
│   ├── communes_regions.json        # Comuna/localidad -> código de región (usado por los scrapers)
│   ├── excluded_events.json         # IDs que los scrapers nunca deben volver a agregar (duplicados, descartes)
│   ├── events.json                  # Catálogo central de carreras (fuente única de verdad)
│   └── regions.json                 # Catálogo oficial de las 16 regiones de Chile
└── scripts/
    ├── requirements.txt             # Dependencias Python (requests, beautifulsoup4)
    ├── sync_events.py               # Orquestador de sincronización, deduplicación y guardado
    ├── validate_events.py           # Validador de esquemas e integridad (fechas reales, regiones, URLs, coordenadas)
    ├── add_event.py                 # Asistente CLI interactivo para ingreso manual rápido
    └── scrapers/
        ├── __init__.py              # Exportador de scrapers
        ├── base_scraper.py          # Clase base con resolución geográfica y de disciplinas
        ├── bicineta_scraper.py      # Scraper de Bicineta.cl (feed JSON /eventos/fetch_more con todas las carreras)
        ├── guca_scraper.py          # Scraper de GUCA.cl (home + página de detalle de cada carrera)
        ├── ridechile_scraper.py     # Scraper del "Nuevo Calendario" de Ridechile.cl (con distancias)
        └── ticketsport_scraper.py   # Scraper de TicketSport.cl
tests/
└── test_pipeline.py                 # Pruebas unitarias (scrapers, deduplicación, validador)
```

---

## 4. Esquema de Datos (`data/events.json`)

Cada carrera debe cumplir con la siguiente estructura JSON validada por `scripts/validate_events.py`:

```json
{
  "id": "slug-identificador-unico-ano",
  "name": "Nombre Oficial de la Carrera",
  "date": "2026-10-10",
  "end_date": "2026-10-10",
  "disciplines": ["Gravel", "MTB"],
  "region": "VI",
  "region_name": "O'Higgins",
  "commune": "Machalí",
  "location": "Machalí, Región O'Higgins",
  "distances": ["45 km", "85 km"],
  "distance_min_km": 45,
  "distance_max_km": 85,
  "elevation_gain_m": 1250,
  "price_type": "paid",
  "status": "open",
  "organizer": "Club Organizador",
  "url": "https://...",
  "registration_url": "https://...",
  "description": "Descripción concisa del evento.",
  "featured": false,
  "source": "bicineta",
  "lat": -34.1819,
  "lng": -70.6506
}
```

### Reglas de Validación:
- `date` / `end_date`: Fechas reales con formato `YYYY-MM-DD`; `end_date` no puede ser anterior a `date`.
- `id`: Slug en minúsculas (`a-z`, `0-9` y guiones).
- `url` / `registration_url`: Solo `http://` o `https://` (se renderizan como enlaces).
- `region_name`: Debe coincidir con el nombre corto de `data/regions.json`.
- `lat` / `lng`: Deben venir juntas y estar dentro de Chile.
- `location_unverified`: `true` cuando las fuentes no confirman comuna/región. En ese caso `region`, `region_name`, `commune`, `lat` y `lng` pueden faltar; la carrera se oculta por defecto en la web (botón "Incluir sin ubicación confirmada", `?sinubicacion=1`) y no se dibuja en el mapa.
- `distance_min_km` / `distance_max_km`: Números, o `null` cuando la distancia no se conoce (nunca valores inventados).
- `region`: Debe pertenecer al conjunto de 16 códigos válidos: `["XV", "I", "II", "III", "IV", "V", "RM", "VI", "VII", "XVI", "VIII", "IX", "XIV", "X", "XI", "XII"]`.
- `id`: No pueden existir claves duplicadas.

---

## 5. Pipeline de Sincronización y Scrapers

1. **Ejecución Manual**:
   ```powershell
   conda activate py313
   python -m unittest discover -s tests
   python scripts/sync_events.py
   python scripts/validate_events.py
   ```
   Reglas de los scrapers:
   - Nunca se inventa una región ni una fecha: sin fecha el evento se omite. Si el lugar no se puede ubicar (`data/communes_regions.json`) la carrera **se conserva** con `location_unverified: true`; si el lugar es extranjero se descarta.
   - Se descartan eventos extranjeros y que no son de ciclismo (running, triatlón, aguas abiertas, etc.).
   - Una comuna conocida manda sobre la región que marca el organizador (Bicineta a veces se equivoca). Agrega comunas nuevas a `data/communes_regions.json` para que las carreras queden ubicadas.
   - Bicineta solo muestra 16 carreras en HTML; el scraper recorre su endpoint JSON `/eventos/fetch_more` (el feed no trae año: se deduce del orden cronológico).
   - Duplicados entre fuentes se fusionan por enlace de inscripción (salvo enlaces de redes sociales compartidos por toda una serie) o por fecha + región + título parecido; los que la heurística no detecta se registran en `data/excluded_events.json`. Al fusionar, una fuente puede completar la ubicación o las distancias que faltaban.
   - Para una fuente, un cambio de fecha actualiza la carrera existente; otras fuentes nunca pisan fechas curadas manualmente.
2. **Ejecución Automática**:
   El flujo `.github/workflows/deploy.yml` corre diariamente a las `06:00 UTC`.
   Ejecuta las pruebas, sincroniza, valida, y si detecta cambios en `data/events.json` genera un commit automático con `[skip ci]`. Antes de desplegar reemplaza el `?v=` de los assets en `index.html` por el hash del commit (invalida la caché del navegador).

---

## 6. Filosofía de Diseño Frontend (Perfil Sobrio)

1. **Paleta de Colores**:
   - Fondos: Blanco limpio (`#ffffff`) y pizarra sutil (`#f8fafc`).
   - Texto: Gris oscuro de alto contraste (`#0f172a` y `#334155`).
   - Acentos: Verde bosque sobrio (`#166534`) y azul pizarra (`#1e40af`).
   - Badges de disciplina: Tonos pastel atenuados con bordes definidos, evitando saturaciones estridentes.
2. **Calendario Mensual**:
   - Utilizar **CSS Grid con 7 columnas idénticas** (`repeat(7, minmax(0, 1fr))`) para garantizar que ningún día de la semana sea comprimido.
   - Limitar el contenido de días con muchas carreras y ofrecer interacción para visualizar la lista completa sin desbordar los límites del contenedor.
3. **Propuesta de Nuevas Carreras**:
   - El formulario "Publicar Carrera" abre el cliente de correo con un mensaje estructurado hacia `contacto@pedaleo.cl` (sin servidores intermediarios). El mantenedor agrega la carrera con `scripts/add_event.py`.
4. **Seguridad y Accesibilidad Frontend**:
   - Todo dato de `events.json` (viene de scrapers) se inserta en el DOM con `Utils.esc()`; los enlaces pasan por `Utils.safeUrl()` / `Utils.eventHref()`. Nunca interpolar datos de eventos en `innerHTML` sin escapar.
   - Las fechas son strings `YYYY-MM-DD`: usar `Utils.todayStr()` / `Utils.parseDate()` (no `toISOString()`, que usa UTC y cambia el día en Chile).
   - Los modales se abren con `App.showModal(id)` (gestiona foco, `Escape`, bloqueo de scroll).
   - Por defecto solo se listan carreras que aún no terminan; el interruptor "Incluir pasadas" (`?pasadas=1`) muestra el historial.
