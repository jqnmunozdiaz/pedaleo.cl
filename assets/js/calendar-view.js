/**
 * Pedaleo.cl - Monthly Grid Calendar View
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
    const month = this.currentDate.getMonth(); // 0-indexed

    const monthNames = [
      'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
      'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    // Days in Chilean calendar start Monday (1) to Sunday (0)
    let startDayOfWeek = firstDay.getDay() - 1;
    if (startDayOfWeek === -1) startDayOfWeek = 6; // Sunday becomes 6

    const totalDays = lastDay.getDate();

    let html = `
      <div class="calendar-grid-view">
        <div class="calendar-nav-bar">
          <button class="cal-nav-btn" id="cal-prev-month">&larr; Mes Anterior</button>
          <div class="calendar-nav-title">${monthNames[month]} ${year}</div>
          <button class="cal-nav-btn" id="cal-next-month">Mes Siguiente &rarr;</button>
        </div>
        <table class="calendar-table">
          <thead>
            <tr>
              <th>Lun</th><th>Mar</th><th>Mié</th><th>Jue</th><th>Vie</th><th>Sáb</th><th>Dom</th>
            </tr>
          </thead>
          <tbody>
    `;

    let dayCounter = 1;
    let nextMonthCounter = 1;
    const prevMonthLastDay = new Date(year, month, 0).getDate();

    // 6 weeks max in calendar grid
    for (let row = 0; row < 6; row++) {
      html += '<tr>';
      for (let col = 0; col < 7; col++) {
        if (row === 0 && col < startDayOfWeek) {
          // Previous month days
          const prevDay = prevMonthLastDay - (startDayOfWeek - col - 1);
          html += `<td class="other-month"><div class="cal-day-number">${prevDay}</div></td>`;
        } else if (dayCounter > totalDays) {
          // Next month days
          html += `<td class="other-month"><div class="cal-day-number">${nextMonthCounter++}</div></td>`;
        } else {
          // Current month days
          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(dayCounter).padStart(2, '0')}`;
          const dayEvents = events.filter(e => {
            const eStart = e.date;
            const eEnd = e.end_date || e.date;
            return dateStr >= eStart && dateStr <= eEnd;
          });

          let eventsPills = '';
          dayEvents.forEach(e => {
            const discClass = `badge-${(e.disciplines[0] || 'mtb').toLowerCase().split('/')[0]}`;
            eventsPills += `
              <span class="cal-event-pill ${discClass}" data-id="${e.id}" title="${e.name}">
                🚴 ${e.name}
              </span>
            `;
          });

          html += `
            <td>
              <div class="cal-day-number">${dayCounter}</div>
              ${eventsPills}
            </td>
          `;
          dayCounter++;
        }
      }
      html += '</tr>';
      if (dayCounter > totalDays) break;
    }

    html += `
          </tbody>
        </table>
      </div>
    `;

    container.innerHTML = html;

    // Attach listeners
    document.getElementById('cal-prev-month').addEventListener('click', () => {
      this.currentDate.setMonth(this.currentDate.getMonth() - 1);
      this.render(container, events, onSelectEvent);
    });

    document.getElementById('cal-next-month').addEventListener('click', () => {
      this.currentDate.setMonth(this.currentDate.getMonth() + 1);
      this.render(container, events, onSelectEvent);
    });

    container.querySelectorAll('.cal-event-pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        const eventId = e.currentTarget.dataset.id;
        const ev = events.find(item => item.id === eventId);
        if (ev && onSelectEvent) {
          onSelectEvent(ev);
        }
      });
    });
  }
};

window.CalendarView = CalendarView;
