/**
 * Pedaleo.cl - Sober, Balanced CSS Grid Calendar View
 * Guarantees 7 strictly equal columns and handles multi-event days cleanly
 */

const CalendarView = {
  // Month being displayed; null means "pick the most relevant month for the current results".
  viewed: null,
  MAX_VISIBLE: 3,

  /** Forget the month the user navigated to (called when filters change). */
  resetMonth() {
    this.viewed = null;
  },

  /** Month of the next upcoming race (or the most recent one if all are past, or the current month). */
  pickInitialMonth(events) {
    const today = Utils.todayStr();
    const sorted = [...events].sort((a, b) => a.date.localeCompare(b.date));
    const upcoming = sorted.find(e => Utils.eventEnd(e) >= today);
    const target = upcoming || sorted[sorted.length - 1];
    if (!target) {
      const now = new Date();
      return { year: now.getFullYear(), month: now.getMonth() };
    }
    // A race already under way is shown in today's month, not its start month.
    const anchor = upcoming && target.date < today ? today : target.date;
    const [y, m] = anchor.split('-').map(Number);
    return { year: y, month: m - 1 };
  },

  shiftMonth(delta) {
    const d = new Date(this.viewed.year, this.viewed.month + delta, 1);
    this.viewed = { year: d.getFullYear(), month: d.getMonth() };
  },

  eventsOnDate(events, dateStr) {
    return events.filter(e => dateStr >= e.date && dateStr <= Utils.eventEnd(e));
  },

  /**
   * Render monthly grid view
   * @param {HTMLElement} container
   * @param {Array<Object>} events
   * @param {Function} onSelectEvent
   */
  render(container, events, onSelectEvent) {
    if (!this.viewed) this.viewed = this.pickInitialMonth(events);
    const { year, month } = this.viewed;

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    // Chilean calendar starts Monday (0) to Sunday (6)
    let startDayOfWeek = firstDay.getDay() - 1;
    if (startDayOfWeek === -1) startDayOfWeek = 6;

    const totalDays = lastDay.getDate();
    const prevMonthLastDay = new Date(year, month, 0).getDate();
    const todayStr = Utils.todayStr();

    let html = `
      <div class="cal-container">
        <div class="cal-nav">
          <button class="cal-btn" id="cal-prev-month" title="Mes anterior">&larr; Anterior</button>
          <div class="cal-title" aria-live="polite">${Utils.MONTH_NAMES[month]} ${year}</div>
          <div class="cal-nav-right">
            <button class="cal-btn-today" id="cal-today">Hoy</button>
            <button class="cal-btn" id="cal-next-month" title="Mes siguiente">Siguiente &rarr;</button>
          </div>
        </div>

        <div class="cal-grid-header">
          <div>Lun</div>
          <div>Mar</div>
          <div>Mié</div>
          <div>Jue</div>
          <div>Vie</div>
          <div class="weekend-head">Sáb</div>
          <div class="weekend-head">Dom</div>
        </div>

        <div class="cal-grid-body">
    `;

    // 1. Previous month trailing days
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      html += `
        <div class="cal-cell cal-cell-muted">
          <div class="cal-day-num">${prevMonthLastDay - i}</div>
        </div>
      `;
    }

    // 2. Current month days
    for (let day = 1; day <= totalDays; day++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const isToday = dateStr === todayStr;
      const dayEvents = this.eventsOnDate(events, dateStr);

      let pillsHtml = '';
      dayEvents.slice(0, this.MAX_VISIBLE).forEach(e => {
        const info = Utils.disciplineInfo((e.disciplines || [])[0]);
        const label = `${e.name} (${(e.disciplines || []).join(', ')})`;
        pillsHtml += `
          <button type="button" class="cal-pill badge-${info.key}${Utils.isPast(e, todayStr) ? ' is-past' : ''}" data-id="${Utils.esc(e.id)}" title="${Utils.esc(label)}">
            <span class="cal-pill-dot"></span>
            <span class="cal-pill-title">${Utils.esc(e.name)}</span>
          </button>
        `;
      });

      const remainingCount = dayEvents.length - this.MAX_VISIBLE;
      if (remainingCount > 0) {
        pillsHtml += `
          <button type="button" class="cal-more-btn" data-date="${dateStr}" title="Ver todas las carreras del día">
            +${remainingCount} más
          </button>
        `;
      }

      html += `
        <div class="cal-cell ${isToday ? 'cal-cell-today' : ''}">
          <div class="cal-day-header">
            <span class="cal-day-num ${isToday ? 'is-today' : ''}">${day}</span>
            ${dayEvents.length > 0 ? `<span class="cal-count-tag">${dayEvents.length}</span>` : ''}
          </div>
          <div class="cal-cell-events">
            ${pillsHtml}
          </div>
        </div>
      `;
    }

    // 3. Next month leading days to complete grid row
    const remainder = (startDayOfWeek + totalDays) % 7;
    const daysToAdd = remainder === 0 ? 0 : 7 - remainder;
    for (let nextDay = 1; nextDay <= daysToAdd; nextDay++) {
      html += `
        <div class="cal-cell cal-cell-muted">
          <div class="cal-day-num">${nextDay}</div>
        </div>
      `;
    }

    html += `
        </div>
      </div>
    `;

    container.innerHTML = html;

    const rerender = () => this.render(container, events, onSelectEvent);

    container.querySelector('#cal-prev-month').addEventListener('click', () => {
      this.shiftMonth(-1);
      rerender();
    });
    container.querySelector('#cal-next-month').addEventListener('click', () => {
      this.shiftMonth(1);
      rerender();
    });
    container.querySelector('#cal-today').addEventListener('click', () => {
      const now = new Date();
      this.viewed = { year: now.getFullYear(), month: now.getMonth() };
      rerender();
    });

    // Pill click -> detail modal
    container.querySelectorAll('.cal-pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        const ev = events.find(item => item.id === e.currentTarget.dataset.id);
        if (ev && onSelectEvent) onSelectEvent(ev);
      });
    });

    // More button click -> Day summary modal
    container.querySelectorAll('.cal-more-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const dateStr = e.currentTarget.dataset.date;
        this.openDayModal(dateStr, this.eventsOnDate(events, dateStr), onSelectEvent);
      });
    });
  },

  /**
   * Modal to show all events when a day has more than 3 races
   */
  openDayModal(dateStr, dayEvents, onSelectEvent) {
    const d = Utils.parseDate(dateStr);
    const formatted = `${Utils.DOW_LONG[d.getDay()]} ${d.getDate()} de ${Utils.MONTH_NAMES[d.getMonth()]}, ${d.getFullYear()}`;

    const title = document.getElementById('modal-detail-title');
    const body = document.getElementById('modal-detail-body');
    if (!title || !body) return;

    title.textContent = `Carreras del ${formatted}`;

    let listHtml = `
      <p class="day-modal-intro">
        Se realizan ${dayEvents.length} competencias en esta fecha:
      </p>
      <div class="day-modal-list">
    `;

    dayEvents.forEach(ev => {
      const disciplines = (ev.disciplines || []).join(', ');
      listHtml += `
        <div class="day-modal-item">
          <div>
            <div class="day-modal-name">${Utils.esc(ev.name)}</div>
            <div class="day-modal-meta">
              📍 ${Utils.esc(ev.location || ev.commune)} &bull; ${Utils.esc(ev.region_name || 'Chile')} &bull; ${Utils.esc(disciplines)}
            </div>
          </div>
          <div class="day-modal-actions">
            <button type="button" class="cal-btn-mini day-modal-view-btn" data-id="${Utils.esc(ev.id)}">Ver Detalle</button>
            <a href="${Utils.eventHref(ev)}" target="_blank" rel="noopener" class="cal-btn-mini btn-action">Inscripción</a>
          </div>
        </div>
      `;
    });

    listHtml += '</div>';
    body.innerHTML = listHtml;

    body.querySelectorAll('.day-modal-view-btn').forEach(b => {
      b.addEventListener('click', (e) => {
        const ev = dayEvents.find(x => x.id === e.currentTarget.dataset.id);
        if (ev && onSelectEvent) onSelectEvent(ev);
      });
    });

    if (window.App) {
      window.App.showModal('modal-detail');
    } else {
      document.getElementById('modal-detail')?.classList.add('active');
    }
  }
};

window.CalendarView = CalendarView;
