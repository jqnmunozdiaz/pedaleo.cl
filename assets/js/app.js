/**
 * Pedaleo.cl - Main Application Controller
 * Sober, clean, fast cycling race catalog for Chile
 */

document.addEventListener('DOMContentLoaded', () => {
  const VALID_VIEWS = ['agenda', 'map', 'calendar'];
  const MODAL_FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  const App = {
    events: [],
    regions: [],
    filteredEvents: [],
    today: Utils.todayStr(),

    filters: {
      search: '',
      region: '',
      disciplines: [],
      months: [],
      showPast: false,
      showUnlocated: false
    },

    currentView: 'agenda', // 'agenda' | 'map' | 'calendar'
    lastFocused: null,

    async init() {
      await this.loadData();
      this.initFiltersFromURL();
      this.populateMonthPills();
      this.updateUnlocatedCount();
      this.setupDOMListeners();
      this.initStickyOffsets();
      this.applyFilters();
      this.openEventFromHash();
      this.injectStructuredData();
    },

    async loadData() {
      try {
        const [eventsRes, regionsRes] = await Promise.all([
          fetch('data/events.json', { cache: 'no-cache' }),
          fetch('data/regions.json', { cache: 'no-cache' })
        ]);
        if (!eventsRes.ok || !regionsRes.ok) throw new Error('Respuesta HTTP no válida');
        this.events = await eventsRes.json();
        this.showDataDate(eventsRes.headers.get('Last-Modified'));
        this.regions = await regionsRes.json();
        this.events.forEach(ev => {
          ev._search = Utils.normalize(
            [ev.name, ev.location, ev.commune, ev.region_name, ev.organizer, ev.description].join(' ')
          );
        });
        this.populateRegionSelect();
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
        const countEl = document.getElementById('results-count');
        if (countEl) countEl.textContent = 'sin datos';
      }
    },

    /** "Datos actualizados el 13 de octubre de 2026" from the data file's Last-Modified header. */
    showDataDate(lastModified) {
      const el = document.getElementById('footer-updated');
      const date = lastModified ? new Date(lastModified) : null;
      if (!el || !date || isNaN(date)) return;
      el.textContent = `Datos actualizados el ${date.getDate()} de ${Utils.MONTH_NAMES[date.getMonth()].toLowerCase()} de ${date.getFullYear()}.`;
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

    /** True when the sources did not give a confirmed place for the race. */
    isUnlocated(ev) {
      return ev.location_unverified === true || !ev.region;
    },

    /** Events that the month pills / default listing work with (hides finished / unlocated races unless requested). */
    baseEvents() {
      return this.events.filter(ev =>
        ev.status !== 'cancelled' &&
        (this.filters.showPast || !Utils.isPast(ev, this.today)) &&
        (this.filters.showUnlocated || !this.isUnlocated(ev))
      );
    },

    updateUnlocatedCount() {
      const el = document.getElementById('unlocated-count');
      if (!el) return;
      const n = this.events.filter(ev => this.isUnlocated(ev) && (this.filters.showPast || !Utils.isPast(ev, this.today))).length;
      el.textContent = ` (${n})`;
    },

    populateMonthPills() {
      const container = document.getElementById('filter-month-group');
      if (!container) return;

      const monthSet = new Set();
      this.baseEvents().forEach(ev => {
        if (ev.date && ev.date.length >= 7) monthSet.add(ev.date.substring(0, 7));
      });
      const sortedMonths = Array.from(monthSet).sort();

      // Drop selected months that no longer exist (e.g. after hiding past races)
      this.filters.months = this.filters.months.filter(m => monthSet.has(m));

      const hasActiveMonths = this.filters.months.length > 0;
      let html = `<button type="button" class="pill-btn pill-month ${hasActiveMonths ? '' : 'active'}" data-month="">Todos</button>`;
      sortedMonths.forEach(mKey => {
        const [year, month] = mKey.split('-').map(Number);
        const label = `${Utils.MONTH_SHORT[month - 1]} ${year}`;
        const isActive = this.filters.months.includes(mKey);
        html += `<button type="button" class="pill-btn pill-month ${isActive ? 'active' : ''}" data-month="${mKey}">${label}</button>`;
      });
      container.innerHTML = html;
    },

    syncMonthPills() {
      const hasSelected = this.filters.months.length > 0;
      document.querySelectorAll('.pill-month').forEach(b => {
        const bVal = (b.dataset.month || '').trim();
        b.classList.toggle('active', bVal ? this.filters.months.includes(bVal) : !hasSelected);
      });
    },

    syncDisciplinePills() {
      const hasActive = this.filters.disciplines.length > 0;
      document.querySelectorAll('.pill-discipline').forEach(b => {
        const val = Utils.normalize((b.dataset.discipline || '').trim());
        b.classList.toggle('active', val ? this.filters.disciplines.includes(val) : !hasActive);
      });
    },

    initFiltersFromURL() {
      const params = new URLSearchParams(window.location.search);
      const urlRegion = (params.get('region') || '').trim().toUpperCase();
      if (urlRegion && this.regions.some(r => r.id === urlRegion)) this.filters.region = urlRegion;
      const regionSelect = document.getElementById('filter-region');
      if (regionSelect) regionSelect.value = this.filters.region;
      if (params.get('disciplina')) {
        this.filters.disciplines = params.get('disciplina')
          .split(',')
          .map(d => Utils.normalize(d.trim()))
          .filter(Boolean);
      }
      if (params.get('meses')) {
        this.filters.months = params.get('meses').split(',').map(m => m.trim()).filter(Boolean);
      } else if (params.get('mes')) {
        this.filters.months = [params.get('mes').trim()];
      }
      if (params.get('buscar')) this.filters.search = Utils.normalize(params.get('buscar').trim());
      if (params.get('pasadas') === '1') this.filters.showPast = true;
      if (params.get('sinubicacion') === '1') this.filters.showUnlocated = true;
      if (VALID_VIEWS.includes(params.get('vista'))) this.currentView = params.get('vista');

      const searchInput = document.getElementById('search-input');
      if (searchInput && params.get('buscar')) searchInput.value = params.get('buscar').trim();

      const pastToggle = document.getElementById('toggle-past');
      if (pastToggle) pastToggle.checked = this.filters.showPast;
      const unlocatedToggle = document.getElementById('toggle-unlocated');
      if (unlocatedToggle) unlocatedToggle.checked = this.filters.showUnlocated;

      this.syncDisciplinePills();
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
      if (this.filters.months.length > 0) params.set('meses', this.filters.months.join(','));
      const searchInput = document.getElementById('search-input');
      const rawSearch = searchInput ? searchInput.value.trim() : this.filters.search;
      if (rawSearch) params.set('buscar', rawSearch);
      if (this.filters.showPast) params.set('pasadas', '1');
      if (this.filters.showUnlocated) params.set('sinubicacion', '1');
      if (this.currentView !== 'agenda') params.set('vista', this.currentView);

      const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '') + window.location.hash;
      window.history.replaceState({}, '', newUrl);
    },

    setupDOMListeners() {
      // Search Input
      const searchInput = document.getElementById('search-input');
      if (searchInput) {
        searchInput.addEventListener('input', (e) => {
          this.filters.search = Utils.normalize(e.target.value.trim());
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

      // Discipline Pills (multi-selección no excluyente)
      document.querySelectorAll('.pill-discipline').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const val = Utils.normalize((e.currentTarget.dataset.discipline || '').trim());
          if (!val) {
            this.filters.disciplines = [];
          } else {
            const idx = this.filters.disciplines.indexOf(val);
            if (idx > -1) this.filters.disciplines.splice(idx, 1);
            else this.filters.disciplines.push(val);
          }
          this.syncDisciplinePills();
          this.applyFilters();
        });
      });

      // Month Pills (delegated: the pills are rebuilt when the past-races toggle changes)
      document.getElementById('filter-month-group')?.addEventListener('click', (e) => {
        const btn = e.target.closest('.pill-month');
        if (!btn) return;
        const val = (btn.dataset.month || '').trim();
        if (!val) {
          this.filters.months = [];
        } else {
          const idx = this.filters.months.indexOf(val);
          if (idx > -1) this.filters.months.splice(idx, 1);
          else this.filters.months.push(val);
        }
        this.syncMonthPills();
        this.applyFilters();
      });

      // Show / hide finished races
      document.getElementById('toggle-past')?.addEventListener('change', (e) => {
        this.filters.showPast = e.target.checked;
        this.populateMonthPills();
        this.updateUnlocatedCount();
        this.applyFilters();
      });

      // Show / hide races whose location is not confirmed
      document.getElementById('toggle-unlocated')?.addEventListener('change', (e) => {
        this.filters.showUnlocated = e.target.checked;
        this.populateMonthPills();
        this.applyFilters();
      });

      // Clear Filters
      document.getElementById('clear-filters')?.addEventListener('click', () => {
        this.filters.search = '';
        this.filters.region = '';
        this.filters.disciplines = [];
        this.filters.months = [];
        this.filters.showPast = false;
        this.filters.showUnlocated = false;

        if (searchInput) searchInput.value = '';
        if (regionSelect) regionSelect.value = '';
        const pastToggle = document.getElementById('toggle-past');
        if (pastToggle) pastToggle.checked = false;
        const unlocatedToggle = document.getElementById('toggle-unlocated');
        if (unlocatedToggle) unlocatedToggle.checked = false;
        this.updateUnlocatedCount();

        this.syncDisciplinePills();
        this.populateMonthPills();
        this.applyFilters();
      });

      // View Switcher Buttons
      document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          this.currentView = e.currentTarget.dataset.view;
          this.updateViewButtons();
          this.render();
          this.updateURL();
        });
      });

      // Publicar Carrera / Contacto
      document.getElementById('nav-publish')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.openPublishModal();
      });
      document.getElementById('nav-contact')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.openContactModal();
      });
      document.getElementById('footer-contact-link')?.addEventListener('click', (e) => {
        e.preventDefault();
        this.openContactModal();
      });

      // Modals: close buttons, backdrop click, Escape, focus trap
      document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', () => this.closeModals());
      });
      document.querySelectorAll('.modal-overlay').forEach(ov => {
        ov.addEventListener('click', (e) => {
          if (e.target === ov) this.closeModals();
        });
      });
      document.addEventListener('keydown', (e) => this.handleModalKeys(e));
      document.addEventListener('click', () => this.closeCalendarMenus());
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') this.closeCalendarMenus(); });

      // Back/forward or a pasted #carrera=<id> link while the page is open
      window.addEventListener('hashchange', () => {
        if (window.location.hash.startsWith('#carrera=')) this.openEventFromHash();
        else if (document.querySelector('#modal-detail.active')) this.closeModals({ restoreFocus: false });
      });

      // Forms
      const publishForm = document.getElementById('publish-race-form');
      if (publishForm) {
        publishForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.handlePublishFormSubmit(publishForm);
        });
      }
      const contactForm = document.getElementById('contact-form');
      if (contactForm) {
        contactForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.handleContactFormSubmit(contactForm);
        });
      }

      // Mensajes de validación nativos del navegador en español
      document.addEventListener('invalid', (e) => {
        const el = e.target;
        if (!el || !el.validity) return;

        if (el.validity.valueMissing) {
          el.setCustomValidity(el.tagName === 'SELECT' ? 'Por favor selecciona una opción.' : 'Por favor completa este campo.');
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

      const clearValidity = (e) => {
        if (e.target && typeof e.target.setCustomValidity === 'function') {
          e.target.setCustomValidity('');
        }
      };
      document.addEventListener('input', clearValidity, true);
      document.addEventListener('change', clearValidity, true);

      // Keep "today" fresh if the tab stays open past midnight
      document.addEventListener('visibilitychange', () => {
        const now = Utils.todayStr();
        if (!document.hidden && now !== this.today) {
          this.today = now;
          this.populateMonthPills();
          this.applyFilters();
        }
      });
    },

    updateViewButtons() {
      document.querySelectorAll('.view-btn').forEach(btn => {
        const active = btn.dataset.view === this.currentView;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-pressed', String(active));
      });
    },

    applyFilters() {
      const f = this.filters;
      const showPast = f.showPast;

      this.filteredEvents = this.events.filter(ev => {
        if (ev.status === 'cancelled') return false; // suspended / cancelled races are not listed
        if (!showPast && Utils.isPast(ev, this.today)) return false;
        const unlocated = this.isUnlocated(ev);
        if (unlocated && !f.showUnlocated) return false;
        if (f.search && !ev._search.includes(f.search)) return false;
        // Races without a confirmed region can't be excluded by region: they stay while "sin ubicación" is on
        if (f.region && !unlocated && ev.region !== f.region) return false;

        if (f.disciplines.length > 0) {
          const match = (ev.disciplines || []).some(d => {
            const dNorm = Utils.normalize(d);
            return f.disciplines.some(sel => dNorm.includes(sel));
          });
          if (!match) return false;
        }

        if (f.months.length > 0 && !f.months.some(m => ev.date.startsWith(m))) return false;

        return true;
      });

      this.filteredEvents.sort((a, b) => a.date.localeCompare(b.date) || a.name.localeCompare(b.name));

      CalendarView.resetMonth();
      this.updateURL();
      this.render();
    },

    updateResultsCount() {
      const countEl = document.getElementById('results-count');
      if (countEl) {
        const n = this.filteredEvents.length;
        countEl.textContent = `${n} carrera${n === 1 ? '' : 's'}`;
      }
    },

    render() {
      this.updateResultsCount();

      const agendaContainer = document.getElementById('view-agenda');
      const mapContainer = document.getElementById('view-map');
      const calContainer = document.getElementById('view-calendar');
      if (!agendaContainer || !mapContainer || !calContainer) return;

      const mapWasHidden = mapContainer.style.display === 'none';
      agendaContainer.style.display = this.currentView === 'agenda' ? 'block' : 'none';
      mapContainer.style.display = this.currentView === 'map' ? 'block' : 'none';
      calContainer.style.display = this.currentView === 'calendar' ? 'block' : 'none';

      if (this.currentView === 'map') {
        // Races with no confirmed place can't be pinned
        const mappable = this.filteredEvents.filter(ev => !this.isUnlocated(ev));
        const hidden = this.filteredEvents.length - mappable.length;
        const note = document.getElementById('map-unlocated-note');
        if (note) {
          note.style.display = hidden > 0 ? '' : 'none';
          note.textContent = hidden > 0
            ? `${hidden} carrera${hidden === 1 ? '' : 's'} sin ubicación confirmada no se muestra${hidden === 1 ? '' : 'n'} en el mapa (están en la vista Lista y Mes).`
            : '';
        }
        if (mapWasHidden) MapView.show(mappable, (ev) => this.openDetailModal(ev));
        else MapView.updateMarkers(mappable);
      } else if (this.currentView === 'calendar') {
        CalendarView.render(calContainer, this.filteredEvents, (ev) => this.openDetailModal(ev));
      } else {
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
            <div class="empty-state-icon">🚴</div>
            <h3>No se encontraron carreras con los filtros seleccionados</h3>
            <p>Prueba seleccionando otra región, disciplina o restablece los filtros.</p>
            <button type="button" class="cal-btn" id="empty-clear-btn">Restablecer Filtros</button>
          </div>
        `;
        document.getElementById('empty-clear-btn')?.addEventListener('click', () => {
          document.getElementById('clear-filters')?.click();
        });
        return;
      }

      // Group by Month ("YYYY-MM"), keeping chronological order
      const groups = new Map();
      this.filteredEvents.forEach(ev => {
        const monthKey = ev.date.substring(0, 7);
        if (!groups.has(monthKey)) groups.set(monthKey, []);
        groups.get(monthKey).push(ev);
      });

      let html = '';
      for (const [monthKey, monthEvents] of groups) {
        const [year, month] = monthKey.split('-').map(Number);
        const monthTitle = `${Utils.MONTH_NAMES[month - 1]} ${year}`;

        html += `
          <section class="month-block">
            <header class="month-heading">
              <span class="month-name">${monthTitle}</span>
              <span class="month-count">${monthEvents.length} carrera${monthEvents.length === 1 ? '' : 's'}</span>
            </header>
            <div class="month-card">
        `;

        monthEvents.forEach(ev => {
          const dObj = Utils.parseDate(ev.date);
          const dayNum = dObj.getDate();
          const dowShort = Utils.DOW_SHORT[dObj.getDay()];
          const isPast = Utils.isPast(ev, this.today);
          const isOngoing = !isPast && ev.date <= this.today && Utils.eventEnd(ev) >= this.today;

          const disciplinesList = Array.isArray(ev.disciplines) && ev.disciplines.length > 0 ? ev.disciplines : ['MTB'];
          const discBadgesHtml = disciplinesList.map(d => {
            const item = Utils.disciplineInfo(d);
            return `<span class="badge-discipline badge-${item.key}" title="${Utils.esc(item.full)}">${Utils.esc(item.label)}</span>`;
          }).join('');

          const distText = Utils.distanceText(ev);
          const elevText = ev.elevation_gain_m ? `+${ev.elevation_gain_m.toLocaleString('es-CL')}m` : '';

          let metricsHtml = '';
          if (distText) metricsHtml += `<span class="dist-meta">🏁 ${Utils.esc(distText)}</span>`;
          if (elevText) metricsHtml += `<span class="elev-meta" title="Desnivel acumulado${(ev.distances || []).length > 1 ? ' (la ruta con más desnivel)' : ''}">⛰️ ${elevText}</span>`;

          const unlocated = this.isUnlocated(ev);
          const regName = unlocated
            ? 'Sin región'
            : ev.region_name || (this.regions.find(r => r.id === ev.region)?.short) || ev.region;
          const hasPlaceText = unlocated && ev.location && ev.location !== 'Ubicación por confirmar';
          const cleanLoc = unlocated
            ? (hasPlaceText ? `${ev.location} (por confirmar)` : 'Ubicación por confirmar')
            : Utils.cleanLocality(ev, regName);
          const stateTag = isPast
            ? '<span class="event-state-tag">Finalizada</span>'
            : ev.status === 'postponed' ? '<span class="event-state-tag is-warn" title="Los organizadores anunciaron un cambio de fecha: confirma en su sitio">Reprogramada</span>'
            : isOngoing ? '<span class="event-state-tag is-live">En curso</span>' : '';

          html += `
            <article class="event-item${isPast ? ' is-past' : ''}" data-id="${Utils.esc(ev.id)}">
              <div class="event-col-date" title="${Utils.esc(Utils.formatDateLong(ev))}">
                <span class="chip-dow">${dowShort}</span>
                <span class="chip-day">${dayNum}</span>
              </div>

              <div class="event-col-title">
                <a href="#carrera=${encodeURIComponent(ev.id)}" class="event-link" data-id="${Utils.esc(ev.id)}" title="${Utils.esc(ev.name)}">${Utils.esc(ev.name)}</a>
                <div class="event-subtitle-row">
                  <div class="event-tags-sub" title="Disciplinas: ${Utils.esc(disciplinesList.join(', '))}">
                    ${discBadgesHtml}
                  </div>
                  ${stateTag}
                  ${metricsHtml ? `<span class="meta-separator">•</span> ${metricsHtml}` : ''}
                </div>
              </div>

              <div class="event-col-loc">
                <span class="meta-location">📍 ${Utils.esc(cleanLoc)}</span>
                <span class="badge-reg${unlocated ? ' badge-unlocated' : ''}">${Utils.esc(regName)}</span>
              </div>

              <div class="event-col-actions">
                <div class="dropdown-calendar">
                  <button type="button" class="btn-cal-export" title="Agendar en Google o Apple Calendar" aria-haspopup="true">
                    📅 <span class="hide-mobile">Agendar</span>
                  </button>
                  <div class="cal-dropdown-menu">
                    <button type="button" class="cal-dropdown-item btn-export-google" data-id="${Utils.esc(ev.id)}">
                      Google Calendar
                    </button>
                    <button type="button" class="cal-dropdown-item btn-export-apple" data-id="${Utils.esc(ev.id)}">
                      Apple / Outlook (.ics)
                    </button>
                  </div>
                </div>

                <a href="${Utils.eventHref(ev)}" target="_blank" rel="noopener" class="btn-action-primary">
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

    closeCalendarMenus() {
      document.querySelectorAll('.dropdown-calendar.is-open').forEach(el => {
        el.classList.remove('is-open');
        el.querySelector('.btn-cal-export')?.setAttribute('aria-expanded', 'false');
      });
    },

    findEvent(id) {
      return this.events.find(it => it.id === id);
    },

    attachEventRowListeners(container) {
      // Event row click -> Detail Modal (if not clicking on link or button)
      container.querySelectorAll('.event-item').forEach(item => {
        item.addEventListener('click', (e) => {
          if (e.target.closest('a') || e.target.closest('button') || e.target.closest('.dropdown-calendar')) return;
          const ev = this.findEvent(item.dataset.id);
          if (ev) this.openDetailModal(ev);
        });
      });

      // Event title click -> Detail Modal
      container.querySelectorAll('.event-link').forEach(link => {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          const ev = this.findEvent(e.currentTarget.dataset.id);
          if (ev) this.openDetailModal(ev);
        });
      });

      // The menu also opens on hover/focus via CSS; the click toggle is for touch screens
      // (iOS Safari does not focus a button when it is tapped).
      container.querySelectorAll('.btn-cal-export').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const wrap = btn.closest('.dropdown-calendar');
          const willOpen = !wrap.classList.contains('is-open');
          this.closeCalendarMenus();
          wrap.classList.toggle('is-open', willOpen);
          btn.setAttribute('aria-expanded', String(willOpen));
        });
      });

      container.querySelectorAll('.btn-export-google').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.closeCalendarMenus();
          const ev = this.findEvent(e.currentTarget.dataset.id);
          if (ev) CalendarExporter.exportToGoogle(ev);
        });
      });

      container.querySelectorAll('.btn-export-apple').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.closeCalendarMenus();
          const ev = this.findEvent(e.currentTarget.dataset.id);
          if (ev) CalendarExporter.exportToICS(ev);
        });
      });
    },

    // ---------------------------------------------------------------- Modals

    showModal(id) {
      const modal = document.getElementById(id);
      if (!modal) return;
      if (!document.querySelector('.modal-overlay.active')) {
        this.lastFocused = document.activeElement;
      }
      this.closeModals({ restoreFocus: false, keepHash: true });
      modal.classList.add('active');
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('modal-open');
      const first = modal.querySelector('.modal-close-btn') || modal.querySelector(MODAL_FOCUSABLE);
      if (first) first.focus({ preventScroll: true });
    },

    closeModals({ restoreFocus = true, keepHash = false } = {}) {
      const wasOpen = document.querySelector('.modal-overlay.active');
      document.querySelectorAll('.modal-overlay').forEach(ov => {
        ov.classList.remove('active');
        ov.setAttribute('aria-hidden', 'true');
      });
      document.body.classList.remove('modal-open');

      if (!keepHash && window.location.hash.startsWith('#carrera=')) {
        window.history.replaceState({}, '', window.location.pathname + window.location.search);
      }
      if (wasOpen && restoreFocus && this.lastFocused && document.contains(this.lastFocused)) {
        this.lastFocused.focus({ preventScroll: true });
      }
    },

    handleModalKeys(e) {
      const modal = document.querySelector('.modal-overlay.active');
      if (!modal) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        this.closeModals();
        return;
      }

      if (e.key === 'Tab') {
        const focusable = Array.from(modal.querySelectorAll(MODAL_FOCUSABLE)).filter(el => el.offsetParent !== null);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },

    openEventFromHash() {
      const match = window.location.hash.match(/^#carrera=(.+)$/);
      if (!match) return;
      const ev = this.findEvent(decodeURIComponent(match[1]));
      if (ev) this.openDetailModal(ev);
    },

    openDetailModal(ev) {
      const body = document.getElementById('modal-detail-body');
      const title = document.getElementById('modal-detail-title');
      if (!body || !title) return;

      title.textContent = ev.name;

      const unlocated = this.isUnlocated(ev);
      const regName = unlocated
        ? 'Ubicación por confirmar'
        : ev.region_name || (this.regions.find(r => r.id === ev.region)?.short) || ev.region;
      const isPast = Utils.isPast(ev, this.today);

      const modalBadgesHtml = (Array.isArray(ev.disciplines) && ev.disciplines.length > 0 ? ev.disciplines : ['MTB']).map(d => {
        const info = Utils.disciplineInfo(d);
        return `<span class="badge-discipline badge-${info.key}">${Utils.esc(d)}</span>`;
      }).join(' ');

      const distances = Utils.distanceText(ev, ', ') || 'Ver bases';

      body.innerHTML = `
        <div class="detail-badges">
          ${modalBadgesHtml}
          <span class="badge-reg${unlocated ? ' badge-unlocated' : ''}">${Utils.esc(regName)}</span>
          ${ev.price_type === 'free' ? '<span class="badge-reg badge-free">GRATIS</span>' : ''}
          ${isPast ? '<span class="badge-reg">Finalizada</span>' : ''}
          ${ev.status === 'postponed' && !isPast ? '<span class="badge-reg badge-unlocated">Reprogramada: confirma la fecha</span>' : ''}
        </div>

        <p class="detail-description">
          ${Utils.esc(ev.description || 'Sin descripción detallada disponible.')}
        </p>

        <div class="detail-grid">
          <div><strong>Fecha:</strong> ${Utils.esc(Utils.formatDateLong(ev))}</div>
          <div><strong>Lugar:</strong> ${Utils.esc(unlocated ? (ev.location || 'Por confirmar') : (ev.location || ev.commune))}${unlocated ? ' <em>(sin confirmar en las fuentes)</em>' : ''}</div>
          <div><strong>Distancias:</strong> ${Utils.esc(distances)}</div>
          <div><strong>${(ev.distances || []).length > 1 && ev.elevation_gain_m ? 'Desnivel máx.' : 'Desnivel'}:</strong> ${ev.elevation_gain_m ? '+' + Utils.esc(ev.elevation_gain_m.toLocaleString('es-CL')) + ' m' : 'No especificado'}</div>
          <div><strong>Organizador:</strong> ${Utils.esc(ev.organizer || 'Organización oficial')}</div>
        </div>

        <div class="detail-actions">
          <div class="detail-actions-left">
            <button type="button" class="cal-btn-mini" id="modal-export-google">📅 Google Calendar</button>
            <button type="button" class="cal-btn-mini" id="modal-export-apple">🍏 Apple Calendar (.ics)</button>
            <button type="button" class="cal-btn-mini" id="modal-share">🔗 Compartir</button>
          </div>
          <a href="${Utils.eventHref(ev)}" target="_blank" rel="noopener" class="btn-action-primary">
            Inscripción Oficial &rarr;
          </a>
        </div>
      `;

      document.getElementById('modal-export-google')?.addEventListener('click', () => CalendarExporter.exportToGoogle(ev));
      document.getElementById('modal-export-apple')?.addEventListener('click', () => CalendarExporter.exportToICS(ev));
      document.getElementById('modal-share')?.addEventListener('click', (e) => this.shareEvent(ev, e.currentTarget));

      window.history.replaceState({}, '', window.location.pathname + window.location.search + `#carrera=${encodeURIComponent(ev.id)}`);
      this.showModal('modal-detail');
    },

    async shareEvent(ev, button) {
      const url = `${window.location.origin}${window.location.pathname}#carrera=${encodeURIComponent(ev.id)}`;
      const text = `${ev.name} — ${Utils.formatDateLong(ev)}`;
      const original = button.textContent;
      try {
        if (navigator.share) {
          await navigator.share({ title: ev.name, text, url });
          return;
        }
        await navigator.clipboard.writeText(url);
        button.textContent = '✔ Enlace copiado';
      } catch (err) {
        if (err && err.name === 'AbortError') return;
        window.prompt('Copia el enlace de la carrera:', url);
        return;
      }
      setTimeout(() => { button.textContent = original; }, 2000);
    },

    openPublishModal() {
      const feedback = document.getElementById('publish-feedback');
      if (feedback) feedback.style.display = 'none';
      this.showModal('modal-publish');
    },

    openContactModal() {
      const feedback = document.getElementById('contact-feedback');
      if (feedback) feedback.style.display = 'none';
      this.showModal('modal-contact');
    },

    showFormFeedback(el, html) {
      if (!el) return;
      el.style.display = 'block';
      el.style.background = '#dcfce7';
      el.style.color = '#166534';
      el.style.border = '1px solid #bbf7d0';
      el.innerHTML = html;
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

      window.location.href = `mailto:contacto@pedaleo.cl?subject=${mailtoSubject}&body=${mailtoBody}`;

      const feedback = document.getElementById('contact-feedback');
      this.showFormFeedback(feedback, `¡Gracias por tu mensaje, <strong>${Utils.esc(name)}</strong>! Se ha generado tu correo hacia <strong>contacto@pedaleo.cl</strong>.`);

      setTimeout(() => {
        this.closeModals();
        form.reset();
        if (feedback) feedback.style.display = 'none';
      }, 3500);
    },

    /**
     * Handles race submission as a contact email to contacto@pedaleo.cl
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

      window.location.href = `mailto:contacto@pedaleo.cl?subject=${mailtoSubject}&body=${mailtoBody}`;

      const feedback = document.getElementById('publish-feedback');
      this.showFormFeedback(feedback, `¡Solicitud enviada! Se ha preparado tu correo a <strong>contacto@pedaleo.cl</strong> para revisar y publicar <strong>${Utils.esc(name)}</strong>.`);

      setTimeout(() => {
        this.closeModals();
        form.reset();
        if (feedback) feedback.style.display = 'none';
      }, 3500);
    },

    // ------------------------------------------------------------------- SEO

    /** schema.org SportsEvent markup for upcoming races (helps Google show rich results). */
    injectStructuredData() {
      const upcoming = this.events.filter(ev => ev.status !== 'cancelled' && !Utils.isPast(ev, this.today) && !this.isUnlocated(ev));
      if (!upcoming.length) return;

      const graph = upcoming.map(ev => ({
        '@type': 'SportsEvent',
        name: ev.name,
        startDate: ev.date,
        endDate: Utils.eventEnd(ev),
        eventStatus: ev.status === 'postponed' ? 'https://schema.org/EventPostponed' : 'https://schema.org/EventScheduled',
        eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
        sport: (ev.disciplines || []).join(', ') || 'Cycling',
        description: ev.description || undefined,
        url: Utils.safeUrl(ev.registration_url || ev.url),
        location: {
          '@type': 'Place',
          name: ev.location || ev.commune,
          address: {
            '@type': 'PostalAddress',
            addressLocality: ev.commune,
            addressRegion: ev.region_name,
            addressCountry: 'CL'
          }
        },
        organizer: ev.organizer ? { '@type': 'Organization', name: ev.organizer } : undefined
      }));

      let script = document.getElementById('ld-events');
      if (!script) {
        script = document.createElement('script');
        script.type = 'application/ld+json';
        script.id = 'ld-events';
        document.head.appendChild(script);
      }
      script.textContent = JSON.stringify({ '@context': 'https://schema.org', '@graph': graph }).replace(/</g, '\\u003c');
    }
  };

  window.App = App;
  App.init();
});
