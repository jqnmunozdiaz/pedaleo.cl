/**
 * Pedaleo.cl - Calendar Exporter Utility
 * Allows instant, per-race calendar export to Google Calendar and Apple Calendar (.ics)
 */

const CalendarExporter = {
  /** "Machalí, Región O'Higgins, Chile" without repeating the region twice. */
  buildLocation(ev) {
    const base = ev.location || ev.commune || '';
    const region = ev.region_name || ev.region || '';
    const hasRegion = region && Utils.normalize(base).includes(Utils.normalize(region));
    return [base, hasRegion || !region ? '' : `Región ${region}`, 'Chile'].filter(Boolean).join(', ');
  },

  buildDetails(ev, lineBreak) {
    const distances = ev.distances && ev.distances.length ? ev.distances.join(', ') : 'Ver bases';
    return [
      `Disciplina: ${(ev.disciplines || []).join(', ')}`,
      `Distancias: ${distances}`,
      `Desnivel: ${ev.elevation_gain_m ? '+' + ev.elevation_gain_m + 'm' : 'No especificado'}`,
      `Inscripción / Info: ${ev.registration_url || ev.url}`,
      '',
      ev.description || '',
      '',
      'Vía Pedaleo.cl — Calendario de Ciclismo de Chile'
    ].join(lineBreak);
  },

  /**
   * Generates a Google Calendar URL for an event and opens it
   * @param {Object} ev
   */
  exportToGoogle(ev) {
    const start = ev.date.replace(/-/g, '');
    const end = Utils.nextDayStr(Utils.eventEnd(ev)).replace(/-/g, '');

    const params = new URLSearchParams({
      action: 'TEMPLATE',
      text: `🚴 ${ev.name}`,
      dates: `${start}/${end}`,
      details: this.buildDetails(ev, '\n'),
      location: this.buildLocation(ev)
    });

    window.open(`https://calendar.google.com/calendar/render?${params.toString()}`, '_blank', 'noopener,noreferrer');
  },

  /** RFC 5545 TEXT escaping. */
  escapeICS(text) {
    return String(text ?? '')
      .replace(/\\/g, '\\\\')
      .replace(/;/g, '\\;')
      .replace(/,/g, '\\,')
      .replace(/\r?\n/g, '\\n');
  },

  /** RFC 5545 line folding: max 75 octets per line, continuation lines start with a space. */
  foldICS(line) {
    const encoder = new TextEncoder();
    if (encoder.encode(line).length <= 75) return line;

    const chunks = [];
    let current = '';
    let currentBytes = 0;
    let limit = 75;
    for (const ch of line) { // iterates by code point, never splits a surrogate pair
      const bytes = encoder.encode(ch).length;
      if (currentBytes + bytes > limit) {
        chunks.push(current);
        current = '';
        currentBytes = 0;
        limit = 74; // continuation lines lose one octet to the leading space
      }
      current += ch;
      currentBytes += bytes;
    }
    chunks.push(current);
    return chunks.join('\r\n ');
  },

  /**
   * Generates and downloads a standard .ics file for Apple Calendar or Outlook
   * @param {Object} ev
   */
  exportToICS(ev) {
    const startDate = ev.date.replace(/-/g, '');
    const endDate = Utils.nextDayStr(Utils.eventEnd(ev)).replace(/-/g, '');
    const stamp = new Date().toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';

    const icsLines = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Pedaleo.cl//Calendario Ciclismo Chile//ES',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
      'BEGIN:VEVENT',
      `UID:pedaleo-${ev.id}@pedaleo.cl`,
      `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${startDate}`,
      `DTEND;VALUE=DATE:${endDate}`,
      `SUMMARY:${this.escapeICS('🚴 ' + ev.name)}`,
      `LOCATION:${this.escapeICS(this.buildLocation(ev))}`,
      `DESCRIPTION:${this.escapeICS(this.buildDetails(ev, '\n'))}`,
      `URL:${Utils.safeUrl(ev.registration_url || ev.url)}`,
      'STATUS:CONFIRMED',
      'TRANSP:TRANSPARENT',
      'BEGIN:VALARM',
      'TRIGGER:-P7D',
      'ACTION:DISPLAY',
      `DESCRIPTION:${this.escapeICS('Recordatorio: ' + ev.name + ' en 7 días')}`,
      'END:VALARM',
      'END:VEVENT',
      'END:VCALENDAR'
    ].map(line => this.foldICS(line));

    const blob = new Blob([icsLines.join('\r\n') + '\r\n'], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${ev.id || 'carrera'}.ics`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
};

window.CalendarExporter = CalendarExporter;
