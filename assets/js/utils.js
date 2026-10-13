/**
 * Pedaleo.cl - Shared helpers
 * HTML escaping, safe URLs, accent-insensitive text matching and
 * timezone-safe date handling (all event dates are plain "YYYY-MM-DD" strings).
 */

const Utils = {
  MONTH_NAMES: [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
  ],
  MONTH_SHORT: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
  DOW_SHORT: ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'],
  DOW_LONG: ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'],

  /** Escapes a value for safe interpolation into HTML text or attribute values. */
  esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  },

  /** Returns the URL only when it is http(s); otherwise '#'. Result is NOT escaped. */
  safeUrl(url) {
    const u = String(url ?? '').trim();
    return /^https?:\/\//i.test(u) ? u : '#';
  },

  /** Best link to register / get info for an event, escaped for use in an href attribute. */
  eventHref(ev) {
    return this.esc(this.safeUrl(ev.registration_url || ev.url));
  },

  /** Lowercase + strip diacritics so "Valparaiso" matches "Valparaíso". */
  normalize(text) {
    return String(text ?? '')
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .toLowerCase();
  },

  /** Local-time "YYYY-MM-DD" (toISOString() would use UTC and shift the day in Chile). */
  toDateStr(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  },

  todayStr() {
    return this.toDateStr(new Date());
  },

  /** Parses "YYYY-MM-DD" as a local date at noon (safe from DST / timezone edges). */
  parseDate(dateStr) {
    const [y, m, d] = String(dateStr).split('-').map(Number);
    return new Date(y, (m || 1) - 1, d || 1, 12);
  },

  /** "YYYY-MM-DD" of the day after the given "YYYY-MM-DD". */
  nextDayStr(dateStr) {
    const d = this.parseDate(dateStr);
    d.setDate(d.getDate() + 1);
    return this.toDateStr(d);
  },

  /** Last day an event occupies. */
  eventEnd(ev) {
    return ev.end_date && ev.end_date >= ev.date ? ev.end_date : ev.date;
  },

  isPast(ev, today = this.todayStr()) {
    return this.eventEnd(ev) < today;
  },

  /** "sáb 10 de octubre de 2026" style label (optionally with end date range). */
  formatDateLong(ev) {
    const fmt = (s) => {
      const d = this.parseDate(s);
      return `${this.DOW_LONG[d.getDay()]} ${d.getDate()} de ${this.MONTH_NAMES[d.getMonth()].toLowerCase()} de ${d.getFullYear()}`;
    };
    const end = this.eventEnd(ev);
    return end !== ev.date ? `${fmt(ev.date)} al ${fmt(end)}` : fmt(ev.date);
  },

  /**
   * Normalizes a free-text discipline into a CSS key + short label.
   * key matches the .badge-<key> classes in style.css.
   */
  disciplineInfo(raw) {
    const clean = (raw || 'MTB').trim();
    const lower = this.normalize(clean);
    if (lower.includes('ultra') || lower.includes('bikepacking')) return { key: 'ultra', label: 'Ultra', full: clean };
    if (lower.includes('enduro')) return { key: 'enduro', label: 'Enduro', full: clean };
    if (lower.includes('descenso') || lower.includes('downhill') || /\bdh\b/.test(lower)) return { key: 'enduro', label: 'DH', full: clean };
    if (lower.includes('gravel')) return { key: 'gravel', label: 'Gravel', full: clean };
    if (lower.includes('ruta') || lower.includes('carretera')) return { key: 'ruta', label: 'Ruta', full: clean };
    if (lower.includes('mtb') || lower.includes('mountain')) return { key: 'mtb', label: 'MTB', full: clean };
    if (lower.includes('cicloturismo')) return { key: 'mtb', label: 'Turismo', full: clean };
    return { key: 'mtb', label: clean.length > 8 ? clean.substring(0, 7) : clean, full: clean };
  },

  /** Commune text without region suffixes ("Machalí - Región VI" -> "Machalí"). */
  cleanLocality(ev, fallback = '') {
    const raw = ev.commune || ev.location || '';
    const cleaned = raw
      .split(',')[0]
      .split(' - ')[0]
      .replace(/\b(Regi[oó]n\s+[A-Za-zÁÉÍÓÚáéíóúÑñ'\s]+)\b/gi, '')
      .trim();
    return cleaned || fallback;
  },

  /** Distances worth showing (hides the "Ver bases" placeholder). */
  distanceText(ev, sep = ' • ') {
    const list = Array.isArray(ev.distances) ? ev.distances : [];
    return list.length && list[0] !== 'Ver bases' ? list.join(sep) : '';
  }
};

window.Utils = Utils;
