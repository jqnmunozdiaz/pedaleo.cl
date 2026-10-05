/**
 * Pedaleo.cl - Planner & "Mi Temporada" Manager
 * Client-side local storage persistence & .ics calendar export
 */

const Planner = {
  STORAGE_KEY: 'pedaleo_my_season_races',

  /**
   * Get all planned races from localStorage
   * @returns {Array<{ id: string, priority: string, status: string, addedAt: string }>}
   */
  getPlannedRaces() {
    try {
      const data = localStorage.getItem(this.STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      console.error('Error reading planned races from localStorage:', e);
      return [];
    }
  },

  /**
   * Check if a specific race is planned
   * @param {string} eventId
   * @returns {boolean}
   */
  isPlanned(eventId) {
    const list = this.getPlannedRaces();
    return list.some(item => item.id === eventId);
  },

  /**
   * Toggle planning a race
   * @param {string} eventId
   * @param {string} [priority='A']
   * @returns {boolean} true if added, false if removed
   */
  toggleRace(eventId, priority = 'A') {
    const list = this.getPlannedRaces();
    const index = list.findIndex(item => item.id === eventId);
    let added = false;

    if (index >= 0) {
      list.splice(index, 1);
    } else {
      list.push({
        id: eventId,
        priority: priority, // 'A' (Principal), 'B' (Preparatoria), 'C' (Entrenamiento)
        status: 'planificada', // 'planificada', 'inscrito', 'completada'
        addedAt: new Date().toISOString()
      });
      added = true;
    }

    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(list));
    } catch (e) {
      console.error('Error saving to localStorage:', e);
    }

    this.updateBadge();
    return added;
  },

  /**
   * Update priority for a planned race
   */
  setPriority(eventId, priority) {
    const list = this.getPlannedRaces();
    const item = list.find(r => r.id === eventId);
    if (item) {
      item.priority = priority;
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(list));
    }
  },

  /**
   * Update status for a planned race
   */
  setStatus(eventId, status) {
    const list = this.getPlannedRaces();
    const item = list.find(r => r.id === eventId);
    if (item) {
      item.status = status;
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(list));
    }
  },

  /**
   * Update the badge counter in the header
   */
  updateBadge() {
    const badge = document.getElementById('planner-counter');
    if (!badge) return;
    const count = this.getPlannedRaces().length;
    badge.textContent = count;
    badge.style.display = count > 0 ? 'inline-flex' : 'none';
  },

  /**
   * Export planned races to .ics calendar format
   * Fully compatible with Google Calendar, Apple Calendar, and Outlook
   * @param {Array<Object>} allEvents
   */
  exportToICS(allEvents) {
    const planned = this.getPlannedRaces();
    if (planned.length === 0) {
      alert('Aún no has agregado carreras a "Mi Temporada". Haz clic en la estrella (★) de cualquier carrera para agregarla.');
      return;
    }

    const plannedMap = new Map(planned.map(p => [p.id, p]));
    const eventsToExport = allEvents.filter(e => plannedMap.has(e.id));

    let icsContent = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Pedaleo.cl//Calendario Ciclismo Chile//ES',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
      'X-WR-CALNAME:Pedaleo.cl - Mi Temporada',
      'X-WR-TIMEZONE:America/Santiago'
    ];

    eventsToExport.forEach(event => {
      const planInfo = plannedMap.get(event.id);
      const startDate = event.date.replace(/-/g, '');
      const endDate = (event.end_date || event.date).replace(/-/g, '');

      // Format end date for all-day event (next day in iCal format)
      const endD = new Date(event.end_date || event.date);
      endD.setDate(endD.getDate() + 1);
      const nextDayStr = endD.toISOString().split('T')[0].replace(/-/g, '');

      const summary = `🚴 ${event.name} [Objetivo ${planInfo.priority}]`;
      const location = `${event.location || event.commune}, Región ${event.region_name}, Chile`;
      const description = `Modalidad: ${event.disciplines.join(', ')}\\n` +
                          `Distancias: ${event.distances.join(', ')}\\n` +
                          `Desnivel: +${event.elevation_gain_m || 0}m\\n` +
                          `Estado: ${planInfo.status.toUpperCase()}\\n` +
                          `Más info e inscripciones: ${event.registration_url || event.url}\\n\\n` +
                          `${event.description || ''}\\n\\n` +
                          `Organizado por ${event.organizer} - Vía Pedaleo.cl`;

      icsContent.push('BEGIN:VEVENT');
      icsContent.push(`UID:pedaleo-${event.id}@pedaleo.cl`);
      icsContent.push(`DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').split('.')[0]}Z`);
      icsContent.push(`DTSTART;VALUE=DATE:${startDate}`);
      icsContent.push(`DTEND;VALUE=DATE:${nextDayStr}`);
      icsContent.push(`SUMMARY:${summary}`);
      icsContent.push(`LOCATION:${location}`);
      icsContent.push(`DESCRIPTION:${description}`);
      icsContent.push(`URL:${event.registration_url || event.url}`);
      icsContent.push('STATUS:CONFIRMED');
      icsContent.push('TRANSP:TRANSPARENT');
      icsContent.push('BEGIN:VALARM');
      icsContent.push('TRIGGER:-P7D');
      icsContent.push('ACTION:DISPLAY');
      icsContent.push(`DESCRIPTION:Recordatorio: ${event.name} en 7 días`);
      icsContent.push('END:VALARM');
      icsContent.push('END:VEVENT');
    });

    icsContent.push('END:VCALENDAR');

    const blob = new Blob([icsContent.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `pedaleo_temporada_${new Date().getFullYear()}.ics`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
};

window.Planner = Planner;
