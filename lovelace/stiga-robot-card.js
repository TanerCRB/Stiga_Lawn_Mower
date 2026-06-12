/**
 * Stiga Robot Card — Home Assistant Lovelace custom card
 *
 * Installation:
 *   1. Copy this file to <HA config>/www/stiga-robot-card.js
 *   2. Settings → Dashboards → Resources → Add
 *      URL: /local/stiga-robot-card.js  Type: JavaScript module
 *   3. Add to a dashboard:
 *
 *   type: custom:stiga-robot-card
 *   entity_prefix: bob          # robot name from STIGA app (lowercase)
 *
 * Optional overrides (if HA renamed any entity):
 *   lawn_mower:        lawn_mower.bob
 *   tracker:           device_tracker.bob_location
 *   status:            sensor.bob_status
 */

(function () {
  /* ── Leaflet CDN + Google satellite tiles ────────────────────────────── */
  const LEAFLET_JS   = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  const LEAFLET_CSS  = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
  // Google satellite + labels tiles (no API key required for personal use)
  const TILE_URL     = 'https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}';
  const TILE_OPTIONS = { subdomains: '0123', maxZoom: 22, maxNativeZoom: 20 };

  function loadLeaflet() {
    return new Promise((resolve) => {
      if (window.L) { resolve(); return; }
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = LEAFLET_CSS;
      document.head.appendChild(link);
      const script = document.createElement('script');
      script.src = LEAFLET_JS;
      script.onload = resolve;
      document.head.appendChild(script);
    });
  }

  /* ── Status configuration ─────────────────────────────────────────────── */
  const STATUS = {
    mowing:               { label: 'Mowing',           color: '#34a853', pulse: true  },
    planning:             { label: 'Planning',          color: '#34a853', pulse: true  },
    cutting_border:       { label: 'Cutting Border',    color: '#34a853', pulse: true  },
    navigating_to_area:   { label: 'Going to Zone',     color: '#1a73e8', pulse: false },
    reaching_first_point: { label: 'Positioning',       color: '#1a73e8', pulse: false },
    going_home:           { label: 'Going Home',        color: '#1a73e8', pulse: false },
    storing_data:         { label: 'Storing Data',      color: '#1a73e8', pulse: false },
    charging:             { label: 'Charging',          color: '#fbbc04', pulse: false },
    docked:               { label: 'Docked',            color: '#fbbc04', pulse: false },
    waiting_for_command:  { label: 'Idle',              color: '#80868b', pulse: false },
    calibration:          { label: 'Calibrating',       color: '#a142f4', pulse: false },
    blades_calibration:   { label: 'Blade Calibration', color: '#a142f4', pulse: false },
    docking_calibration:  { label: 'Dock Calibration',  color: '#a142f4', pulse: false },
    updating:             { label: 'Updating',          color: '#a142f4', pulse: false },
    error:                { label: 'Error',             color: '#ea4335', pulse: true  },
    blocked:              { label: 'Blocked',           color: '#ea4335', pulse: true  },
    lid_open:             { label: 'Lid Open',          color: '#ea4335', pulse: true  },
    startup_required:     { label: 'Startup Required',  color: '#ea4335', pulse: true  },
  };

  /* ── Leaflet marker: arrow pointing in heading direction ─────────────── */
  function robotIcon(color, heading) {
    const r = (heading == null || isNaN(heading)) ? 0 : heading;
    return L.divIcon({
      className: '',
      html: `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="-18 -18 36 36">
        <g transform="rotate(${r})">
          <polygon points="0,-14 10,10 0,5 -10,10"
                   fill="${color}" stroke="white" stroke-width="2.5"
                   stroke-linejoin="round"/>
        </g>
      </svg>`,
      iconSize:   [36, 36],
      iconAnchor: [18, 18],
    });
  }

  /* ── Leaflet marker: base/docking station ────────────────────────────── */
  function dockIcon() {
    return L.divIcon({
      className: '',
      html: `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="32" viewBox="0 0 24 28">
        <filter id="ds" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="1" flood-opacity=".4"/>
        </filter>
        <g filter="url(#ds)">
          <path d="M12 2L2 10h3v10h5v-6h4v6h5V10h3z" fill="#1a73e8" stroke="white" stroke-width="1.2" stroke-linejoin="round"/>
          <rect x="9" y="16" width="6" height="4" rx="1" fill="white" opacity=".6"/>
        </g>
      </svg>`,
      iconSize:   [28, 32],
      iconAnchor: [14, 32],
    });
  }

  /* ── Card HTML + CSS (shadow DOM) ────────────────────────────────────── */
  const TEMPLATE = `
  <style>
    :host { display: block; }
    * { box-sizing: border-box; margin: 0; padding: 0; }

    .card {
      background: var(--ha-card-background, var(--card-background-color, #fff));
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,.12));
      overflow: hidden;
      font-family: var(--primary-font-family, Roboto, sans-serif);
      color: var(--primary-text-color, #212121);
    }

    /* ── Header ── */
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px 10px;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .robot-name {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;
    }
    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--secondary-text-color, #757575);
    }
    .conn-dot {
      width: 10px; height: 10px;
      border-radius: 50%;
      background: #bdbdbd;
      transition: background .4s;
    }
    .conn-dot.online { background: #34a853; }

    /* ── Status ── */
    .status-row {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px 16px 10px;
    }
    .status-dot {
      width: 14px; height: 14px;
      border-radius: 50%;
      background: #bdbdbd;
      flex-shrink: 0;
      transition: background .4s;
    }
    .status-dot.pulse { animation: blink 1.4s ease-in-out infinite; }
    @keyframes blink {
      0%, 100% { opacity: 1;   transform: scale(1);    }
      50%       { opacity: .45; transform: scale(.78);  }
    }
    .status-label {
      font-size: 20px;
      font-weight: 600;
    }

    /* ── Progress bars ── */
    .progress-section { padding: 4px 16px 14px; }
    .progress-row { margin-bottom: 10px; }
    .progress-header {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: var(--secondary-text-color, #757575);
      margin-bottom: 5px;
    }
    .progress-track {
      height: 9px;
      border-radius: 5px;
      background: var(--divider-color, #e0e0e0);
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      border-radius: 5px;
      width: 0%;
      transition: width .7s ease, background .5s;
    }

    /* ── Map ── */
    #map-wrap {
      height: 280px;
      position: relative;
      overflow: hidden;
      border-top: 1px solid var(--divider-color, #e0e0e0);
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    #the-map { position: absolute; inset: 0; }
    .map-msg {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      color: var(--secondary-text-color, #757575);
      background: var(--secondary-background-color, #f5f5f5);
      text-align: center;
      padding: 24px;
      z-index: 10;
    }
    .map-msg.hidden { display: none; }

    /* ── Stats grid ── */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
    }
    .stat-cell {
      padding: 12px 6px;
      text-align: center;
      border-right: 1px solid var(--divider-color, #e0e0e0);
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .stat-cell:nth-child(3n) { border-right: none; }
    .stat-cell:nth-last-child(-n+3) { border-bottom: none; }
    .stat-value {
      font-size: 18px;
      font-weight: 600;
      line-height: 1.2;
    }
    .stat-value.dim { color: var(--disabled-text-color, #bdbdbd); }
    .stat-label {
      font-size: 10px;
      color: var(--secondary-text-color, #757575);
      text-transform: uppercase;
      letter-spacing: .5px;
      margin-top: 3px;
    }

    /* ── Action buttons ── */
    .actions {
      display: flex;
      gap: 8px;
      padding: 12px 16px;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .btn {
      flex: 1;
      padding: 10px 6px;
      border: none;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity .15s, transform .1s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
    }
    .btn:hover  { opacity: .88; }
    .btn:active { transform: scale(.95); opacity: .75; }
    .btn-start { background: #34a853; color: #fff; }
    .btn-stop  { background: var(--secondary-background-color, #f1f3f4);
                 color: var(--primary-text-color); }
    .btn-dock  { background: #1a73e8; color: #fff; }
  </style>

  <div class="card">

    <div class="header">
      <span class="robot-name">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" opacity=".75">
          <path d="M12 2a2 2 0 012 2 2 2 0 01-2 2 2 2 0 01-2-2 2 2 0 012-2m0
                   5c2.67 0 8 1.34 8 4v2H4V11c0-2.66 5.33-4 8-4zm8
                   7v7a1 1 0 01-1 1H5a1 1 0 01-1-1v-7h2v2h2v-2h8v2h2v-2h2z"/>
        </svg>
        <span class="js-name">Robot</span>
      </span>
      <span class="header-right">
        <span class="js-conn-label">Offline</span>
        <span class="conn-dot js-conn-dot"></span>
      </span>
    </div>

    <div class="status-row">
      <span class="status-dot js-status-dot"></span>
      <span class="status-label js-status-label">—</span>
    </div>

    <div class="progress-section">
      <div class="progress-row">
        <div class="progress-header">
          <span>🔋 Battery</span>
          <span class="js-batt-val">—</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill js-batt-fill" style="background:#34a853"></div>
        </div>
      </div>
      <div class="progress-row">
        <div class="progress-header">
          <span>🌿 Garden</span>
          <span class="js-garden-val">—</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill js-garden-fill" style="background:#1a73e8"></div>
        </div>
      </div>
    </div>

    <div id="map-wrap">
      <div id="the-map"></div>
      <div class="map-msg js-map-msg">Loading map…</div>
    </div>

    <div class="stats-grid">
      <div class="stat-cell">
        <div class="stat-value js-zone">—</div>
        <div class="stat-label">Zone</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value js-zone-pct">—</div>
        <div class="stat-label">Zone %</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value js-sats">—</div>
        <div class="stat-label">Satellites</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value js-rtk">—</div>
        <div class="stat-label">RTK %</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value js-area">—</div>
        <div class="stat-label">Garden m²</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value js-rssi">—</div>
        <div class="stat-label">RSSI dBm</div>
      </div>
    </div>

    <div class="actions">
      <button class="btn btn-start" data-action="start_mowing">▶ Start</button>
      <button class="btn btn-stop"  data-action="pause">■ Stop</button>
      <button class="btn btn-dock"  data-action="dock">⌂ Dock</button>
    </div>

  </div>`;

  /* ── Card class ──────────────────────────────────────────────────────── */
  class StigaRobotCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._hass          = null;
      this._config        = null;
      this._map           = null;
      this._marker        = null;
      this._firstView     = true;
      this._baseMarker    = null;
      this._zoneLayers    = [];
      this._obstacleLayers = [];
      this._perimeterKey  = null;
      this._dockLat       = null;
      this._dockLon       = null;
    }

    /* Called once by HA when the card config is parsed */
    setConfig(config) {
      if (!config.entity_prefix) throw new Error('stiga-robot-card: entity_prefix is required');
      this._config = config;
      this.shadowRoot.innerHTML = TEMPLATE;
      this._applyLayout();
      this._bindButtons();
      if (config.show_map !== false) {
        loadLeaflet().then(() => this._initMap());
      }
    }

    /* Apply layout config options (visibility, map height) */
    _applyLayout() {
      const c = this._config;

      // Map height (default 280px)
      if (c.map_height != null) {
        const wrap = this._$('#map-wrap');
        if (wrap) wrap.style.height = `${parseInt(c.map_height, 10)}px`;
      }

      // Section visibility
      const vis = (sel, flag) => {
        const el = this._$(sel);
        if (el) el.style.display = flag === false ? 'none' : '';
      };
      vis('#map-wrap',         c.show_map      !== false);
      vis('.progress-section', c.show_progress !== false);
      vis('.stats-grid',       c.show_stats    !== false);
      vis('.actions',          c.show_buttons  !== false);
    }

    /* Called by HA on every state change */
    set hass(hass) {
      this._hass = hass;
      if (this._config) this._update();
    }

    /* ── Helpers ── */
    _eid(key, defaultSuffix) {
      return this._config[key] || `${defaultSuffix.split('.')[0]}.${this._config.entity_prefix}_${defaultSuffix.split('.')[1] || defaultSuffix}`;
    }

    _entity(suffix) {
      // suffix like "sensor.status" → "sensor.bob_status"
      const [domain, name] = suffix.split('.');
      const override = this._config[name] || this._config[suffix];
      if (override) return this._hass?.states[override];
      return this._hass?.states[`${domain}.${this._config.entity_prefix}_${name}`];
    }

    _state(suffix) { return this._entity(suffix)?.state; }
    _attr(suffix, a) { return this._entity(suffix)?.attributes?.[a]; }
    _$(s) { return this.shadowRoot.querySelector(s); }

    /* ── Button wiring ── */
    _bindButtons() {
      this.shadowRoot.querySelectorAll('.btn[data-action]').forEach(btn => {
        btn.addEventListener('click', () => {
          const prefix = this._config.entity_prefix;
          const entityId = this._config.lawn_mower || `lawn_mower.${prefix}`;
          this._hass?.callService('lawn_mower', btn.dataset.action, { entity_id: entityId });
        });
      });
    }

    /* ── Leaflet init ── */
    _initMap() {
      const mapEl = this._$('#the-map');
      if (!mapEl || this._map) return;

      // Leaflet CSS must be inside the shadow root — document.head styles
      // do not cross the Shadow DOM boundary, so tiles and controls render
      // unstyled (blank) without this injection.
      if (!this.shadowRoot.querySelector('link[data-leaflet-css]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = LEAFLET_CSS;
        link.setAttribute('data-leaflet-css', '');
        this.shadowRoot.insertBefore(link, this.shadowRoot.firstChild);
      }

      const map = L.map(mapEl, {
        zoomControl: true,
        attributionControl: false,
        zoom: 19,
        center: [51.505, -0.09],  // temporary center; panned on first fix
      });

      L.tileLayer(TILE_URL, TILE_OPTIONS).addTo(map);

      this._map = map;

      // Leaflet must recompute its viewport after the card is painted.
      // rAF handles normal render; 400 ms timeout is a fallback for cards
      // inside inactive dashboard tabs or collapsed conditional cards.
      requestAnimationFrame(() => map.invalidateSize());
      setTimeout(() => map.invalidateSize(), 400);

      // Keep the map correct when the card is revealed later (tab switch, etc.)
      new ResizeObserver(() => map.invalidateSize())
        .observe(this._$('#map-wrap'));

      if (this._hass) this._update();  // apply buffered state
    }

    /* ── Base station marker ── */
    _updateBaseMarker(lat, lon) {
      if (!this._map || lat == null || lon == null || isNaN(lat) || isNaN(lon)) return;
      if (this._baseMarker) {
        this._baseMarker.setLatLng([lat, lon]);
      } else {
        this._baseMarker = L.marker([lat, lon], { icon: dockIcon(), zIndexOffset: -200 })
          .addTo(this._map)
          .bindTooltip('Base Station', { permanent: false, direction: 'top', offset: [0, -28] });
      }
    }

    /* ── Zone / obstacle polygon layers ── */
    _updatePerimeters(zones, obstacles) {
      if (!this._map) return;
      const key = `${zones.length}:${obstacles.length}:${(zones[0]?.id ?? '')}`;
      if (key === this._perimeterKey) return;
      this._perimeterKey = key;

      this._zoneLayers.forEach(l => l.remove());
      this._obstacleLayers.forEach(l => l.remove());
      this._zoneLayers    = [];
      this._obstacleLayers = [];

      for (const zone of zones) {
        if (!zone.polygon || zone.polygon.length < 3) continue;
        const poly = L.polygon(zone.polygon, {
          color:       '#34a853',
          weight:      2,
          fillColor:   '#34a853',
          fillOpacity: 0.15,
        }).addTo(this._map);
        poly.bindTooltip(zone.name, { permanent: false, direction: 'center', className: 'stiga-tip' });
        this._zoneLayers.push(poly);
      }

      for (const obs of obstacles) {
        if (!obs.polygon || obs.polygon.length < 3) continue;
        const poly = L.polygon(obs.polygon, {
          color:       '#ea4335',
          weight:      2,
          fillColor:   '#ea4335',
          fillOpacity: 0.25,
          dashArray:   '5 4',
        }).addTo(this._map);
        poly.bindTooltip(obs.name || 'Obstacle', { permanent: false, direction: 'center', className: 'stiga-tip' });
        this._obstacleLayers.push(poly);
      }
    }

    /* ── Map marker update ── */
    _updateMap(lat, lon, heading, color) {
      if (!this._map) return;

      const msg = this._$('.js-map-msg');
      if (lat == null || lon == null || isNaN(lat) || isNaN(lon)) {
        if (msg) { msg.textContent = 'Configure base station coordinates to show GPS position'; msg.classList.remove('hidden'); }
        return;
      }
      if (msg) msg.classList.add('hidden');

      const icon    = robotIcon(color, heading);
      const latlng  = [lat, lon];

      if (this._marker) {
        this._marker.setLatLng(latlng);
        this._marker.setIcon(icon);
      } else {
        this._marker = L.marker(latlng, { icon }).addTo(this._map);
      }

      if (this._firstView) {
        this._map.setView(latlng, 19);
        this._firstView = false;
      } else {
        this._map.panTo(latlng, { animate: true, duration: 0.8 });
      }
    }

    /* ── Main update — called on every HA state push ── */
    _update() {
      if (!this._hass || !this._config) return;
      const p = this._config.entity_prefix;

      /* Robot name from device friendly_name */
      const rawName = this._attr('sensor.status', 'friendly_name') || '';
      const name    = rawName.replace(/\s*status\s*/i, '').trim() || p.toUpperCase();
      this._$('.js-name').textContent = name;

      /* Cloud connection */
      const online = this._state('binary_sensor.cloud_connection') === 'on';
      this._$('.js-conn-dot').classList.toggle('online', online);
      this._$('.js-conn-label').textContent = online ? 'Online' : 'Offline';

      /* Status badge */
      const statusVal = this._state('sensor.status') || 'unknown';
      const cfg       = STATUS[statusVal] || {
        label: statusVal.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        color: '#80868b',
        pulse: false,
      };
      const dot = this._$('.js-status-dot');
      dot.style.background = cfg.color;
      dot.classList.toggle('pulse', cfg.pulse);
      this._$('.js-status-label').textContent = cfg.label;
      this._$('.js-status-label').style.color  = cfg.color;

      /* Battery progress */
      const batt = parseFloat(this._state('sensor.battery'));
      if (!isNaN(batt)) {
        const battColor = batt < 20 ? '#ea4335' : batt < 50 ? '#fbbc04' : '#34a853';
        this._$('.js-batt-fill').style.width      = `${Math.min(batt, 100)}%`;
        this._$('.js-batt-fill').style.background = battColor;
        this._$('.js-batt-val').textContent = `${batt.toFixed(0)}%`;
      }

      /* Garden completion progress */
      const garden = parseFloat(this._state('sensor.garden_completed'));
      if (!isNaN(garden)) {
        this._$('.js-garden-fill').style.width = `${Math.min(garden, 100)}%`;
        this._$('.js-garden-val').textContent  = `${garden.toFixed(0)}%`;
      }

      /* Stats helper */
      const set = (sel, raw, fmt) => {
        const el = this._$(sel);
        if (!el) return;
        const ok = raw != null && raw !== 'unknown' && raw !== 'unavailable' && raw !== '';
        el.textContent = ok ? (fmt ? fmt(raw) : raw) : '—';
        el.classList.toggle('dim', !ok);
      };

      set('.js-zone',     this._state('sensor.zone'));
      set('.js-zone-pct', this._state('sensor.zone_completed'), v => `${parseFloat(v).toFixed(0)}%`);
      set('.js-sats',     this._state('sensor.gps_satellites'));
      set('.js-rtk',      this._state('sensor.rtk_quality'));
      set('.js-area',     this._state('sensor.garden_area'),    v => `${parseFloat(v).toFixed(0)}`);
      set('.js-rssi',     this._state('sensor.rssi'));

      /* Map: read from device_tracker attributes */
      const tracker  = this._hass.states[
        this._config.tracker || `device_tracker.${p}_location`
      ];
      const lat      = tracker?.attributes?.latitude;
      const lon      = tracker?.attributes?.longitude;
      const heading  = tracker?.attributes?.heading;
      const baseLat  = tracker?.attributes?.base_station_lat;
      const baseLon  = tracker?.attributes?.base_station_lon;
      const zones    = tracker?.attributes?.zone_polygons     || [];
      const obstacles = tracker?.attributes?.obstacle_polygons || [];

      // When docked/charging the robot IS at the dock — remember that position.
      // Falls back to HA-configured base coords if robot was never seen docked.
      if ((statusVal === 'charging' || statusVal === 'docked') && lat != null && lon != null) {
        this._dockLat = lat;
        this._dockLon = lon;
      }
      const dockLat = this._dockLat ?? baseLat;
      const dockLon = this._dockLon ?? baseLon;

      this._updatePerimeters(zones, obstacles);
      this._updateBaseMarker(dockLat, dockLon);
      this._updateMap(lat, lon, heading, cfg.color);
    }

    // HA Sections dashboard (2024.3+): controls how many columns the card spans.
    // Falls back to no constraint in Masonry view (width set by HA grid there).
    getGridOptions() {
      if (!this._config?.columns) return {};
      const cols = Math.min(12, Math.max(2, parseInt(this._config.columns, 10)));
      return { columns: cols, min_columns: 2 };
    }
  }

  customElements.define('stiga-robot-card', StigaRobotCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type:        'stiga-robot-card',
    name:        'Stiga Robot Mower Card',
    description: 'Live status, GPS map and controls for Stiga A-series robot mowers',
  });
})();
