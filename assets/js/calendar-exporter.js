/**
 * Pedaleo.cl - Calendar Exporter Utility
 * Allows instant, per-race calendar export to Google Calendar and Apple Calendar (.ics)
 */

const CalendarExporter = {
  /**
   * Generates a Google Calendar URL for an event and opens it
   * @param {Object} ev
   */
  exportToGoogle(ev) {
    const title = encodeURIComponent(`🚴 ${ev.name}`);
    const location = encodeURIComponent(`${ev.location || ev.commune}, Región ${ev.region_name || ev.region}, Chile`);

    // Format dates to YYYYMMDD for all-day event
    const startDate = ev.date.replace(/-/g, '');
    const endD = new Date(ev.end_date || ev.date);
    endD.setDate(endD.getDate() + 1);
    const nextDayStr = endD.toISOString().split('T')[0].replace(/-/g, '');
    const dates = `${startDate}/${nextDayStr}`;

    const details = encodeURIComponent(
      `Carrera: ${ev.name}\n` +
      `Disciplina: ${ev.disciplines.join(', ')}\n` +
      `Distancias: ${ev.distances ? ev.distances.join(', ') : 'Ver bases'}\n` +
      `Desnivel: ${ev.elevation_gain_m ? '+' + ev.elevation_gain_m + 'm' : 'No especificado'}\n` +
      `Inscripción / Info: ${ev.registration_url || ev.url}\n\n` +
      `${ev.description || ''}\n\n` +
      `Vía Pedaleo.cl — Calendario de Ciclismo de Chile`
    );

    const googleUrl = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${dates}&details=${details}&location=${location}`;
    window.open(googleUrl, '_blank', 'noopener,noreferrer');
  },

  /**
   * Generates and downloads a standard .ics file for Apple Calendar or Outlook
   * @param {Object} ev
   */
  exportToICS(ev) {
    const startDate = ev.date.replace(/-/g, '');
    const endD = new Date(ev.end_date || ev.date);
    endD.setDate(endD.getDate() + 1);
    const nextDayStr = endD.toISOString().split('T')[0].replace(/-/g, '');

    const summary = `🚴 ${ev.name}`;
    const location = `${ev.location || ev.commune}, Región ${ev.region_name || ev.region}, Chile`;
    const description = `Disciplina: ${ev.disciplines.join(', ')}\\n` +
                        `Distancias: ${ev.distances ? ev.distances.join(', ') : 'Ver bases'}\\n` +
                        `Desnivel: ${ev.elevation_gain_m ? '+' + ev.elevation_gain_m + 'm' : 'No especificado'}\\n` +
                        `Inscripciones: ${ev.registration_url || ev.url}\\n\\n` +
                        `${ev.description || ''}\\n\\n` +
                        `Vía Pedaleo.cl`;

    const icsContent = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Pedaleo.cl//Calendario Ciclismo Chile//ES',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
      'BEGIN:VEVENT',
      `UID:pedaleo-${ev.id}@pedaleo.cl`,
      `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').split('.')[0]}Z`,
      `DTSTART;VALUE=DATE:${startDate}`,
      `DTEND;VALUE=DATE:${nextDayStr}`,
      `SUMMARY:${summary}`,
      `LOCATION:${location}`,
      `DESCRIPTION:${description}`,
      `URL:${ev.registration_url || ev.url}`,
      'STATUS:CONFIRMED',
      'TRANSP:TRANSPARENT',
      'BEGIN:VALARM',
      'TRIGGER:-P7D',
      'ACTION:DISPLAY',
      `DESCRIPTION:Recordatorio: ${ev.name} en 7 días`,
      'END:VALARM',
      'END:VEVENT',
      'END:VCALENDAR'
    ];

    const blob = new Blob([icsContent.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${ev.id || 'carrera'}.ics`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
};

window.CalendarExporter = CalendarExporter;
