/**
 * MSFS A320 Checklist Companion - Frontend
 */

class ChecklistApp {
    constructor() {
        this.ws = null;
        this._reconnectDelay = 2000;
        this._maxReconnectDelay = 30000;
        this._justReconnected = false;
        this._lastStateVersion = -1;
        this._renderedPhase = null;
        this.state = {
            connected: false,
            phase: 'cockpit_preparation',
            phase_display: 'COCKPIT PREP',
            phase_mode: 'manual',
            checklist: null,
            flight_state: null,
            flight_plan: null,
            state_version: 0,
        };

        this.elements = {
            connectionStatus: document.getElementById('connection-status'),
            statusText: document.querySelector('.status-text'),
            phaseTitle: document.getElementById('phase-title'),
            phaseTrigger: document.getElementById('phase-trigger'),
            checklistItems: document.getElementById('checklist-items'),
            altitude: document.getElementById('altitude'),
            groundSpeed: document.getElementById('ground-speed'),
            phaseDisplay: document.getElementById('phase-display'),
            phaseMode: document.getElementById('phase-mode'),
            btnPrev: document.getElementById('btn-prev'),
            btnNext: document.getElementById('btn-next'),
            btnReset: document.getElementById('btn-reset'),
            flightplanBanner: document.getElementById('flightplan-banner'),
            bannerRoute: document.getElementById('banner-route'),
            bannerFuel: document.getElementById('banner-fuel'),
        };

        this.init();
    }

    init() {
        this.loadSettings();
        this.connectWebSocket();
        this.setupEventListeners();
        this.setupChecklistClickHandler();
        this.requestWakeLock();
    }

    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const settings = await response.json();
            if (settings.dark_mode) {
                document.body.classList.add('dark-mode');
            }
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log('Connecting to WebSocket:', wsUrl);

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this._reconnectDelay = 2000;
            this._justReconnected = true;
        };

        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        this.ws.onclose = () => {
            console.log(`WebSocket disconnected, reconnecting in ${this._reconnectDelay / 1000}s...`);
            const delay = this._reconnectDelay;
            this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxReconnectDelay);
            setTimeout(() => this.connectWebSocket(), delay);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleMessage(message) {
        if (message.type === 'state_update') {
            this.updateState(message.data);
        }
    }

    updateState(data) {
        const prevPhase = this.state.phase;
        const prevVersion = this._lastStateVersion;

        this.state = { ...this.state, ...data };

        // Use state_version counter to detect checklist changes (avoids JSON.stringify)
        const newVersion = this.state.state_version ?? 0;
        const checklistChanged = newVersion !== prevVersion || prevPhase !== this.state.phase;
        this._lastStateVersion = newVersion;

        // After reconnect, force a full re-render to reconcile any optimistic UI divergence
        const forceFullRender = this._justReconnected;
        this._justReconnected = false;

        this.renderConnectionStatus();
        this.renderPhaseHeader();
        this.renderFlightPlanBanner();
        if (forceFullRender || checklistChanged) {
            this.renderChecklist(forceFullRender || prevPhase !== this.state.phase);
        }
        this.renderFlightData();
    }

    render() {
        this.renderConnectionStatus();
        this.renderPhaseHeader();
        this.renderFlightPlanBanner();
        this.renderChecklist();
        this.renderFlightData();
    }

    // Debounce helper to prevent rapid re-renders
    _lastClickTime = 0;

    renderConnectionStatus() {
        const { connected } = this.state;
        const statusEl = this.elements.connectionStatus;
        const textEl = this.elements.statusText;

        if (connected) {
            statusEl.classList.remove('disconnected');
            statusEl.classList.add('connected');
            textEl.textContent = 'LIVE';
        } else {
            statusEl.classList.remove('connected');
            statusEl.classList.add('disconnected');
            textEl.textContent = 'MANUAL';
        }
    }

    renderPhaseHeader() {
        const { phase_display, checklist } = this.state;

        this.elements.phaseTitle.textContent = phase_display || 'CHECKLIST';
        this.elements.phaseTrigger.textContent = checklist?.trigger || '';
    }

    renderFlightPlanBanner() {
        const { flight_plan } = this.state;
        const banner = this.elements.flightplanBanner;

        if (!banner) return;

        if (flight_plan && flight_plan.origin) {
            banner.classList.remove('hidden');
            // Use textContent for user-provided values to prevent XSS
            const routeEl = this.elements.bannerRoute;
            routeEl.textContent = '';
            routeEl.appendChild(document.createTextNode(flight_plan.origin));
            routeEl.appendChild(document.createTextNode(' \u2192 '));
            routeEl.appendChild(document.createTextNode(flight_plan.destination));
            this.elements.bannerFuel.textContent =
                `FUEL: ${flight_plan.fuel_block.toLocaleString()} ${flight_plan.fuel_units}`;
        } else {
            banner.classList.add('hidden');
        }
    }

    renderChecklist(fullRender = false) {
        const { checklist, phase } = this.state;
        const container = this.elements.checklistItems;

        if (!checklist || !checklist.items) {
            container.innerHTML = '<li class="checklist-empty">No checklist loaded</li>';
            this._renderedPhase = null;
            return;
        }

        // Full render on phase change, first render, or forced reconciliation
        if (fullRender || this._renderedPhase !== phase) {
            container.innerHTML = checklist.items.map(item => this.renderChecklistItem(item, phase)).join('');
            this._renderedPhase = phase;
            return;
        }

        // Smart DOM patch: update only changed items in-place
        for (const item of checklist.items) {
            const el = container.querySelector(`[data-item-id="${item.id}"]`);
            if (!el) {
                // Item not found - fall back to full render
                container.innerHTML = checklist.items.map(i => this.renderChecklistItem(i, phase)).join('');
                return;
            }

            // Update checked state
            el.classList.toggle('checked', item.checked);
            el.classList.toggle('verified', item.verified === true);
            el.classList.toggle('not-verified', item.verified === false);

            const checkbox = el.querySelector('.item-checkbox');
            if (checkbox) {
                checkbox.innerHTML = item.checked ? '&#10003;' : '';
            }
        }
    }

    setupChecklistClickHandler() {
        // Use event delegation - attach once to container, not to each item
        const container = this.elements.checklistItems;
        container.addEventListener('click', (e) => {
            const item = e.target.closest('.checklist-item');
            if (item) {
                const itemId = item.dataset.itemId;
                const phase = this.state.phase;

                // Optimistic UI update - toggle immediately without waiting for server
                item.classList.toggle('checked');
                const checkbox = item.querySelector('.item-checkbox');
                if (checkbox) {
                    checkbox.innerHTML = item.classList.contains('checked') ? '&#10003;' : '';
                }

                this.toggleItem(phase, itemId);
            }
        });
    }

    renderChecklistItem(item, phase) {
        const classes = ['checklist-item'];
        if (item.checked) classes.push('checked');
        if (item.verified === true) classes.push('verified');
        if (item.verified === false) classes.push('not-verified');

        const checkmark = item.checked ? '&#10003;' : '';

        // Build response with MSFS actual + SimBrief expected if available
        let response = item.response;

        if (item.simbrief_type && item.simbrief_value && this.state.connected && this.state.flight_state) {
            const msfsValue = this.getMsfsValue(item.simbrief_type);
            if (msfsValue !== null) {
                response = this.buildCombinedResponse(item, msfsValue);
            }
        }

        return `
            <li class="${classes.join(' ')}" data-item-id="${item.id}">
                <div class="item-checkbox">${checkmark}</div>
                <div class="item-content">
                    <span class="item-challenge">${item.challenge}</span>
                    <span class="item-dots"></span>
                    <span class="item-response">${response}</span>
                </div>
            </li>
        `;
    }

    getMsfsValue(type) {
        const fs = this.state.flight_state;
        if (!fs) return null;

        switch (type) {
            case 'fuel':
                return fs.fuel_total_kg ? Math.round(fs.fuel_total_kg) : null;
            case 'baro':
                return fs.altimeter_hpa || null;
            default:
                return null;
        }
    }

    buildCombinedResponse(item, msfsValue) {
        // Format: "ACTUAL / EXPECTED REST_OF_TEMPLATE"
        const template = item.response;
        const simbriefValue = item.simbrief_value;

        // Format values based on type
        let msfsFormatted, simbriefFormatted, units;

        if (item.simbrief_type === 'fuel') {
            msfsFormatted = msfsValue.toLocaleString();
            simbriefFormatted = parseInt(simbriefValue).toLocaleString();
            units = 'KG';
        } else if (item.simbrief_type === 'baro') {
            msfsFormatted = msfsValue;
            simbriefFormatted = simbriefValue;
            units = '';
        } else {
            return template;
        }

        // Extract the part after the placeholder from template
        // Template is like "___KG CHECKED" or "___SET (BOTH)"
        const placeholderMatch = item.response.match(/<span class="simbrief-value">.*?<\/span>(.*)$/);
        const suffix = placeholderMatch ? placeholderMatch[1] : '';

        // Build combined response: ACTUAL / EXPECTED + suffix
        return `<span class="msfs-value">${msfsFormatted}</span> / <span class="simbrief-value">${simbriefFormatted} </span>${suffix}`;
    }

    renderFlightData() {
        const { flight_state, phase_display, phase_mode, connected } = this.state;

        if (connected && flight_state) {
            const alt = Math.round(flight_state.altitude_msl);
            const gs = Math.round(flight_state.ground_velocity);
            this.elements.altitude.textContent = `${alt.toLocaleString()} ft`;
            this.elements.groundSpeed.textContent = `${gs} kts`;
        } else {
            this.elements.altitude.textContent = '-- --';
            this.elements.groundSpeed.textContent = '-- --';
        }

        this.elements.phaseDisplay.textContent = phase_display || 'UNKNOWN';

        const modeEl = this.elements.phaseMode;
        modeEl.textContent = `(${phase_mode})`;
        modeEl.classList.toggle('auto', phase_mode === 'auto');
    }

    toggleItem(phase, itemId) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        this.ws.send(JSON.stringify({
            type: 'check_item',
            data: { phase, item_id: itemId }
        }));
    }

    nextPhase() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        this.ws.send(JSON.stringify({ type: 'next_phase', data: {} }));
    }

    prevPhase() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        this.ws.send(JSON.stringify({ type: 'prev_phase', data: {} }));
    }

    resetChecklists() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        if (confirm('Reset all checklists?')) {
            this.ws.send(JSON.stringify({ type: 'reset', data: {} }));
        }
    }

    setupEventListeners() {
        this.elements.btnPrev.addEventListener('click', () => this.prevPhase());
        this.elements.btnNext.addEventListener('click', () => this.nextPhase());
        this.elements.btnReset.addEventListener('click', () => this.resetChecklists());
        this.elements.phaseMode.addEventListener('click', () => this.toggleMode());
    }

    toggleMode() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        const newMode = this.state.phase_mode === 'auto' ? 'manual' : 'auto';
        this.ws.send(JSON.stringify({ type: 'set_mode', data: { mode: newMode } }));
    }

    async requestWakeLock() {
        if ('wakeLock' in navigator) {
            try {
                await navigator.wakeLock.request('screen');
                console.log('Wake lock acquired');
            } catch (e) {
                console.log('Wake lock request failed:', e);
            }
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ChecklistApp();
});
