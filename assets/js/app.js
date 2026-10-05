/**
 * Pedaleo.cl - Main Application Controller
 * Inspired by corre.cl: fast, simple, responsive, lightweight
 */

document.addEventListener('DOMContentLoaded', () => {
  const App = {
    events: [],
    regions: [],
    filteredEvents: [],

    filters: {
      search: '',
      region: '',
      discipline: '',
      distance: 'all',
      price: 'all',
      status: 'all'
    },

    currentView: 'agenda', // 'agenda' | 'calendar' | 'planner'

    async init() {
      await this.loadData();
      this.initFiltersFromURL();
      this.setupDOMListeners();
      Planner.updateBadge();
      this.applyFilters();
    },

    async loadData() {
      try {
        const [eventsRes, regionsRes] = await Promise.all([
          fetch('data/events.json'),
          fetch('data/regions.json')
        ]);
        this.events = await eventsRes.json();
        this.regions = await regionsRes.json();
        this.populateRegionSelect();
      } catch (err) {
        console.error('Error cargando los datos:', err);
        document.getElementById('events-container').innerHTML = `
          <div class="planner-empty-state">
            <p>Error al cargar el calendario de carreras. Por favor recarga la página.</p>
          </div>
        `;
      }
    },

    populateRegionSelect() {
      const select = document.getElementById('filter-region');
      if (!select) return;
      select.innerHTML = '<option value="">Todas las regiones...</option>';
      this.regions.forEach(reg => {
        const opt = document.createElement('option');
        opt.value = reg.id;
        opt.textContent = `${reg.roman} - ${reg.name}`;
        select.appendChild(opt);
      });
      if (this.filters.region) {
        select.value = this.filters.region;
      }
    },

    initFiltersFromURL() {
      const params = new URLSearchParams(window.location.search);
      if (params.get('region')) this.filters.region = params.get('region');
      if (params.get('disciplina')) this.filters.discipline = params.get('disciplina');
      if (params.get('distancia')) this.filters.distance = params.get('distancia');
      if (params.get('buscar')) this.filters.search = params.get('buscar');
      if (params.get('vista')) this.currentView = params.get('vista');

      const searchInput = document.getElementById('search-input');
      if (searchInput && this.filters.search) {
        searchInput.value = this.filters.search;
      }

      const discSelect = document.getElementById('filter-discipline');
      if (discSelect && this.filters.discipline) {
        discSelect.value = this.filters.discipline;
      }

      this.updateViewButtons();
    },

    updateURL() {
      const params = new URLSearchParams();
      if (this.filters.region) params.set('region', this.filters.region);
      if (this.filters.discipline) params.set('disciplina', this.filters.discipline);
      if (this.filters.distance !== 'all') params.set('distancia', this.filters.distance);
      if (this.filters.search) params.set('buscar', this.filters.search);
      if (this.currentView !== 'agenda') params.set('vista', this.currentView);

      const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
      window.history.replaceState({}, '', newUrl);
    },

    setupDOMListeners() {
      // Search Input
      const searchInput = document.getElementById('search-input');
      if (searchInput) {
        searchInput.addEventListener('input', (e) => {
          this.filters.search = e.target.value.trim().toLowerCase();
          this.applyFilters();
        });
      }

      // Region Filter
      const regionSelect = document.getElementById('filter-region');
      if (regionSelect) {
        regionSelect.addEventListener('change', (e) => {
          this.filters.region = e.target.value;
          this.applyFilters();
        });
      }

      // Discipline Filter
      const discSelect = document.getElementById('filter-discipline');
      if (discSelect) {
        discSelect.addEventListener('change', (e) => {
          this.filters.discipline = e.target.value;
          this.applyFilters();
        });
      }

      // Distance Pills
      document.querySelectorAll('.pill-distance').forEach(btn => {
        btn.addEventListener('click', (e) => {
          document.querySelectorAll('.pill-distance').forEach(b => b.classList.remove('active'));
          e.currentTarget.classList.add('active');
          this.filters.distance = e.currentTarget.dataset.distance;
          this.applyFilters();
        });
      });

      // Clear Filters
      const clearBtn = document.getElementById('clear-filters');
      if (clearBtn) {
        clearBtn.addEventListener('click', () => {
          this.filters.search = '';
          this.filters.region = '';
          this.filters.discipline = '';
          this.filters.distance = 'all';
          this.filters.price = 'all';

          if (searchInput) searchInput.value = '';
          if (regionSelect) regionSelect.value = '';
          if (discSelect) discSelect.value = '';

          document.querySelectorAll('.pill-distance').forEach(b => {
            b.classList.toggle('active', b.dataset.distance === 'all');
          });

          this.applyFilters();
        });
      }

      // View Switcher Buttons
      document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          this.currentView = e.currentTarget.dataset.view;
          this.updateViewButtons();
          this.render();
          this.updateURL();
        });
      });

      // Top Nav Links
      document.getElementById('nav-calendar')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.currentView = 'agenda';
        this.updateViewButtons();
        this.render();
        this.updateURL();
      });

      document.getElementById('nav-planner')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.currentView = 'planner';
        this.updateViewButtons();
        this.render();
        this.updateURL();
      });

      document.getElementById('nav-publish')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.openPublishModal();
      });

      // Modals
      document.getElementById('modal-close-detail')?.addEventListener('click', () => this.closeModals());
      document.getElementById('modal-close-publish')?.addEventListener('click', () => this.closeModals());
      document.querySelectorAll('.modal-overlay').forEach(ov => {
        ov.addEventListener('click', (e) => {
          if (e.target === ov) this.closeModals();
        });
      });

      // Form Submit Race
      const publishForm = document.getElementById('publish-race-form');
      if (publishForm) {
        publishForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.handlePublishFormSubmit(publishForm);
        });
      }
    },

    updateViewButtons() {
      document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === this.currentView);
      });
      document.querySelectorAll('.nav-btn').forEach(btn => {
        if (btn.id === 'nav-calendar') btn.classList.toggle('active', this.currentView === 'agenda' || this.currentView === 'calendar');
        if (btn.id === 'nav-planner') btn.classList.toggle('active', this.currentView === 'planner');
      });

      // Filter bar visibility: hide filters on "planner" view if desired, or keep available
      const filterBar = document.getElementById('filter-bar-container');
      if (filterBar) {
        filterBar.style.display = this.currentView === 'planner' ? 'none' : 'block';
      }
    },

    applyFilters() {
      this.filteredEvents = this.events.filter(ev => {
        // Search query
        if (this.filters.search) {
          const q = this.filters.search;
          const matchName = ev.name.toLowerCase().includes(q);
          const matchLoc = (ev.location || '').toLowerCase().includes(q);
          const matchCom = (ev.commune || '').toLowerCase().includes(q);
          const matchOrg = (ev.organizer || '').toLowerCase().includes(q);
          const matchDesc = (ev.description || '').toLowerCase().includes(q);
          if (!matchName && !matchLoc && !matchCom && !matchOrg && !matchDesc) return false;
        }

        // Region
        if (this.filters.region && ev.region !== this.filters.region) {
          return false;
        }

        // Discipline
        if (this.filters.discipline) {
          const match = ev.disciplines.some(d => d.toLowerCase().includes(this.filters.discipline.toLowerCase()));
          if (!match) return false;
        }

        // Distance
        if (this.filters.distance !== 'all') {
          const maxDist = ev.distance_max_km || 0;
          if (this.filters.distance === 'short' && maxDist > 40) return false;
          if (this.filters.distance === 'mid' && (maxDist < 40 || maxDist > 90)) return false;
          if (this.filters.distance === 'long' && maxDist < 90) return false;
          if (this.filters.distance === 'ultra' && maxDist < 200) return false;
        }

        return true;
      });

      // Sort chronologically by date
      this.filteredEvents.sort((a, b) => a.date.localeCompare(b.date));

      this.updateURL();
      this.render();
    },

    render() {
      const container = document.getElementById('events-container');
      const countEl = document.getElementById('results-count');
      if (countEl) countEl.textContent = `${this.filteredEvents.length} carrera${this.filteredEvents.length === 1 ? '' : 's'}`;

      if (this.currentView === 'planner') {
        this.renderPlannerView(container);
      } else if (this.currentView === 'calendar') {
        CalendarView.render(container, this.filteredEvents, (ev) => this.openDetailModal(ev));
      } else {
        this.renderAgendaView(container);
      }
    },

    /**
     * Agenda View (corre.cl style list grouped by Month and Day)
     */
    renderAgendaView(container) {
      if (this.filteredEvents.length === 0) {
        container.innerHTML = `
          <div class="planner-panel">
            <div class="planner-empty-state">
              <div class="planner-empty-icon">🚴</div>
              <h3>No se encontraron carreras con los filtros seleccionados</h3>
              <p style="margin-top:0.5rem">Intenta ajustar tu búsqueda, cambiar la región o limpiar los filtros.</p>
              <button class="cal-nav-btn" style="margin-top:1rem" id="empty-clear-btn">Limpiar Filtros</button>
            </div>
          </div>
        `;
        document.getElementById('empty-clear-btn')?.addEventListener('click', () => {
          document.getElementById('clear-filters')?.click();
        });
        return;
      }

      // Group events by Month ("YYYY-MM")
      const groups = {};
      this.filteredEvents.forEach(ev => {
        const monthKey = ev.date.substring(0, 7); // e.g. "2026-10"
        if (!groups[monthKey]) groups[monthKey] = [];
        groups[monthKey].push(ev);
      });

      let html = '';
      const monthNames = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
      ];
      const dayNames = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];

      for (const [monthKey, monthEvents] of Object.entries(groups)) {
        const [year, month] = monthKey.split('-').map(Number);
        const monthTitle = `${monthNames[month - 1]} ${year}`;

        html += `
          <div class="month-group">
            <div class="month-header">
              <span>📅 ${monthTitle}</span>
              <span class="month-badge">${monthEvents.length} carrera${monthEvents.length === 1 ? '' : 's'}</span>
            </div>
            <div class="month-events-container">
        `;

        // Subgroup by date
        const dateSubgroups = {};
        monthEvents.forEach(ev => {
          if (!dateSubgroups[ev.date]) dateSubgroups[ev.date] = [];
          dateSubgroups[ev.date].push(ev);
        });

        for (const [dateStr, dayEvents] of Object.entries(dateSubgroups)) {
          const dObj = new Date(dateStr + 'T12:00:00');
          const dayFormatted = `${String(dObj.getDate()).padStart(2, '0')}/${String(dObj.getMonth() + 1).padStart(2, '0')} - ${dayNames[dObj.getDay()]}`;

          html += `<div class="day-header">📌 ${dayFormatted}</div>`;

          dayEvents.forEach(ev => {
            const isPlanned = Planner.isPlanned(ev.id);
            const discMain = (ev.disciplines[0] || 'MTB').toLowerCase().split('/')[0];
            const discClass = `badge-${discMain}`;

            let distText = ev.distances && ev.distances.length ? ev.distances.join(' y ') : '';
            let elevText = ev.elevation_gain_m ? `+${ev.elevation_gain_m.toLocaleString('es-CL')}m` : '';

            html += `
              <div class="event-row" data-id="${ev.id}">
                <div>
                  <span class="badge-discipline ${discClass}">${ev.disciplines.join(' / ')}</span>
                </div>
                <div class="event-info">
                  <a href="#" class="event-name-link" data-id="${ev.id}">${ev.name}</a>
                  <div class="event-meta">
                    <span class="event-location">📍 ${ev.location || ev.commune}</span>
                    <span class="badge-region">Región ${ev.region_name || ev.region}</span>
                    ${distText ? `<span class="event-dist">🏁 ${distText}</span>` : ''}
                    ${elevText ? `<span class="event-elev">⛰️ ${elevText}</span>` : ''}
                    ${ev.price_type === 'free' ? '<span class="badge-price-free">GRATIS</span>' : ''}
                  </div>
                </div>
                <div class="event-actions">
                  <button class="btn-star-plan ${isPlanned ? 'planned' : ''}" data-id="${ev.id}" title="${isPlanned ? 'Quitar de Mi Temporada' : 'Agregar a Mi Temporada (Planificar)'}">
                    ★
                  </button>
                  <a href="${ev.registration_url || ev.url}" target="_blank" rel="noopener" class="btn-race-link">
                    Inscripción / Info &rarr;
                  </a>
                </div>
              </div>
            `;
          });
        }

        html += `
            </div>
          </div>
        `;
      }

      container.innerHTML = html;
      this.attachEventRowListeners(container);
    },

    /**
     * Planner View ("Mi Temporada / Mis Carreras")
     */
    renderPlannerView(container) {
      const planned = Planner.getPlannedRaces();
      const plannedMap = new Map(planned.map(p => [p.id, p]));
      const userEvents = this.events.filter(e => plannedMap.has(e.id));
      userEvents.sort((a, b) => a.date.localeCompare(b.date));

      // Calculate Metrics
      let totalKm = 0;
      let totalElev = 0;
      userEvents.forEach(e => {
        totalKm += e.distance_max_km || 0;
        totalElev += e.elevation_gain_m || 0;
      });

      // Days to next race
      let daysToNext = '-';
      const today = new Date().toISOString().split('T')[0];
      const nextRace = userEvents.find(e => e.date >= today);
      if (nextRace) {
        const diff = Math.ceil((new Date(nextRace.date) - new Date(today)) / (1000 * 60 * 60 * 24));
        daysToNext = `${diff} día${diff === 1 ? '' : 's'}`;
      }

      let html = `
        <div class="planner-panel">
          <div class="planner-header">
            <div>
              <div class="planner-title">🚴 Mi Temporada de Carreras</div>
              <p style="color:var(--text-muted); font-size:0.9rem; margin-top:0.25rem">
                Organiza tu calendario de competencias, define prioridades (Objetivos A, B, C) y sincroniza con tu calendario personal.
              </p>
            </div>
            <div class="planner-actions">
              <button class="btn-export-ics" id="btn-export-ics">
                📅 Exportar a Google / Apple Calendar (.ics)
              </button>
            </div>
          </div>

          <div class="planner-kpis">
            <div class="kpi-card">
              <div class="kpi-label">Carreras Planificadas</div>
              <div class="kpi-value">${userEvents.length}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Kilómetros Totales</div>
              <div class="kpi-value">${totalKm.toLocaleString('es-CL')} km</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Desnivel Acumulado</div>
              <div class="kpi-value">+${totalElev.toLocaleString('es-CL')} m</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">Próxima Carrera en</div>
              <div class="kpi-value">${daysToNext}</div>
            </div>
          </div>
      `;

      if (userEvents.length === 0) {
        html += `
          <div class="planner-empty-state">
            <div class="planner-empty-icon">⭐</div>
            <h3>No tienes carreras en tu temporada todavía</h3>
            <p style="margin-top:0.5rem">
              Explora el <a href="#" id="planner-go-calendar" style="color:var(--primary); font-weight:700">Calendario</a> y haz clic en la estrella (★) para agregar carreras a tus objetivos.
            </p>
          </div>
        `;
      } else {
        html += '<div class="month-events-container" style="border:1px solid var(--border-color); border-radius:var(--radius-sm)">';

        userEvents.forEach(ev => {
          const planInfo = plannedMap.get(ev.id);
          const discMain = (ev.disciplines[0] || 'MTB').toLowerCase().split('/')[0];
          const discClass = `badge-${discMain}`;

          html += `
            <div class="event-row" data-id="${ev.id}">
              <div>
                <span class="badge-discipline ${discClass}">${ev.disciplines.join(' / ')}</span>
              </div>
              <div class="event-info">
                <a href="#" class="event-name-link" data-id="${ev.id}">${ev.name}</a>
                <div class="event-meta">
                  <span>📅 ${ev.date}</span>
                  <span>📍 ${ev.location || ev.commune}</span>
                  <span class="event-dist">🏁 ${ev.distances.join(', ')}</span>
                  ${ev.elevation_gain_m ? `<span class="event-elev">⛰️ +${ev.elevation_gain_m}m</span>` : ''}
                </div>
              </div>
              <div>
                <div style="display:flex; flex-direction:column; gap:0.35rem">
                  <div style="font-size:0.75rem; color:var(--text-muted); font-weight:600">Prioridad:</div>
                  <div class="priority-selector">
                    <span class="priority-opt ${planInfo.priority === 'A' ? 'active-A' : ''}" data-p="A" data-id="${ev.id}">Obj. A</span>
                    <span class="priority-opt ${planInfo.priority === 'B' ? 'active-B' : ''}" data-p="B" data-id="${ev.id}">Obj. B</span>
                    <span class="priority-opt ${planInfo.priority === 'C' ? 'active-C' : ''}" data-p="C" data-id="${ev.id}">Obj. C</span>
                  </div>
                </div>
              </div>
              <div class="event-actions">
                <button class="btn-star-plan planned" data-id="${ev.id}" title="Quitar de mi temporada">
                  ✕
                </button>
                <a href="${ev.registration_url || ev.url}" target="_blank" rel="noopener" class="btn-race-link">
                  Inscripción &rarr;
                </a>
              </div>
            </div>
          `;
        });

        html += '</div>';
      }

      html += '</div>';
      container.innerHTML = html;

      // Listeners
      document.getElementById('btn-export-ics')?.addEventListener('click', () => {
        Planner.exportToICS(this.events);
      });

      document.getElementById('planner-go-calendar')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.currentView = 'agenda';
        this.updateViewButtons();
        this.render();
      });

      container.querySelectorAll('.priority-opt').forEach(opt => {
        opt.addEventListener('click', (e) => {
          const id = e.currentTarget.dataset.id;
          const priority = e.currentTarget.dataset.p;
          Planner.setPriority(id, priority);
          this.render();
        });
      });

      this.attachEventRowListeners(container);
    },

    attachEventRowListeners(container) {
      // Name click -> Detail modal
      container.querySelectorAll('.event-name-link').forEach(link => {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          const id = e.currentTarget.dataset.id;
          const ev = this.events.find(item => item.id === id);
          if (ev) this.openDetailModal(ev);
        });
      });

      // Star toggle
      container.querySelectorAll('.btn-star-plan').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const id = e.currentTarget.dataset.id;
          Planner.toggleRace(id);
          this.render();
        });
      });
    },

    openDetailModal(ev) {
      const isPlanned = Planner.isPlanned(ev.id);
      const modal = document.getElementById('modal-detail');
      const body = document.getElementById('modal-detail-body');
      const title = document.getElementById('modal-detail-title');

      if (!modal || !body || !title) return;

      title.textContent = ev.name;
      body.innerHTML = `
        <div style="display:flex; flex-wrap:wrap; gap:0.5rem; margin-bottom:1rem">
          <span class="badge-discipline badge-${(ev.disciplines[0]||'mtb').toLowerCase().split('/')[0]}">${ev.disciplines.join(', ')}</span>
          <span class="badge-region">Región ${ev.region_name || ev.region}</span>
          ${ev.price_type === 'free' ? '<span class="badge-price-free">GRATUITA</span>' : ''}
        </div>

        <p style="margin-bottom:1.25rem; font-size:0.95rem; color:#334155; line-height:1.6">
          ${ev.description || 'Sin descripción detallada disponible.'}
        </p>

        <div style="background:var(--bg-subtle); padding:1rem; border-radius:var(--radius-sm); margin-bottom:1.25rem; display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; font-size:0.88rem">
          <div><strong>Fecha:</strong> ${ev.date} ${ev.end_date && ev.end_date !== ev.date ? 'al ' + ev.end_date : ''}</div>
          <div><strong>Lugar:</strong> ${ev.location || ev.commune}</div>
          <div><strong>Distancias:</strong> ${ev.distances.join(', ')}</div>
          <div><strong>Desnivel:</strong> ${ev.elevation_gain_m ? '+' + ev.elevation_gain_m + ' m' : 'No especificado'}</div>
          <div><strong>Organizador:</strong> ${ev.organizer || 'Organización oficial'}</div>
          <div><strong>Fuente:</strong> ${ev.source ? ev.source.toUpperCase() : 'Pedaleo.cl'}</div>
        </div>

        <div style="display:flex; gap:0.75rem; align-items:center; justify-content:space-between">
          <button class="cal-nav-btn" id="modal-star-btn" style="display:flex; align-items:center; gap:0.4rem">
            ${isPlanned ? '★ Quitar de Mi Temporada' : '☆ Agregar a Mi Temporada'}
          </button>
          <a href="${ev.registration_url || ev.url}" target="_blank" rel="noopener" class="btn-primary-action nav-btn">
            Ir a Inscripciones Oficiales &rarr;
          </a>
        </div>
      `;

      document.getElementById('modal-star-btn')?.addEventListener('click', () => {
        Planner.toggleRace(ev.id);
        this.openDetailModal(ev);
        this.render();
      });

      modal.classList.add('active');
    },

    openPublishModal() {
      const modal = document.getElementById('modal-publish');
      if (modal) modal.classList.add('active');
    },

    closeModals() {
      document.querySelectorAll('.modal-overlay').forEach(ov => ov.classList.remove('active'));
    },

    handlePublishFormSubmit(form) {
      const formData = new FormData(form);
      const name = formData.get('name');
      const date = formData.get('date');
      const region = formData.get('region');
      const commune = formData.get('commune');
      const discipline = formData.get('discipline');
      const distances = formData.get('distances');
      const url = formData.get('url');

      const mailSubject = encodeURIComponent(`[Nueva Carrera] ${name}`);
      const mailBody = encodeURIComponent(
        `Hola Pedaleo.cl,\n\nSolicito agregar la siguiente carrera al calendario:\n\n` +
        `Nombre: ${name}\n` +
        `Fecha: ${date}\n` +
        `Región: ${region}\n` +
        `Comuna: ${commune}\n` +
        `Disciplina: ${discipline}\n` +
        `Distancias: ${distances}\n` +
        `Link de Inscripción: ${url}\n`
      );

      window.open(`mailto:contacto@pedaleo.cl?subject=${mailSubject}&body=${mailBody}`, '_blank');
      alert('¡Gracias por enviar la carrera! Se abrirá tu cliente de correo para validar la solicitud.');
      this.closeModals();
      form.reset();
    }
  };

  App.init();
  window.App = App;
});
