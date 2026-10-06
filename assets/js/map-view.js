/**
 * Pedaleo.cl — Interactive Chile Map View
 * Displays cycling races by locality with dynamic auto-zoom based on user filters.
 * Built with Leaflet.js and CartoDB Positron tiles for a sober, fast experience.
 */

const MapView = {
  map: null,
  markersGroup: null,
  currentEvents: [],
  onSelectEventCallback: null,
  currentBoundsList: [],

  disciplineColors: {
    'mtb': '#166534',       // Forest Green
    'ruta': '#1e40af',      // Classic Blue
    'gravel': '#b45309',    // Warm Amber
    'ultra': '#7e22ce',     // Deep Purple
    'enduro': '#b91c1c',    // Crimson Red
    'default': '#0f766e'    // Dark Teal
  },

  regionCentroids: {
    'XV': { lat: -18.4783, lng: -70.3126, name: 'Arica y Parinacota' },
    'I': { lat: -20.2133, lng: -69.8850, name: 'Tarapacá' },
    'II': { lat: -23.6509, lng: -70.3975, name: 'Antofagasta' },
    'III': { lat: -27.3668, lng: -70.3323, name: 'Atacama' },
    'IV': { lat: -29.9027, lng: -71.2520, name: 'Coquimbo' },
    'V': { lat: -33.0472, lng: -71.6127, name: 'Valparaíso' },
    'RM': { lat: -33.4489, lng: -70.6693, name: 'Metropolitana' },
    'VI': { lat: -34.1708, lng: -70.7444, name: "O'Higgins" },
    'VII': { lat: -35.4264, lng: -71.6554, name: 'Maule' },
    'XVI': { lat: -36.6066, lng: -72.1034, name: 'Ñuble' },
    'VIII': { lat: -36.8270, lng: -73.0503, name: 'Biobío' },
    'IX': { lat: -38.7359, lng: -72.5904, name: 'La Araucanía' },
    'XIV': { lat: -39.8142, lng: -73.2459, name: 'Los Ríos' },
    'X': { lat: -41.4693, lng: -72.9424, name: 'Los Lagos' },
    'XI': { lat: -45.5752, lng: -72.0662, name: 'Aysén' },
    'XII': { lat: -53.1638, lng: -70.9171, name: 'Magallanes' }
  },

  getDisciplineColor(disciplines) {
    if (!disciplines || !disciplines.length) return this.disciplineColors.default;
    const first = (disciplines[0] || '').toLowerCase();
    for (const [key, color] of Object.entries(this.disciplineColors)) {
      if (first.includes(key)) return color;
    }
    return this.disciplineColors.default;
  },

  /**
   * Resolves coordinates: uses event lat/lng if present,
   * otherwise falls back to the regional centroid.
   */
  getEventLocation(ev) {
    const hasLat = typeof ev.lat === 'number' && !isNaN(ev.lat) && ev.lat !== 0;
    const hasLng = typeof ev.lng === 'number' && !isNaN(ev.lng) && ev.lng !== 0;

    if (hasLat && hasLng) {
      return {
        lat: ev.lat,
        lng: ev.lng,
        isCentroid: false,
        regionName: ev.region_name || 'Chile'
      };
    }

    const regCode = (ev.region || 'RM').toUpperCase();
    const centroid = this.regionCentroids[regCode] || this.regionCentroids['RM'];
    return {
      lat: centroid.lat,
      lng: centroid.lng,
      isCentroid: true,
      regionName: centroid.name
    };
  },

  init() {
    if (this.map) return; // Already initialized

    if (typeof L === 'undefined') {
      console.warn('Leaflet (L) is not loaded yet');
      return;
    }

    const mapElement = document.getElementById('pedaleo-chile-map');
    if (!mapElement) return;

    if (mapElement._leaflet_id) {
      delete mapElement._leaflet_id;
    }

    try {
      this.map = L.map('pedaleo-chile-map', {
        center: [-35.6751, -71.5430],
        zoom: 5,
        minZoom: 4,
        maxZoom: 16,
        zoomControl: false, // Usar control personalizado con títulos en español
        scrollWheelZoom: true
      });

      L.control.zoom({
        zoomInTitle: 'Acercar mapa',
        zoomOutTitle: 'Alejar mapa'
      }).addTo(this.map);

      // OpenStreetMap tiles: 100% libre, sin API key requerida ni marcas de agua
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> colaboradores',
        maxZoom: 19
      }).addTo(this.map);

      this.markersGroup = L.featureGroup().addTo(this.map);

      // Re-render markers on zoom level change to switch between cluster and dispersed pins
      this.map.on('zoomend', () => {
        if (this.currentEvents && this.currentEvents.length) {
          this.renderMarkersLayers();
        }
      });
    } catch (err) {
      console.error('Error initializing Leaflet map:', err);
    }
  },

  show(events, onSelectEvent) {
    this.currentEvents = events;
    this.onSelectEventCallback = onSelectEvent;

    this.init();

    // Update markers and trigger invalidateSize on next tick after visibility change
    this.updateMarkers(events);

    setTimeout(() => {
      if (this.map) {
        this.map.invalidateSize();
        if (this.currentBoundsList && this.currentBoundsList.length) {
          this.autoZoom(this.currentBoundsList);
        }
      }
    }, 120);
  },

  updateMarkers(events) {
    this.init();
    if (!this.map || !this.markersGroup) return;

    this.currentEvents = events;

    // Update counter text
    const counterEl = document.getElementById('map-counter-text');
    if (counterEl) {
      counterEl.textContent = `${events.length} carrera${events.length === 1 ? '' : 's'} geolocalizada${events.length === 1 ? '' : 's'}`;
    }

    if (!events.length) {
      this.markersGroup.clearLayers();
      this.currentBoundsList = [];
      this.map.setView([-35.6751, -71.5430], 5);
      const grid = document.getElementById('map-localities-grid');
      if (grid) {
        grid.innerHTML = '<p class="map-empty-note">No hay carreras para mostrar con los filtros activos.</p>';
      }
      return;
    }

    // Group events by locality coordinates (round to 3 decimals to cluster points in same town/centroid)
    this.localityGroups = {};
    events.forEach(ev => {
      const loc = this.getEventLocation(ev);
      const key = `${loc.lat.toFixed(3)},${loc.lng.toFixed(3)}`;

      if (!this.localityGroups[key]) {
        let rawLoc = ev.commune || ev.location || '';
        let cleanCom = rawLoc
          .split(',')[0]
          .split('-')[0]
          .replace(/\b(Regi[oó]n\s+[A-Za-z\s]+|RM|XV|XVI|XIV|XII|XI|VIII|VII|VI|IV|III|II|I|X|V)\b/gi, '')
          .trim();

        if (loc.isCentroid || !cleanCom) {
          cleanCom = `${loc.regionName}`;
        }

        this.localityGroups[key] = {
          key: key,
          lat: loc.lat,
          lng: loc.lng,
          commune: cleanCom,
          regionName: loc.regionName,
          isCentroid: loc.isCentroid,
          events: []
        };
      }
      this.localityGroups[key].events.push(ev);
    });

    const markerBounds = Object.values(this.localityGroups).map(g => [g.lat, g.lng]);
    this.currentBoundsList = markerBounds;

    // Render layers according to current zoom
    this.renderMarkersLayers();

    // Render Localities Quick Grid below the map
    this.renderLocalitiesGrid(this.localityGroups);

    // Auto-zoom dynamic logic
    this.autoZoom(markerBounds);
  },

  /**
   * Renders map markers:
   * - If zoom < 11: renders consolidated cluster pins per locality/centroid with count badges.
   * - If zoom >= 11: resolves multiple races at the exact same location by fanning them out (radial spiderfy).
   */
  renderMarkersLayers() {
    if (!this.map || !this.markersGroup || !this.localityGroups) return;
    this.markersGroup.clearLayers();

    const currentZoom = this.map.getZoom();
    const isDetailedZoom = currentZoom >= 11;

    Object.values(this.localityGroups).forEach(group => {
      const count = group.events.length;
      const primaryColor = this.getDisciplineColor(group.events[0].disciplines);

      // Single event OR zoomed-out multi-event: render consolidated cluster pin
      if (count === 1 || !isDetailedZoom) {
        const iconHtml = `
          <div class="custom-map-pin ${count > 1 ? 'is-cluster' : ''} ${group.isCentroid ? 'is-centroid' : ''}" style="--pin-color: ${primaryColor}" title="${count > 1 ? `${count} carreras en ${group.commune}` : group.events[0].name}">
            <div class="pin-bubble">
              <span class="pin-symbol">🚴</span>
              ${count > 1 ? `<span class="pin-count">${count}</span>` : ''}
            </div>
            <div class="pin-arrow"></div>
          </div>
        `;

        const customIcon = L.divIcon({
          className: 'leaflet-custom-marker',
          html: iconHtml,
          iconSize: [36, 42],
          iconAnchor: [18, 42],
          popupAnchor: [0, -40]
        });

        const marker = L.marker([group.lat, group.lng], { icon: customIcon });
        marker.bindPopup(this.createGroupPopupHtml(group), {
          maxWidth: 320,
          className: 'pedaleo-popup'
        });

        marker.on('popupopen', () => this.attachPopupListeners());

        // Clicking a cluster at zoom < 11 zooms in to separate the races
        if (count > 1) {
          marker.on('click', () => {
            if (this.map.getZoom() < 11) {
              this.map.flyTo([group.lat, group.lng], 12, { duration: 0.6 });
            }
          });
        }

        this.markersGroup.addLayer(marker);
      } else {
        // Detailed Zoom (>= 11) with multiple events at the SAME location:
        // Resolve overlap using radial spiderfy dispersion so every race has its own visible pin
        const radiusKm = count > 8 ? 0.6 : 0.38;

        group.events.forEach((ev, idx) => {
          const angle = (2 * Math.PI * idx) / count;
          const latOffset = (radiusKm / 111.32) * Math.cos(angle);
          const lngOffset = (radiusKm / (111.32 * Math.cos(group.lat * Math.PI / 180))) * Math.sin(angle);
          const mLat = group.lat + latOffset;
          const mLng = group.lng + lngOffset;

          const discColor = this.getDisciplineColor(ev.disciplines);
          const discShort = ev.disciplines[0] ? ev.disciplines[0].substring(0, 3).toUpperCase() : 'MTB';

          const singlePinHtml = `
            <div class="custom-map-pin single-race-pin ${group.isCentroid ? 'is-centroid' : ''}" style="--pin-color: ${discColor}" title="${ev.name} (${ev.disciplines[0] || 'MTB'})">
              <div class="pin-bubble">
                <span class="pin-symbol">🚴</span>
                <span class="pin-disc-mini">${discShort}</span>
              </div>
              <div class="pin-arrow"></div>
            </div>
          `;

          const singleIcon = L.divIcon({
            className: 'leaflet-custom-marker',
            html: singlePinHtml,
            iconSize: [36, 42],
            iconAnchor: [18, 42],
            popupAnchor: [0, -40]
          });

          const singleMarker = L.marker([mLat, mLng], { icon: singleIcon });
          singleMarker.bindPopup(this.createSingleEventPopupHtml(ev, group), {
            maxWidth: 320,
            className: 'pedaleo-popup'
          });

          singleMarker.on('popupopen', () => this.attachPopupListeners());
          this.markersGroup.addLayer(singleMarker);
        });
      }
    });
  },

  createGroupPopupHtml(group) {
    let popupHtml = `
      <div class="map-popup-card">
        <header class="map-popup-header">
          <h4 class="map-popup-commune">${group.commune}</h4>
          <span class="map-popup-region">${group.regionName}</span>
          ${group.isCentroid ? '<span class="map-ref-tag">📍 Referencia Regional</span>' : ''}
        </header>
        <div class="map-popup-list">
    `;

    group.events.forEach(ev => {
      const discColor = this.getDisciplineColor(ev.disciplines);
      const distText = ev.distances && ev.distances.length && ev.distances[0] !== 'Ver bases'
        ? ev.distances.join(' • ')
        : '';
      const elevText = ev.elevation_gain_m ? `+${ev.elevation_gain_m}m` : '';

      popupHtml += `
        <div class="map-popup-race-item">
          <div class="map-popup-race-top">
            <span class="map-race-disc-tag" style="background:${discColor}15; color:${discColor}; border-color:${discColor}40">
              ${ev.disciplines[0] || 'MTB'}
            </span>
            <span class="map-race-date">${ev.date}</span>
          </div>
          <div class="map-popup-race-name">${ev.name}</div>
          <div class="map-popup-race-meta">
            ${distText ? `<span>🏁 ${distText}</span>` : ''}
            ${elevText ? `<span>⛰️ ${elevText}</span>` : ''}
          </div>
          <div class="map-popup-actions">
            <button class="map-btn-detail" data-id="${ev.id}">Ver Ficha</button>
            <a href="${ev.registration_url || ev.url}" target="_blank" rel="noopener" class="map-btn-register">Inscripción &rarr;</a>
          </div>
        </div>
      `;
    });

    if (group.events.length > 1) {
      popupHtml += `
        <button class="map-spiderfy-btn" data-lat="${group.lat}" data-lng="${group.lng}">
          🔍 Separar ${group.events.length} carreras en el mapa
        </button>
      `;
    }

    popupHtml += `
        </div>
      </div>
    `;

    return popupHtml;
  },

  createSingleEventPopupHtml(ev, group) {
    const discColor = this.getDisciplineColor(ev.disciplines);
    const distText = ev.distances && ev.distances.length && ev.distances[0] !== 'Ver bases'
      ? ev.distances.join(' • ')
      : '';
    const elevText = ev.elevation_gain_m ? `+${ev.elevation_gain_m}m` : '';

    return `
      <div class="map-popup-card">
        <header class="map-popup-header">
          <h4 class="map-popup-commune">${group.commune}</h4>
          <span class="map-popup-region">${group.regionName}</span>
          ${group.isCentroid ? '<span class="map-ref-tag">📍 Referencia Regional</span>' : ''}
        </header>
        <div class="map-popup-list">
          <div class="map-popup-race-item">
            <div class="map-popup-race-top">
              <span class="map-race-disc-tag" style="background:${discColor}15; color:${discColor}; border-color:${discColor}40">
                ${ev.disciplines[0] || 'MTB'}
              </span>
              <span class="map-race-date">${ev.date}</span>
            </div>
            <div class="map-popup-race-name" style="font-size:1rem; font-weight:800">${ev.name}</div>
            <div class="map-popup-race-meta">
              ${distText ? `<span>🏁 ${distText}</span>` : ''}
              ${elevText ? `<span>⛰️ ${elevText}</span>` : ''}
            </div>
            <div class="map-popup-actions" style="margin-top:0.75rem">
              <button class="map-btn-detail" data-id="${ev.id}">Ver Ficha Completa</button>
              <a href="${ev.registration_url || ev.url}" target="_blank" rel="noopener" class="map-btn-register">Inscripción &rarr;</a>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  attachPopupListeners() {
    document.querySelectorAll('.map-btn-detail').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.currentTarget.dataset.id;
        const ev = this.currentEvents.find(item => item.id === id);
        if (ev && this.onSelectEventCallback) {
          this.onSelectEventCallback(ev);
        }
      });
    });

    document.querySelectorAll('.map-spiderfy-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const lat = parseFloat(e.currentTarget.dataset.lat);
        const lng = parseFloat(e.currentTarget.dataset.lng);
        if (this.map && !isNaN(lat) && !isNaN(lng)) {
          this.map.flyTo([lat, lng], 12, { duration: 0.6 });
        }
      });
    });
  },

  autoZoom(boundsList) {
    if (!this.map || !boundsList.length) {
      this.map.setView([-35.6751, -71.5430], 5);
      return;
    }

    try {
      if (boundsList.length === 1) {
        this.map.flyTo(boundsList[0], 11, {
          duration: 0.8,
          easeLinearity: 0.25
        });
      } else {
        const bounds = L.latLngBounds(boundsList);
        this.map.flyToBounds(bounds, {
          padding: [50, 50],
          maxZoom: 12,
          duration: 0.8
        });
      }
    } catch (e) {
      console.warn('Error in autoZoom:', e);
    }
  },

  renderLocalitiesGrid(localityGroups) {
    const grid = document.getElementById('map-localities-grid');
    if (!grid) return;

    const list = Object.values(localityGroups).sort((a, b) => b.events.length - a.events.length);
    let html = '';

    list.forEach(group => {
      html += `
        <div class="map-locality-card" data-lat="${group.lat}" data-lng="${group.lng}">
          <div class="loc-card-header">
            <strong>${group.commune}</strong>
            <span class="loc-badge">${group.events.length}</span>
          </div>
          <div class="loc-card-region">${group.regionName}${group.isCentroid ? ' · Referencia Regional' : ''}</div>
          <div class="loc-card-races">
            ${group.events.slice(0, 2).map(e => `<span>• ${e.name}</span>`).join('')}
            ${group.events.length > 2 ? `<span class="loc-more">+${group.events.length - 2} más</span>` : ''}
          </div>
        </div>
      `;
    });

    grid.innerHTML = html;

    // Clicking a locality card flies the map right to it and opens its marker popup
    grid.querySelectorAll('.map-locality-card').forEach(card => {
      card.addEventListener('click', (e) => {
        const lat = parseFloat(e.currentTarget.dataset.lat);
        const lng = parseFloat(e.currentTarget.dataset.lng);
        if (this.map && !isNaN(lat) && !isNaN(lng)) {
          this.map.flyTo([lat, lng], 12, { duration: 0.6 });
          this.markersGroup.eachLayer(layer => {
            const pos = layer.getLatLng();
            if (Math.abs(pos.lat - lat) < 0.001 && Math.abs(pos.lng - lng) < 0.001) {
              layer.openPopup();
            }
          });
          document.getElementById('pedaleo-chile-map')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      });
    });
  }
};
