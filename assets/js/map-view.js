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

  getDisciplineColor(disciplines) {
    if (!disciplines || !disciplines.length) return this.disciplineColors.default;
    const first = (disciplines[0] || '').toLowerCase();
    for (const [key, color] of Object.entries(this.disciplineColors)) {
      if (first.includes(key)) return color;
    }
    return this.disciplineColors.default;
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
        zoomControl: true,
        scrollWheelZoom: true
      });

      // OpenStreetMap tiles: 100% libre, sin API key requerida ni marcas de agua
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
      }).addTo(this.map);

      this.markersGroup = L.featureGroup().addTo(this.map);
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

    this.markersGroup.clearLayers();
    this.currentEvents = events;

    // Update counter text
    const counterEl = document.getElementById('map-counter-text');
    if (counterEl) {
      counterEl.textContent = `${events.length} carrera${events.length === 1 ? '' : 's'} geolocalizada${events.length === 1 ? '' : 's'}`;
    }

    if (!events.length) {
      this.currentBoundsList = [];
      this.map.setView([-35.6751, -71.5430], 5);
      const grid = document.getElementById('map-localities-grid');
      if (grid) {
        grid.innerHTML = '<p class="map-empty-note">No hay carreras para mostrar con los filtros activos.</p>';
      }
      return;
    }

    // Group events by locality coordinates (round to 3 decimals to cluster points in same town)
    const localityGroups = {};
    events.forEach(ev => {
      const lat = typeof ev.lat === 'number' && !isNaN(ev.lat) ? ev.lat : -33.4489;
      const lng = typeof ev.lng === 'number' && !isNaN(ev.lng) ? ev.lng : -70.6693;
      const key = `${lat.toFixed(3)},${lng.toFixed(3)}`;

      if (!localityGroups[key]) {
        // Clean commune name
        let rawLoc = ev.commune || ev.location || '';
        let cleanCom = rawLoc.split(',')[0].split('-')[0].replace(/\b(Regi[oó]n\s+[A-Za-z\s]+|RM|XV|XVI|XIV|XII|XI|VIII|VII|VI|IV|III|II|I|X|V)\b/gi, '').trim();
        if (!cleanCom) cleanCom = ev.region_name || 'Chile';

        localityGroups[key] = {
          lat: lat,
          lng: lng,
          commune: cleanCom,
          region: ev.region || '',
          events: []
        };
      }
      localityGroups[key].events.push(ev);
    });

    const markerBounds = [];

    // Create a marker for each locality
    Object.values(localityGroups).forEach(group => {
      markerBounds.push([group.lat, group.lng]);

      const count = group.events.length;
      const primaryColor = this.getDisciplineColor(group.events[0].disciplines);

      // Create Custom SVG Pin
      const iconHtml = `
        <div class="custom-map-pin" style="--pin-color: ${primaryColor}">
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

      // Construct Popup Content
      let popupHtml = `
        <div class="map-popup-card">
          <header class="map-popup-header">
            <h4 class="map-popup-commune">${group.commune}</h4>
            <span class="map-popup-region">Región ${group.region}</span>
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

      popupHtml += `
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml, {
        maxWidth: 320,
        className: 'pedaleo-popup'
      });

      marker.on('popupopen', () => {
        document.querySelectorAll('.map-btn-detail').forEach(btn => {
          btn.addEventListener('click', (e) => {
            const id = e.currentTarget.dataset.id;
            const ev = this.currentEvents.find(item => item.id === id);
            if (ev && this.onSelectEventCallback) {
              this.onSelectEventCallback(ev);
            }
          });
        });
      });

      this.markersGroup.addLayer(marker);
    });

    this.currentBoundsList = markerBounds;

    // Render Localities Quick Grid below the map
    this.renderLocalitiesGrid(localityGroups);

    // Auto-zoom dynamic logic
    this.autoZoom(markerBounds);
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
          <div class="loc-card-region">Región ${group.region}</div>
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
