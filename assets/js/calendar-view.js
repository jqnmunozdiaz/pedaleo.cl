/**
 * Pedaleo.cl - Sober, Balanced CSS Grid Calendar View
 * Guarantees 7 strictly equal columns and handles multi-event days cleanly
 */

const CalendarView = {
  currentDate: new Date(),

  /**
   * Render monthly grid view
   * @param {HTMLElement} container
   * @param {Array<Object>} events
   * @param {Function} onSelectEvent
   */
  render(container, events, onSelectEvent) {
    const year = this.currentDate.getFullYear();
    const month = this.currentDate.getMonth();

    const monthNames = [
      'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
      'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    // Chilean calendar starts Monday (0) to Sunday (6)
    let startDayOfWeek = firstDay.getDay() - 1;
    if (startDayOfWeek === -1) startDayOfWeek = 6;

    const totalDays = lastDay.getDate();
    const prevMonthLastDay = new Date(year, month, 0).getDate();

    let html = `
      <div class="cal-container">
        <!-- Calendar Header Navigation -->
        <div class="cal-nav">
          <button class="cal-btn" id="cal-prev-month" title="Mes Anterior">&larr; Anterior</button>
          <div class="cal-title">${monthNames[month]} ${year}</div>
          <div class="cal-nav-right">
            <button class="cal-btn-today" id="cal-today">Hoy</button>
            <button class="cal-btn" id="cal-next-month" title="Mes Siguiente">Siguiente &rarr;</button>
          </div>
        </div>

        <!-- 7-Day Header -->
        <div class="cal-grid-header">
          <div>Lun</div>
          <div>Mar</div>
          <div>Mié</div>
          <div>Jue</div>
          <div>Vie</div>
          <div class="weekend-head">Sáb</div>
          <div class="weekend-head">Dom</div>
        </div>

        <!-- 7-Column Days Grid -->
        <div class="cal-grid-body">
    `;

    // 1. Previous month trailing days
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const prevDay = prevMonthLastDay - i;
      html += `
        <div class="cal-cell cal-cell-muted">
          <div class="cal-day-num">${prevDay}</div>
        </div>
      `;
    }

    // 2. Current month days
    const todayStr = new Date().toISOString().split('T')[0];

    for (let day = 1; day <= totalDays; day++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const isToday = dateStr === todayStr;

      // Filter events occurring on this date
      const dayEvents = events.filter(e => {
        const start = e.date;
        const end = e.end_date || e.date;
        return dateStr >= start && dateStr <= end;
      });

      const maxVisible = 3;
      const visibleEvents = dayEvents.slice(0, maxVisible);
      const remainingCount = dayEvents.length - maxVisible;

      let pillsHtml = '';
      visibleEvents.forEach(e => {
        const discClass = `badge-${(e.disciplines[0] || 'mtb').toLowerCase().split('/')[0]}`;
        pillsHtml += `
          <div class="cal-pill ${discClass}" data-id="${e.id}" title="${e.name} (${e.disciplines.join(', ')})">
            <span class="cal-pill-dot"></span>
            <span class="cal-pill-title">${e.name}</span>
          </div>
        `;
      });

      if (remainingCount > 0) {
        pillsHtml += `
          <button class="cal-more-btn" data-date="${dateStr}" title="Ver todas las carreras del día">
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
    const totalRendered = startDayOfWeek + totalDays;
    const remainder = totalRendered % 7;
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

    // Attach navigation listeners
    document.getElementById('cal-prev-month').addEventListener('click', () => {
      this.currentDate.setMonth(this.currentDate.getMonth() - 1);
      this.render(container, events, onSelectEvent);
    });

    document.getElementById('cal-next-month').addEventListener('click', () => {
      this.currentDate.setMonth(this.currentDate.getMonth() + 1);
      this.render(container, events, onSelectEvent);
    });

    document.getElementById('cal-today')?.addEventListener('click', () => {
      this.currentDate = new Date();
      this.render(container, events, onSelectEvent);
    });

    // Pill click -> detail modal
    container.querySelectorAll('.cal-pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        const eventId = e.currentTarget.dataset.id;
        const ev = events.find(item => item.id === eventId);
        if (ev && onSelectEvent) {
          onSelectEvent(ev);
        }
      });
    });

    // More button click -> Day summary modal
    container.querySelectorAll('.cal-more-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const dateStr = e.currentTarget.dataset.date;
        const dayEvents = events.filter(ev => {
          const start = ev.date;
          const end = ev.end_date || ev.date;
          return dateStr >= start && dateStr <= end;
        });
        this.openDayModal(dateStr, dayEvents, onSelectEvent);
      });
    });
  },

  /**
   * Modal to show all events when a day has more than 3 races
   */
  openDayModal(dateStr, dayEvents, onSelectEvent) {
    const d = new Date(dateStr + 'T12:00:00');
    const dayNames = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
    const monthNames = [
      'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
      'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];
    const formatted = `${dayNames[d.getDay()]} ${d.getDate()} de ${monthNames[d.getMonth()]}, ${d.getFullYear()}`;

    const modal = document.getElementById('modal-detail');
    const title = document.getElementById('modal-detail-title');
    const body = document.getElementById('modal-detail-body');

    if (!modal || !title || !body) return;

    title.textContent = `Carreras del ${formatted}`;

    let listHtml = `
      <p style="font-size:0.88rem; color:var(--text-muted); margin-bottom:1rem">
        Se realizan ${dayEvents.length} competencias en esta fecha:
      </p>
      <div style="display:flex; flex-direction:column; gap:0.6rem">
    `;

    dayEvents.forEach(ev => {
      const disc = ev.disciplines[0] || 'MTB';
      listHtml += `
        <div style="padding:0.75rem; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-subtle); display:flex; justify-content:space-between; align-items:center; gap:0.5rem">
          <div>
            <div style="font-weight:700; font-size:0.95rem; color:var(--text-main)">${ev.name}</div>
            <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.2rem">
              📍 ${ev.location || ev.commune} &bull; Región ${ev.region_name || ev.region} &bull; ${ev.disciplines.join(', ')}
            </div>
          </div>
          <div style="display:flex; gap:0.4rem; flex-shrink:0">
            <button class="cal-btn-mini day-modal-view-btn" data-id="${ev.id}">Ver Detalle</button>
            <a href="${ev.registration_url || ev.url}" target="_blank" rel="noopener" class="cal-btn-mini btn-action">Inscripción</a>
          </div>
        </div>
      `;
    });

    listHtml += '</div>';
    body.innerHTML = listHtml;

    body.querySelectorAll('.day-modal-view-btn').forEach(b => {
      b.addEventListener('click', (e) => {
        const id = e.currentTarget.dataset.id;
        const ev = dayEvents.find(x => x.id === id);
        if (ev && onSelectEvent) {
          onSelectEvent(ev);
        }
      });
    });

    modal.classList.add('active');
  }
};

window.CalendarView = CalendarView;
