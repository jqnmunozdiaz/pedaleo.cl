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
5. Un sistema de propuesta de carreras conectado a **GitHub Issues** para notificaciones inmediatas al mantenedor.

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
├── README.md                        # Documentación general de usuario y despliegue
├── .github/
│   └── workflows/
│       └── deploy.yml               # Workflow de GitHub Pages y scraping programado (06:00 UTC)
├── assets/
│   ├── css/
│   │   └── style.css                # Estilos sobrios, accesibles y CSS Grid para calendario
│   ├── js/
│   │   ├── app.js                   # Controlador de la aplicación, filtros en tiempo real y URLs
│   │   ├── calendar-exporter.js     # Generador de enlaces a Google Calendar y archivos .ics
│   │   └── calendar-view.js         # Vista de grilla mensual con columnas de ancho fijo (CSS Grid)
│   └── img/
│       └── logo.svg                 # Identidad visual sobria de Pedaleo.cl
├── data/
│   ├── events.json                  # Catálogo central de carreras (fuente única de verdad)
│   └── regions.json                 # Catálogo oficial de las 16 regiones de Chile
└── scripts/
    ├── requirements.txt             # Dependencias Python (requests, beautifulsoup4)
    ├── sync_events.py               # Orquestador de sincronización, deduplicación y guardado
    ├── validate_events.py           # Validador de esquemas e integridad (fechas ISO y regiones)
    ├── add_event.py                 # Asistente CLI interactivo para ingreso manual rápido
    └── scrapers/
        ├── __init__.py              # Exportador de scrapers
        ├── base_scraper.py          # Clase base con resolución geográfica y de disciplinas
        ├── bicineta_scraper.py      # Scraper multietiqueta de Bicineta.cl
        ├── guca_scraper.py          # Scraper de tickets oficiales de GUCA.cl
        └── ticketsport_scraper.py   # Scraper de TicketSport.cl
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
  "source": "bicineta"
}
```

### Reglas de Validación:
- `date`: Formato estricto `YYYY-MM-DD`.
- `region`: Debe pertenecer al conjunto de 16 códigos válidos: `["XV", "I", "II", "III", "IV", "V", "RM", "VI", "VII", "XVI", "VIII", "IX", "XIV", "X", "XI", "XII"]`.
- `id`: No pueden existir claves duplicadas.

---

## 5. Pipeline de Sincronización y Scrapers

1. **Ejecución Manual**:
   ```powershell
   conda activate py313
   python scripts/sync_events.py
   python scripts/validate_events.py
   ```
2. **Ejecución Automática**:
   El flujo `.github/workflows/deploy.yml` corre diariamente a las `06:00 UTC`.
   Si detecta carreras nuevas o actualizaciones en `data/events.json`, genera un commit automático con `[skip ci]` y redespliega en GitHub Pages.

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
3. **Notificaciones de Nuevas Carreras**:
   - El formulario "Publicar Carrera" genera una Issue con plantilla estructurada en el repositorio de GitHub (`https://github.com/jqnmunozdiaz/pedaleo.cl/issues/new`), lo que activa las alertas móviles y por correo oficiales de GitHub para el mantenedor sin requerir servidores intermediarios.
