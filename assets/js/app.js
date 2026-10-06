/**
 * Pedaleo.cl - Main Application Controller
 * Sober, clean, fast cycling race catalog for Chile
 */

document.addEventListener('DOMContentLoaded', () => {
  const App = {
    events: [],
    regions: [],
    filteredEvents: [],

    filters: {
      search: '',
      region: '',
      disciplines: [],
      month: '',
      distance: 'all'
    },

    currentView: 'agenda', // 'agenda' | 'calendar'

    async init() {
      await this.loadData();
      this.initFiltersFromURL();
      this.setupDOMListeners();
      this.initStickyOffsets();
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
        this.populateMonthPills();
      } catch (err) {
        console.error('Error cargando los datos:', err);
        const container = document.getElementById('view-agenda');
        if (container) {
          container.innerHTML = `
            <div class="empty-state">
              <p>Error al cargar el calendario. Por favor recarga la página.</p>
            </div>
          `;
        }
      }
    },

    populateRegionSelect() {
      const select = document.getElementById('filter-region');
      if (!select) return;
      select.innerHTML = '<option value="">Todas las regiones</option>';
      this.regions.forEach(reg => {
        const opt = document.createElement('option');
        opt.value = reg.id;
        opt.textContent = reg.short || reg.name;
        select.appendChild(opt);
      });
      if (this.filters.region) {
        select.value = this.filters.region;
      }
    },

    populateMonthPills() {
      const container = document.getElementById('filter-month-group');
      if (!container) return;

      const monthSet = new Set();
      this.events.forEach(ev => {
        if (ev.date && ev.date.length >= 7) {
          monthSet.add(ev.date.substring(0, 7));
        }
      });

      const sortedMonths = Array.from(monthSet).sort();
      const monthNamesShort = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

      let html = '<button class="pill-btn pill-month active" data-month="">Todos</button>';
      sortedMonths.forEach(mKey => {
        const [year, month] = mKey.split('-').map(Number);
        const label = `${monthNamesShort[month - 1]} ${year}`;
        html += `<button class="pill-btn pill-month" data-month="${mKey}">${label}</button>`;
      });

      container.innerHTML = html;

      container.querySelectorAll('.pill-month').forEach(btn => {
        btn.addEventListener('click', (e) => {
          container.querySelectorAll('.pill-month').forEach(b => b.classList.remove('active'));
          e.currentTarget.classList.add('active');
          this.filters.month = e.currentTarget.dataset.month;
          this.applyFilters();
        });
      });

      if (this.filters.month) {
        const target = container.querySelector(`[data-month="${this.filters.month}"]`);
        if (target) {
          container.querySelectorAll('.pill-month').forEach(b => b.classList.remove('active'));
          target.classList.add('active');
        }
      }
    },

    initFiltersFromURL() {
      const params = new URLSearchParams(window.location.search);
      if (params.get('region')) this.filters.region = params.get('region');
      if (params.get('disciplina')) {
        this.filters.disciplines = params.get('disciplina')
          .split(',')
          .map(d => d.trim().toLowerCase())
          .filter(Boolean);
      } else {
        this.filters.disciplines = [];
      }
      if (params.get('mes')) this.filters.month = params.get('mes');
      if (params.get('distancia')) this.filters.distance = params.get('distancia');
      if (params.get('buscar')) this.filters.search = params.get('buscar');
      if (params.get('vista')) this.currentView = params.get('vista');

      const searchInput = document.getElementById('search-input');
      if (searchInput && this.filters.search) {
        searchInput.value = this.filters.search;
      }

      // Discipline pills active state
      const hasDisciplines = this.filters.disciplines.length > 0;
      document.querySelectorAll('.pill-discipline').forEach(b => {
        const dVal = (b.dataset.discipline || '').toLowerCase();
        if (!dVal) {
          b.classList.toggle('active', !hasDisciplines);
        } else {
          b.classList.toggle('active', this.filters.disciplines.includes(dVal));
        }
      });

      // Month pills active state
      if (this.filters.month) {
        document.querySelectorAll('.pill-month').forEach(b => {
          b.classList.toggle('active', b.dataset.month === this.filters.month);
        });
      }

      this.updateViewButtons();
    },

    initStickyOffsets() {
      const updateOffsets = () => {
        const header = document.querySelector('.site-header');
        const filterWrapper = document.querySelector('.filter-wrapper');
        const hHeight = header ? header.offsetHeight : 56;
        const fHeight = filterWrapper ? filterWrapper.offsetHeight : 110;

        document.documentElement.style.setProperty('--header-height', `${hHeight}px`);
        document.documentElement.style.setProperty('--filter-height', `${fHeight}px`);
        document.documentElement.style.setProperty('--sticky-month-top', `${hHeight + fHeight}px`);
      };

      updateOffsets();

      if (window.ResizeObserver) {
        const ro = new ResizeObserver(() => updateOffsets());
        const header = document.querySelector('.site-header');
        const filterWrapper = document.querySelector('.filter-wrapper');
        if (header) ro.observe(header);
        if (filterWrapper) ro.observe(filterWrapper);
      } else {
        window.addEventListener('resize', updateOffsets);
      }
    },

    updateURL() {
      const params = new URLSearchParams();
      if (this.filters.region) params.set('region', this.filters.region);
      if (this.filters.disciplines.length > 0) params.set('disciplina', this.filters.disciplines.join(','));
      if (this.filters.month) params.set('mes', this.filters.month);
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

      // Discipline Pills (Botones interactivos multi-selección no excluyente)
      const discButtons = document.querySelectorAll('.pill-discipline');
      discButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
          const val = (e.currentTarget.dataset.discipline || '').trim().toLowerCase();
          if (!val) {
            // Click en "Todas": limpia selecciones activas
            this.filters.disciplines = [];
          } else {
            // Alternar disciplina individual seleccionada
            const idx = this.filters.disciplines.indexOf(val);
            if (idx > -1) {
              this.filters.disciplines.splice(idx, 1);
            } else {
              this.filters.disciplines.push(val);
            }
          }

          const hasActive = this.filters.disciplines.length > 0;
          discButtons.forEach(b => {
            const bVal = (b.dataset.discipline || '').trim().toLowerCase();
            if (!bVal) {
              b.classList.toggle('active', !hasActive);
            } else {
              b.classList.toggle('active', this.filters.disciplines.includes(bVal));
            }
          });

          this.applyFilters();
        });
      });

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
          this.filters.disciplines = [];
          this.filters.month = '';
          this.filters.distance = 'all';

          if (searchInput) searchInput.value = '';
          if (regionSelect) regionSelect.value = '';

          document.querySelectorAll('.pill-discipline').forEach(b => {
            b.classList.toggle('active', (b.dataset.discipline || '') === '');
          });

          document.querySelectorAll('.pill-month').forEach(b => {
            b.classList.toggle('active', b.dataset.month === '');
          });

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

      // Publicar Carrera Modal
      document.getElementById('nav-publish')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.openPublishModal();
      });

      // Contacto Modal
      document.getElementById('nav-contact')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.openContactModal();
      });
      document.getElementById('footer-contact-link')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.openContactModal();
      });

      // Modals
      document.getElementById('modal-close-detail')?.addEventListener('click', () => this.closeModals());
      document.getElementById('modal-close-publish')?.addEventListener('click', () => this.closeModals());
      document.getElementById('modal-close-contact')?.addEventListener('click', () => this.closeModals());
      document.querySelectorAll('.modal-overlay').forEach(ov => {
        ov.addEventListener('click', (e) => {
          if (e.target === ov) this.closeModals();
        });
      });

      // Form Submit Race -> GitHub Issue
      const publishForm = document.getElementById('publish-race-form');
      if (publishForm) {
        publishForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.handlePublishFormSubmit(publishForm);
        });
      }

      // Form Submit Contact
      const contactForm = document.getElementById('contact-form');
      if (contactForm) {
        contactForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.handleContactFormSubmit(contactForm);
        });
      }

      // Mensajes de validación nativos del navegador en español ("Por favor completa este campo")
      document.addEventListener('invalid', (e) => {
        const el = e.target;
        if (!el || !el.validity) return;

        if (el.validity.valueMissing) {
          el.setCustomValidity('Por favor completa este campo.');
        } else if (el.validity.typeMismatch && el.type === 'email') {
          el.setCustomValidity('Por favor ingresa un correo electrónico válido.');
        } else if (el.validity.typeMismatch && el.type === 'url') {
          el.setCustomValidity('Por favor ingresa un enlace o dirección web válida.');
        } else if (el.validity.patternMismatch) {
          el.setCustomValidity('Por favor ingresa un formato válido.');
        } else {
          el.setCustomValidity('Por favor completa este campo correctamente.');
        }
      }, true);

      document.addEventListener('input', (e) => {
        if (e.target && typeof e.target.setCustomValidity === 'function') {
          e.target.setCustomValidity('');
        }
      }, true);

      document.addEventListener('change', (e) => {
        if (e.target && typeof e.target.setCustomValidity === 'function') {
          e.target.setCustomValidity('');
        }
      }, true);
    },

    updateViewButtons() {
      document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === this.currentView);
      });
    },

    applyFilters() {
      this.filteredEvents = this.events.filter(ev => {
        // Search text
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

        // Discipline (Multi-select no excluyente)
        if (this.filters.disciplines && this.filters.disciplines.length > 0) {
          const match = ev.disciplines.some(d => {
            const dLower = d.toLowerCase();
            return this.filters.disciplines.some(sel => dLower.includes(sel));
          });
          if (!match) return false;
        }

        // Month
        if (this.filters.month && !ev.date.startsWith(this.filters.month)) {
          return false;
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

      // Sort chronologically
      this.filteredEvents.sort((a, b) => a.date.localeCompare(b.date));

      this.updateURL();
      const countEl = document.getElementById('results-count');
      if (countEl) {
        countEl.textContent = `${this.filteredEvents.length} carrera${this.filteredEvents.length === 1 ? '' : 's'}`;
      }

      if (this.currentView === 'map') {
        MapView.updateMarkers(this.filteredEvents);
      } else if (this.currentView === 'calendar') {
        const calContainer = document.getElementById('view-calendar');
        if (calContainer) {
          CalendarView.render(calContainer, this.filteredEvents, (ev) => this.openDetailModal(ev));
        }
      } else {
        const agendaContainer = document.getElementById('view-agenda');
        if (agendaContainer) {
          this.renderAgendaView(agendaContainer);
        }
      }
    },

    render() {
      const countEl = document.getElementById('results-count');
      if (countEl) {
        countEl.textContent = `${this.filteredEvents.length} carrera${this.filteredEvents.length === 1 ? '' : 's'}`;
      }

      const agendaContainer = document.getElementById('view-agenda');
      const mapContainer = document.getElementById('view-map');
      const calContainer = document.getElementById('view-calendar');

      if (!agendaContainer || !mapContainer || !calContainer) return;

      if (this.currentView === 'map') {
        agendaContainer.style.display = 'none';
        mapContainer.style.display = 'block';
        calContainer.style.display = 'none';
        MapView.show(this.filteredEvents, (ev) => this.openDetailModal(ev));
      } else if (this.currentView === 'calendar') {
        agendaContainer.style.display = 'none';
        mapContainer.style.display = 'none';
        calContainer.style.display = 'block';
        CalendarView.render(calContainer, this.filteredEvents, (ev) => this.openDetailModal(ev));
      } else {
        agendaContainer.style.display = 'block';
        mapContainer.style.display = 'none';
        calContainer.style.display = 'none';
        this.renderAgendaView(agendaContainer);
      }
    },

    /**
     * Simplified, Sober Agenda View grouped by Month
     */
    renderAgendaView(container) {
      if (this.filteredEvents.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div style="font-size:2rem; margin-bottom:0.5rem">🚴</div>
            <h3 style="font-weight:700">No se encontraron carreras con los filtros seleccionados</h3>
            <p style="margin-top:0.25rem; font-size:0.9rem">Prueba seleccionando otra región, disciplina o restablece los filtros.</p>
            <button class="cal-btn" style="margin-top:1rem" id="empty-clear-btn">Restablecer Filtros</button>
          </div>
        `;
        document.getElementById('empty-clear-btn')?.addEventListener('click', () => {
          document.getElementById('clear-filters')?.click();
        });
        return;
      }

      // Group by Month ("YYYY-MM")
      const groups = {};
      this.filteredEvents.forEach(ev => {
        const monthKey = ev.date.substring(0, 7);
        if (!groups[monthKey]) groups[monthKey] = [];
        groups[monthKey].push(ev);
      });

      let html = '';
      const monthNames = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
      ];
      const monthShorts = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
      const dowShorts = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];

      for (const [monthKey, monthEvents] of Object.entries(groups)) {
        const [year, month] = monthKey.split('-').map(Number);
        const monthTitle = `${monthNames[month - 1]} ${year}`;

        html += `
          <section class="month-block">
            <header class="month-heading">
              <span class="month-name">${monthTitle}</span>
              <span class="month-count">${monthEvents.length} carrera${monthEvents.length === 1 ? '' : 's'}</span>
            </header>
            <div class="month-card">
        `;

        monthEvents.forEach(ev => {
          const dObj = new Date(ev.date + 'T12:00:00');
          const dayNum = dObj.getDate();
          const monthShort = monthShorts[dObj.getMonth()];
          const dowShort = dowShorts[dObj.getDay()];

          const disciplinesList = Array.isArray(ev.disciplines) && ev.disciplines.length > 0
            ? ev.disciplines
            : ['MTB'];

          const formatDisc = (d) => {
            const clean = (d || 'MTB').trim();
            const lower = clean.toLowerCase();
            if (lower.includes('ultra') || lower.includes('bikepacking')) return { key: 'ultra', label: 'Ultra', full: clean };
            if (lower.includes('enduro')) return { key: 'enduro', label: 'Enduro', full: clean };
            if (lower.includes('descenso') || lower.includes('downhill') || lower.includes('dh')) return { key: 'enduro', label: 'DH', full: clean };
            if (lower.includes('gravel')) return { key: 'gravel', label: 'Gravel', full: clean };
            if (lower.includes('ruta') || lower.includes('carretera')) return { key: 'ruta', label: 'Ruta', full: clean };
            if (lower.includes('mtb') || lower.includes('mountain')) return { key: 'mtb', label: 'MTB', full: clean };
            if (lower.includes('cicloturismo')) return { key: 'mtb', label: 'Turismo', full: clean };
            return { key: lower.split('/')[0], label: clean.length > 7 ? clean.substring(0, 6) : clean, full: clean };
          };

          const formattedDiscs = disciplinesList.map(formatDisc);
          const discBadgesHtml = formattedDiscs.map(item => {
            return `<span class="badge-discipline badge-${item.key}" title="${item.full}">${item.label}</span>`;
          }).join('');

          const distText = ev.distances && ev.distances.length && ev.distances[0] !== 'Ver bases'
            ? ev.distances.join(' • ')
            : '';
          const elevText = ev.elevation_gain_m ? `+${ev.elevation_gain_m.toLocaleString('es-CL')}m` : '';

          let metricsHtml = '';
          if (distText) metricsHtml += `<span class="dist-meta">🏁 ${distText}</span>`;
          if (elevText) metricsHtml += `<span class="elev-meta">⛰️ ${elevText}</span>`;

          // Region official name without numbers
          const regName = ev.region_name || (this.regions.find(r => r.id === ev.region)?.short) || ev.region;

          // Clean locality to avoid repeating region
          let rawLoc = ev.commune || ev.location || '';
          let cleanLoc = rawLoc
            .split(',')[0]
            .split('-')[0]
            .replace(/\b(Regi[oó]n\s+[A-Za-z\s]+|RM|XV|XVI|XIV|XII|XI|VIII|VII|VI|IV|III|II|I|X|V)\b/gi, '')
            .trim();
          if (!cleanLoc) cleanLoc = regName;

          html += `
            <article class="event-item" data-id="${ev.id}">
              <!-- Columna 1: Fecha (ej. Sáb 10) -->
              <div class="event-col-date" title="${dowShort} ${dayNum} de ${monthTitle}">
                <span class="chip-dow">${dowShort}</span>
                <span class="chip-day">${dayNum}</span>
              </div>

              <!-- Columna 2: Título de Carrera y Subtítulo de Disciplinas + Métricas -->
              <div class="event-col-title">
                <a href="#" class="event-link" data-id="${ev.id}" title="${ev.name}">${ev.name}</a>
                <div class="event-subtitle-row">
                  <div class="event-tags-sub" title="Disciplinas: ${disciplinesList.join(', ')}">
                    ${discBadgesHtml}
                  </div>
                  ${metricsHtml ? `<span class="meta-separator">•</span> ${metricsHtml}` : ''}
                </div>
              </div>

              <!-- Columna 3: Ubicación y Región (alineada independientemente) -->
              <div class="event-col-loc">
                <span class="meta-location">📍 ${cleanLoc}</span>
                <span class="badge-reg">${regName}</span>
              </div>

              <!-- Columna 4: Acciones -->
              <div class="event-col-actions">
                <div class="dropdown-calendar">
                  <button class="btn-cal-export" title="Agendar en Google o Apple Calendar">
                    📅 <span class="hide-mobile">Agendar</span>
                  </button>
                  <div class="cal-dropdown-menu">
                    <button class="cal-dropdown-item btn-export-google" data-id="${ev.id}">
                      Google Calendar
                    </button>
                    <button class="cal-dropdown-item btn-export-apple" data-id="${ev.id}">
                      Apple / Outlook (.ics)
                    </button>
                  </div>
                </div>

                <a href="${ev.registration_url || ev.url}" target="_blank" rel="noopener" class="btn-action-primary">
                  Inscripción &rarr;
                </a>
              </div>
            </article>
          `;
        });

        html += `
            </div>
          </section>
        `;
      }

      container.innerHTML = html;
      this.attachEventRowListeners(container);
    },

    attachEventRowListeners(container) {
      // Event row click -> Detail Modal (if not clicking on link or button)
      container.querySelectorAll('.event-item').forEach(item => {
        item.addEventListener('click', (e) => {
          if (e.target.closest('a') || e.target.closest('button') || e.target.closest('.dropdown-calendar')) {
            return;
          }
          const id = item.dataset.id;
          const ev = this.events.find(it => it.id === id);
          if (ev) this.openDetailModal(ev);
        });
      });

      // Event title click -> Detail Modal
      container.querySelectorAll('.event-link').forEach(link => {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          const id = e.currentTarget.dataset.id;
          const ev = this.events.find(item => item.id === id);
          if (ev) this.openDetailModal(ev);
        });
      });

      // Per-Race Google Calendar Export
      container.querySelectorAll('.btn-export-google').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const id = e.currentTarget.dataset.id;
          const ev = this.events.find(item => item.id === id);
          if (ev) CalendarExporter.exportToGoogle(ev);
        });
      });

      // Per-Race Apple Calendar (.ics) Export
      container.querySelectorAll('.btn-export-apple').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const id = e.currentTarget.dataset.id;
          const ev = this.events.find(item => item.id === id);
          if (ev) CalendarExporter.exportToICS(ev);
        });
      });
    },

    openDetailModal(ev) {
      const modal = document.getElementById('modal-detail');
      const body = document.getElementById('modal-detail-body');
      const title = document.getElementById('modal-detail-title');

      if (!modal || !body || !title) return;

      title.textContent = ev.name;

      const regName = ev.region_name || (this.regions.find(r => r.id === ev.region)?.short) || ev.region;

      const modalBadgesHtml = (Array.isArray(ev.disciplines) && ev.disciplines.length > 0 ? ev.disciplines : ['MTB']).map(d => {
        const dKey = d.toLowerCase().split('/')[0].trim();
        return `<span class="badge-discipline badge-${dKey}">${d}</span>`;
      }).join(' ');

      body.innerHTML = `
        <div style="display:flex; flex-wrap:wrap; gap:0.4rem; margin-bottom:1rem">
          ${modalBadgesHtml}
          <span class="badge-reg">${regName}</span>
          ${ev.price_type === 'free' ? '<span class="badge-reg" style="color:#166534; font-weight:700">GRATIS</span>' : ''}
        </div>

        <p style="margin-bottom:1.25rem; font-size:0.92rem; color:#334155; line-height:1.6">
          ${ev.description || 'Sin descripción detallada disponible.'}
        </p>

        <div class="detail-grid">
          <div><strong>Fecha:</strong> ${ev.date} ${ev.end_date && ev.end_date !== ev.date ? 'al ' + ev.end_date : ''}</div>
          <div><strong>Lugar:</strong> ${ev.location || ev.commune}</div>
          <div><strong>Distancias:</strong> ${ev.distances ? ev.distances.join(', ') : 'Ver bases'}</div>
          <div><strong>Desnivel:</strong> ${ev.elevation_gain_m ? '+' + ev.elevation_gain_m + ' m' : 'No especificado'}</div>
          <div><strong>Organizador:</strong> ${ev.organizer || 'Organización oficial'}</div>
          <div><strong>Fuente:</strong> ${ev.source ? ev.source.toUpperCase() : 'Pedaleo.cl'}</div>
        </div>

        <div style="display:flex; flex-wrap:wrap; gap:0.6rem; align-items:center; justify-content:space-between; margin-top:1.5rem">
          <div style="display:flex; gap:0.4rem">
            <button class="cal-btn-mini" id="modal-export-google">📅 Google Calendar</button>
            <button class="cal-btn-mini" id="modal-export-apple">🍏 Apple Calendar (.ics)</button>
          </div>
          <a href="${ev.registration_url || ev.url}" target="_blank" rel="noopener" class="btn-action-primary">
            Inscripción Oficial &rarr;
          </a>
        </div>
      `;

      document.getElementById('modal-export-google')?.addEventListener('click', () => {
        CalendarExporter.exportToGoogle(ev);
      });

      document.getElementById('modal-export-apple')?.addEventListener('click', () => {
        CalendarExporter.exportToICS(ev);
      });

      modal.classList.add('active');
    },

    openPublishModal() {
      const modal = document.getElementById('modal-publish');
      const feedback = document.getElementById('publish-feedback');
      if (feedback) feedback.style.display = 'none';
      if (modal) modal.classList.add('active');
    },

    openContactModal() {
      const modal = document.getElementById('modal-contact');
      const feedback = document.getElementById('contact-feedback');
      if (feedback) feedback.style.display = 'none';
      if (modal) modal.classList.add('active');
    },

    handleContactFormSubmit(form) {
      const formData = new FormData(form);
      const name = formData.get('name') || '';
      const email = formData.get('email') || '';
      const subject = formData.get('subject') || 'Contacto Pedaleo.cl';
      const message = formData.get('message') || '';

      const mailtoSubject = encodeURIComponent(`[Pedaleo.cl] ${subject} - ${name}`);
      const mailtoBody = encodeURIComponent(
        `Nombre: ${name}\n` +
        `Email: ${email}\n` +
        `Motivo: ${subject}\n\n` +
        `Mensaje:\n${message}\n\n` +
        `---\nEnviado desde Pedaleo.cl`
      );

      // Open email client
      window.location.href = `mailto:contacto@pedaleo.cl?subject=${mailtoSubject}&body=${mailtoBody}`;

      const feedback = document.getElementById('contact-feedback');
      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = '#dcfce7';
        feedback.style.color = '#166534';
        feedback.style.border = '1px solid #bbf7d0';
        feedback.innerHTML = `¡Gracias por tu mensaje, <strong>${name}</strong>! Se ha generado tu correo hacia <strong>contacto@pedaleo.cl</strong>.`;
      }

      setTimeout(() => {
        this.closeModals();
        form.reset();
        if (feedback) feedback.style.display = 'none';
      }, 3500);
    },

    closeModals() {
      document.querySelectorAll('.modal-overlay').forEach(ov => ov.classList.remove('active'));
    },

    /**
     * Handles race submission as a contact email to contacto@pedaleo.cl
     * No longer opens any external GitHub page
     */
    handlePublishFormSubmit(form) {
      const formData = new FormData(form);
      const name = formData.get('name') || '';
      const date = formData.get('date') || '';
      const region = formData.get('region') || '';
      const commune = formData.get('commune') || '';
      const rawDisciplines = formData.getAll('discipline');
      const discipline = rawDisciplines.length > 0 ? rawDisciplines.join(', ') : 'MTB';
      const distances = formData.get('distances') || '';
      let url = (formData.get('url') || '').trim();
      const contact = formData.get('contact') || 'No provisto';

      if (url && !/^https?:\/\//i.test(url)) {
        url = 'https://' + url;
      }

      const mailtoSubject = encodeURIComponent(`[Nueva Carrera] ${name} (${date})`);
      const mailtoBody = encodeURIComponent(
        `Solicitud de publicación de nueva carrera en Pedaleo.cl:\n\n` +
        `- Nombre de la Carrera: ${name}\n` +
        `- Fecha: ${date}\n` +
        `- Región: ${region}\n` +
        `- Comuna / Lugar: ${commune}\n` +
        `- Disciplinas / Formatos: ${discipline}\n` +
        `- Distancias: ${distances || 'Ver bases'}\n` +
        `- Link / Web de Inscripción: ${url}\n` +
        `- Contacto / Productora: ${contact}\n\n` +
        `---\nEnviado desde el formulario oficial de Pedaleo.cl`
      );

      // Open email client
      window.location.href = `mailto:contacto@pedaleo.cl?subject=${mailtoSubject}&body=${mailtoBody}`;

      const feedback = document.getElementById('publish-feedback');
      if (feedback) {
        feedback.style.display = 'block';
        feedback.style.background = '#dcfce7';
        feedback.style.color = '#166534';
        feedback.style.border = '1px solid #bbf7d0';
        feedback.innerHTML = `¡Solicitud enviada! Se ha preparado tu correo a <strong>contacto@pedaleo.cl</strong> para revisar y publicar <strong>${name}</strong>.`;
      }

      setTimeout(() => {
        this.closeModals();
        form.reset();
        if (feedback) feedback.style.display = 'none';
      }, 3500);
    }
  };

  App.init();
  window.App = App;
});
