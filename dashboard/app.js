/* ═══════════════════════════════════════════════════════════════
   Epstein Files Dashboard — Main Application Logic
   ═══════════════════════════════════════════════════════════════ */

// ── Global State ──────────────────────────────────────────────
const state = {
    persons: [],
    flights: [],
    documents: [],
    network: { nodes: [], links: [] },
    summary: {},
    charts: {},
    pagination: {
        persons: { page: 1, perPage: 25 },
        flights: { page: 1, perPage: 30 },
        documents: { page: 1, perPage: 25 },
    },
};

// ── Chart.js Global Config ────────────────────────────────────
Chart.defaults.color = '#8a8a9a';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.padding = 16;

const COLORS = {
    indigo: '#6366f1',
    purple: '#8b5cf6',
    pink: '#ec4899',
    rose: '#f43f5e',
    cyan: '#06b6d4',
    emerald: '#10b981',
    amber: '#f59e0b',
    orange: '#f97316',
    teal: '#14b8a6',
    sky: '#0ea5e9',
};

const COLOR_PALETTE = Object.values(COLORS);

function getColor(i) {
    return COLOR_PALETTE[i % COLOR_PALETTE.length];
}

function getColorAlpha(i, alpha = 0.15) {
    const c = getColor(i);
    return c + Math.round(alpha * 255).toString(16).padStart(2, '0');
}

// ── Data Loading ──────────────────────────────────────────────

async function loadData() {
    const files = [
        'persons_of_interest.json',
        'flight_logs.json',
        'documents.json',
        'network.json',
        'summary.json',
    ];

    const statusEl = document.getElementById('loading-status');

    for (let i = 0; i < files.length; i++) {
        statusEl.textContent = `Loading ${files[i]}...`;
        try {
            const resp = await fetch(`data/${files[i]}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            const key = files[i].replace('.json', '').replace('persons_of_interest', 'persons').replace('flight_logs', 'flights');
            state[key] = data;
        } catch (e) {
            console.warn(`Failed to load ${files[i]}:`, e.message);
        }
    }

    statusEl.textContent = 'Rendering dashboard...';
    await new Promise(r => setTimeout(r, 200));
}

// ── Initialization ────────────────────────────────────────────

async function init() {
    await loadData();

    // Show app
    const loadingEl = document.getElementById('loading-screen');
    const appEl = document.getElementById('app');
    loadingEl.classList.add('fade-out');
    appEl.classList.remove('hidden');
    setTimeout(() => loadingEl.remove(), 600);

    // Update header badge
    const totalRecords = (state.persons?.length || 0) + (state.flights?.length || 0) + (state.documents?.length || 0);
    document.getElementById('record-count').textContent = `${totalRecords.toLocaleString()} records loaded`;

    // Setup tabs
    setupTabs();

    // Render overview (default tab)
    renderOverview();

    // Setup modal
    setupModal();
}

// ── Tab Management ────────────────────────────────────────────

function setupTabs() {
    const btns = document.querySelectorAll('.tab-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.getElementById(`panel-${tab}`).classList.add('active');

            // Lazy render
            switch (tab) {
                case 'overview': renderOverview(); break;
                case 'persons': renderPersons(); break;
                case 'flights': renderFlights(); break;
                case 'documents': renderDocuments(); break;
                case 'network': renderNetwork(); break;
            }
        });
    });
}

// ── Utility ───────────────────────────────────────────────────

function destroyChart(key) {
    if (state.charts[key]) {
        state.charts[key].destroy();
        delete state.charts[key];
    }
}

function formatNum(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toLocaleString();
}

function truncate(s, len = 50) {
    if (!s) return '—';
    return s.length > len ? s.substring(0, len) + '…' : s;
}

function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

// ══════════════════════════════════════════════════════════════
//  OVERVIEW TAB
// ══════════════════════════════════════════════════════════════

function renderOverview() {
    const s = state.summary;

    // Metric cards
    document.getElementById('val-persons').textContent = formatNum(s.total_persons || state.persons?.length || 0);
    document.getElementById('val-flights').textContent = formatNum(s.total_flights || state.flights?.length || 0);
    document.getElementById('val-documents').textContent = formatNum(s.total_documents || state.documents?.length || 0);
    document.getElementById('val-blackbook').textContent = formatNum(s.persons_stats?.in_black_book || 0);
    document.getElementById('val-images').textContent = formatNum(s.total_images || 0);

    // Top Flights chart
    if (s.persons_stats?.top_by_flights) {
        const data = s.persons_stats.top_by_flights;
        destroyChart('topFlights');
        state.charts.topFlights = new Chart(document.getElementById('chart-top-flights'), {
            type: 'bar',
            data: {
                labels: data.map(d => d.name),
                datasets: [{
                    label: 'Flights',
                    data: data.map(d => d.flights),
                    backgroundColor: data.map((_, i) => getColorAlpha(i, 0.7)),
                    borderColor: data.map((_, i) => getColor(i)),
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.03)' } },
                    y: { grid: { display: false }, ticks: { font: { size: 11 } } },
                },
            },
        });
    }

    // Top Connections chart
    if (s.persons_stats?.top_by_connections) {
        const data = s.persons_stats.top_by_connections;
        destroyChart('topConnections');
        state.charts.topConnections = new Chart(document.getElementById('chart-top-connections'), {
            type: 'bar',
            data: {
                labels: data.map(d => d.name),
                datasets: [{
                    label: 'Connections',
                    data: data.map(d => d.connections),
                    backgroundColor: data.map((_, i) => getColorAlpha(i + 3, 0.7)),
                    borderColor: data.map((_, i) => getColor(i + 3)),
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.03)' } },
                    y: { grid: { display: false }, ticks: { font: { size: 11 } } },
                },
            },
        });
    }

    // Flights by Year
    if (s.flight_stats?.by_year) {
        const years = Object.keys(s.flight_stats.by_year).filter(y => y);
        const counts = years.map(y => s.flight_stats.by_year[y]);
        destroyChart('flightsYear');
        state.charts.flightsYear = new Chart(document.getElementById('chart-flights-year'), {
            type: 'line',
            data: {
                labels: years,
                datasets: [{
                    label: 'Flights',
                    data: counts,
                    borderColor: COLORS.cyan,
                    backgroundColor: COLORS.cyan + '20',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: COLORS.cyan,
                    pointRadius: 4,
                    pointHoverRadius: 7,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.03)' } },
                    y: { grid: { color: 'rgba(255,255,255,0.03)' }, beginAtZero: true },
                },
            },
        });
    }

    // Nationality Breakdown (doughnut)
    if (s.persons_stats?.nationalities) {
        const entries = Object.entries(s.persons_stats.nationalities).slice(0, 10);
        destroyChart('nationality');
        state.charts.nationality = new Chart(document.getElementById('chart-nationality'), {
            type: 'doughnut',
            data: {
                labels: entries.map(e => e[0]),
                datasets: [{
                    data: entries.map(e => e[1]),
                    backgroundColor: entries.map((_, i) => getColor(i)),
                    borderColor: '#111118',
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '55%',
                plugins: {
                    legend: { position: 'right', labels: { font: { size: 11 } } },
                },
            },
        });
    }

    // Top Routes
    if (s.flight_stats?.top_routes) {
        const routes = s.flight_stats.top_routes.slice(0, 15);
        destroyChart('topRoutes');
        state.charts.topRoutes = new Chart(document.getElementById('chart-top-routes'), {
            type: 'bar',
            data: {
                labels: routes.map(r => `${r.from} → ${r.to}`),
                datasets: [{
                    label: 'Flights',
                    data: routes.map(r => r.count),
                    backgroundColor: routes.map((_, i) => getColorAlpha(i, 0.65)),
                    borderColor: routes.map((_, i) => getColor(i)),
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { maxRotation: 45, font: { size: 10 } } },
                    y: { grid: { color: 'rgba(255,255,255,0.03)' }, beginAtZero: true },
                },
            },
        });
    }
}

// ══════════════════════════════════════════════════════════════
//  PERSONS TAB
// ══════════════════════════════════════════════════════════════

let personsInited = false;

function renderPersons() {
    if (!state.persons || !state.persons.length) return;

    if (!personsInited) {
        // Setup controls
        document.getElementById('persons-search').addEventListener('input', () => {
            state.pagination.persons.page = 1;
            renderPersonsTable();
        });
        document.getElementById('persons-sort').addEventListener('change', renderPersonsTable);
        document.getElementById('persons-filter').addEventListener('change', () => {
            state.pagination.persons.page = 1;
            renderPersonsTable();
        });
        personsInited = true;
    }

    renderPersonsCharts();
    renderPersonsTable();
}

function getFilteredPersons() {
    let data = [...state.persons];

    // Filter
    const filter = document.getElementById('persons-filter').value;
    if (filter === 'black_book') data = data.filter(p => p.in_black_book);
    if (filter === 'has_flights') data = data.filter(p => p.flights > 0);
    if (filter === 'has_images') data = data.filter(p => p.images && p.images.length > 0);

    // Search
    const query = document.getElementById('persons-search').value.toLowerCase().trim();
    if (query) {
        data = data.filter(p =>
            (p.name || '').toLowerCase().includes(query) ||
            (p.nationality || '').toLowerCase().includes(query) ||
            (p.category || '').toLowerCase().includes(query)
        );
    }

    // Sort
    const sort = document.getElementById('persons-sort').value;
    switch (sort) {
        case 'flights': data.sort((a, b) => b.flights - a.flights); break;
        case 'documents': data.sort((a, b) => b.documents - a.documents); break;
        case 'connections': data.sort((a, b) => b.connections - a.connections); break;
        case 'name': data.sort((a, b) => (a.name || '').localeCompare(b.name || '')); break;
    }

    return data;
}

function renderPersonsCharts() {
    // Top passengers by flights
    const topFlights = state.persons.filter(p => p.flights > 0).slice(0, 15);
    destroyChart('personsFlights');
    if (topFlights.length) {
        state.charts.personsFlights = new Chart(document.getElementById('chart-persons-flights'), {
            type: 'bar',
            data: {
                labels: topFlights.map(p => p.name),
                datasets: [{
                    label: 'Flights',
                    data: topFlights.map(p => p.flights),
                    backgroundColor: topFlights.map((_, i) => getColorAlpha(i, 0.7)),
                    borderColor: topFlights.map((_, i) => getColor(i)),
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.03)' } },
                    y: { grid: { display: false }, ticks: { font: { size: 11 } } },
                },
            },
        });
    }

    // Category distribution
    const categories = {};
    state.persons.forEach(p => {
        const cat = p.category || 'Unknown';
        categories[cat] = (categories[cat] || 0) + 1;
    });
    const catEntries = Object.entries(categories).sort((a, b) => b[1] - a[1]).slice(0, 10);

    destroyChart('personsCategory');
    if (catEntries.length) {
        state.charts.personsCategory = new Chart(document.getElementById('chart-persons-category'), {
            type: 'doughnut',
            data: {
                labels: catEntries.map(e => e[0]),
                datasets: [{
                    data: catEntries.map(e => e[1]),
                    backgroundColor: catEntries.map((_, i) => getColor(i)),
                    borderColor: '#111118',
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '50%',
                plugins: {
                    legend: { position: 'right', labels: { font: { size: 11 } } },
                },
            },
        });
    }
}

function renderPersonsTable() {
    const data = getFilteredPersons();
    const { page, perPage } = state.pagination.persons;
    const start = (page - 1) * perPage;
    const pageData = data.slice(start, start + perPage);

    document.getElementById('persons-count').textContent = `${data.length} results`;

    const tbody = document.getElementById('persons-tbody');
    tbody.innerHTML = pageData.map((p, i) => {
        const imgCell = (p.images && p.images.length > 0)
            ? `<img src="../${p.images[0].path}" class="img-thumb" onclick="openPersonModal(${start + i})" alt="${escapeHtml(p.name)}" onerror="this.outerHTML='<div class=no-img>👤</div>'">`
            : `<div class="no-img" onclick="openPersonModal(${start + i})" style="cursor:pointer">👤</div>`;

        return `<tr onclick="openPersonModal(${start + i})" style="cursor:pointer">
            <td>${start + i + 1}</td>
            <td><strong>${escapeHtml(p.name)}</strong></td>
            <td>${p.flights || 0}</td>
            <td>${p.documents || 0}</td>
            <td>${p.connections || 0}</td>
            <td>${p.in_black_book ? '<span class="tag-pill rose">Yes</span>' : '—'}</td>
            <td>${escapeHtml(p.nationality)}</td>
            <td>${imgCell}</td>
        </tr>`;
    }).join('');

    renderPagination('persons', data.length);
}

function renderPagination(section, total) {
    const { page, perPage } = state.pagination[section];
    const totalPages = Math.ceil(total / perPage);
    const container = document.getElementById(`${section}-pagination`);

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = `<button ${page <= 1 ? 'disabled' : ''} onclick="goPage('${section}', ${page - 1})">← Prev</button>`;

    const maxButtons = 7;
    let startP = Math.max(1, page - Math.floor(maxButtons / 2));
    let endP = Math.min(totalPages, startP + maxButtons - 1);
    if (endP - startP < maxButtons - 1) startP = Math.max(1, endP - maxButtons + 1);

    if (startP > 1) html += `<button onclick="goPage('${section}', 1)">1</button><button disabled>…</button>`;
    for (let p = startP; p <= endP; p++) {
        html += `<button class="${p === page ? 'active' : ''}" onclick="goPage('${section}', ${p})">${p}</button>`;
    }
    if (endP < totalPages) html += `<button disabled>…</button><button onclick="goPage('${section}', ${totalPages})">${totalPages}</button>`;

    html += `<button ${page >= totalPages ? 'disabled' : ''} onclick="goPage('${section}', ${page + 1})">Next →</button>`;
    container.innerHTML = html;
}

window.goPage = function (section, page) {
    state.pagination[section].page = page;
    switch (section) {
        case 'persons': renderPersonsTable(); break;
        case 'flights': renderFlightsTable(); break;
        case 'documents': renderDocsTable(); break;
    }
    // Scroll to table
    document.getElementById(`${section === 'documents' ? 'docs' : section}-table`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

// ══════════════════════════════════════════════════════════════
//  FLIGHTS TAB
// ══════════════════════════════════════════════════════════════

let flightsInited = false;

function renderFlights() {
    if (!state.flights || !state.flights.length) return;

    if (!flightsInited) {
        // Populate year selectors
        const years = [...new Set(state.flights.map(f => f.year).filter(Boolean))].sort();
        const startSel = document.getElementById('flights-year-start');
        const endSel = document.getElementById('flights-year-end');
        years.forEach(y => {
            startSel.innerHTML += `<option value="${y}">${y}</option>`;
            endSel.innerHTML += `<option value="${y}">${y}</option>`;
        });

        // Populate aircraft selector
        const aircraft = [...new Set(state.flights.map(f => f.aircraft).filter(Boolean))].sort();
        const aircraftSel = document.getElementById('flights-aircraft');
        aircraft.forEach(a => {
            aircraftSel.innerHTML += `<option value="${escapeHtml(a)}">${escapeHtml(a)}</option>`;
        });

        // Event listeners
        ['flights-year-start', 'flights-year-end', 'flights-aircraft'].forEach(id => {
            document.getElementById(id).addEventListener('change', () => {
                state.pagination.flights.page = 1;
                renderFlightsCharts();
                renderFlightsTable();
            });
        });
        document.getElementById('flights-search').addEventListener('input', () => {
            state.pagination.flights.page = 1;
            renderFlightsTable();
        });

        flightsInited = true;
    }

    renderFlightsCharts();
    renderFlightsTable();
}

function getFilteredFlights() {
    let data = [...state.flights];

    const yearStart = document.getElementById('flights-year-start').value;
    const yearEnd = document.getElementById('flights-year-end').value;
    const aircraft = document.getElementById('flights-aircraft').value;
    const query = document.getElementById('flights-search').value.toLowerCase().trim();

    if (yearStart) data = data.filter(f => f.year >= yearStart);
    if (yearEnd) data = data.filter(f => f.year <= yearEnd);
    if (aircraft && aircraft !== 'all') data = data.filter(f => f.aircraft === aircraft);
    if (query) {
        data = data.filter(f =>
            (f.departure || '').toLowerCase().includes(query) ||
            (f.arrival || '').toLowerCase().includes(query) ||
            (f.passengers || '').toLowerCase().includes(query) ||
            (f.date || '').toLowerCase().includes(query)
        );
    }

    return data;
}

function renderFlightsCharts() {
    const data = getFilteredFlights();

    // Flights per year
    const yearCounts = {};
    data.forEach(f => { if (f.year) yearCounts[f.year] = (yearCounts[f.year] || 0) + 1; });
    const years = Object.keys(yearCounts).sort();

    destroyChart('flightsTimeline');
    state.charts.flightsTimeline = new Chart(document.getElementById('chart-flights-timeline'), {
        type: 'bar',
        data: {
            labels: years,
            datasets: [{
                label: 'Flights',
                data: years.map(y => yearCounts[y]),
                backgroundColor: COLORS.indigo + 'aa',
                borderColor: COLORS.indigo,
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: 'rgba(255,255,255,0.03)' }, beginAtZero: true },
            },
        },
    });

    // Aircraft usage
    const aircraftCounts = {};
    data.forEach(f => { if (f.aircraft) aircraftCounts[f.aircraft] = (aircraftCounts[f.aircraft] || 0) + 1; });
    const acEntries = Object.entries(aircraftCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);

    destroyChart('flightsAircraft');
    state.charts.flightsAircraft = new Chart(document.getElementById('chart-flights-aircraft'), {
        type: 'doughnut',
        data: {
            labels: acEntries.map(e => e[0]),
            datasets: [{
                data: acEntries.map(e => e[1]),
                backgroundColor: acEntries.map((_, i) => getColor(i + 2)),
                borderColor: '#111118',
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '50%',
            plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } },
        },
    });

    // Top departures
    const depCounts = {};
    data.forEach(f => { if (f.departure) depCounts[f.departure] = (depCounts[f.departure] || 0) + 1; });
    const depEntries = Object.entries(depCounts).sort((a, b) => b[1] - a[1]).slice(0, 12);

    destroyChart('flightsDepartures');
    state.charts.flightsDepartures = new Chart(document.getElementById('chart-flights-departures'), {
        type: 'bar',
        data: {
            labels: depEntries.map(e => e[0]),
            datasets: [{
                label: 'Departures',
                data: depEntries.map(e => e[1]),
                backgroundColor: COLORS.emerald + 'aa',
                borderColor: COLORS.emerald,
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { maxRotation: 45, font: { size: 10 } } },
                y: { grid: { color: 'rgba(255,255,255,0.03)' }, beginAtZero: true },
            },
        },
    });

    // Top arrivals
    const arrCounts = {};
    data.forEach(f => { if (f.arrival) arrCounts[f.arrival] = (arrCounts[f.arrival] || 0) + 1; });
    const arrEntries = Object.entries(arrCounts).sort((a, b) => b[1] - a[1]).slice(0, 12);

    destroyChart('flightsArrivals');
    state.charts.flightsArrivals = new Chart(document.getElementById('chart-flights-arrivals'), {
        type: 'bar',
        data: {
            labels: arrEntries.map(e => e[0]),
            datasets: [{
                label: 'Arrivals',
                data: arrEntries.map(e => e[1]),
                backgroundColor: COLORS.pink + 'aa',
                borderColor: COLORS.pink,
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { maxRotation: 45, font: { size: 10 } } },
                y: { grid: { color: 'rgba(255,255,255,0.03)' }, beginAtZero: true },
            },
        },
    });
}

function renderFlightsTable() {
    const data = getFilteredFlights();
    const { page, perPage } = state.pagination.flights;
    const start = (page - 1) * perPage;
    const pageData = data.slice(start, start + perPage);

    document.getElementById('flights-count').textContent = `${data.length} records`;

    const tbody = document.getElementById('flights-tbody');
    tbody.innerHTML = pageData.map((f, i) => `
        <tr>
            <td>${start + i + 1}</td>
            <td>${escapeHtml(f.date) || '—'}</td>
            <td>${escapeHtml(f.departure) || '—'}</td>
            <td>${escapeHtml(f.arrival) || '—'}</td>
            <td><span class="tag-pill">${escapeHtml(f.aircraft) || 'N/A'}</span></td>
            <td>${escapeHtml(truncate(f.passengers, 80))}</td>
        </tr>
    `).join('');

    renderPagination('flights', data.length);
}

// ══════════════════════════════════════════════════════════════
//  DOCUMENTS TAB
// ══════════════════════════════════════════════════════════════

let docsInited = false;

function renderDocuments() {
    if (!state.documents || !state.documents.length) return;

    if (!docsInited) {
        // Populate tag filter
        const allTags = {};
        state.documents.forEach(d => (d.tags || []).forEach(t => { if (t) allTags[t] = (allTags[t] || 0) + 1; }));
        const tagSel = document.getElementById('docs-tag-filter');
        Object.entries(allTags).sort((a, b) => b[1] - a[1]).slice(0, 50).forEach(([tag]) => {
            tagSel.innerHTML += `<option value="${escapeHtml(tag)}">${escapeHtml(tag)}</option>`;
        });

        // Importance slider
        const slider = document.getElementById('docs-importance-slider');
        const valEl = document.getElementById('docs-importance-value');
        slider.addEventListener('input', () => {
            valEl.textContent = slider.value;
            state.pagination.documents.page = 1;
            renderDocsTable();
        });

        document.getElementById('docs-search').addEventListener('input', () => {
            state.pagination.documents.page = 1;
            renderDocsTable();
        });

        document.getElementById('docs-tag-filter').addEventListener('change', () => {
            state.pagination.documents.page = 1;
            renderDocsTable();
        });

        docsInited = true;
    }

    renderDocsCharts();
    renderDocsTable();
}

function getFilteredDocs() {
    let data = [...state.documents];

    const minScore = parseInt(document.getElementById('docs-importance-slider').value) || 0;
    const tagFilter = document.getElementById('docs-tag-filter').value;
    const query = document.getElementById('docs-search').value.toLowerCase().trim();

    if (minScore > 0) data = data.filter(d => d.importance_score >= minScore);
    if (tagFilter !== 'all') data = data.filter(d => (d.tags || []).includes(tagFilter));
    if (query) {
        data = data.filter(d =>
            (d.headline || '').toLowerCase().includes(query) ||
            (d.tags || []).some(t => t.toLowerCase().includes(query)) ||
            (d.power_mentions || []).some(p => p.toLowerCase().includes(query))
        );
    }

    return data;
}

function renderDocsCharts() {
    const s = state.summary;

    // Importance distribution
    if (s.document_stats?.importance_distribution) {
        const dist = s.document_stats.importance_distribution;
        const labels = Object.keys(dist).sort();
        destroyChart('docsImportance');
        state.charts.docsImportance = new Chart(document.getElementById('chart-docs-importance'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Documents',
                    data: labels.map(l => dist[l]),
                    backgroundColor: labels.map((_, i) => getColorAlpha(i, 0.65)),
                    borderColor: labels.map((_, i) => getColor(i)),
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, title: { display: true, text: 'Importance Score Range', color: '#55556a' } },
                    y: { grid: { color: 'rgba(255,255,255,0.03)' }, beginAtZero: true },
                },
            },
        });
    }

    // Top Tags
    if (s.document_stats?.top_tags) {
        const entries = Object.entries(s.document_stats.top_tags).slice(0, 15);
        destroyChart('docsTags');
        state.charts.docsTags = new Chart(document.getElementById('chart-docs-tags'), {
            type: 'bar',
            data: {
                labels: entries.map(e => e[0]),
                datasets: [{
                    label: 'Count',
                    data: entries.map(e => e[1]),
                    backgroundColor: COLORS.amber + 'aa',
                    borderColor: COLORS.amber,
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.03)' } },
                    y: { grid: { display: false }, ticks: { font: { size: 10 } } },
                },
            },
        });
    }

    // Power mentions
    if (s.document_stats?.top_power_mentions) {
        const entries = Object.entries(s.document_stats.top_power_mentions).slice(0, 12);
        destroyChart('docsPower');
        state.charts.docsPower = new Chart(document.getElementById('chart-docs-power'), {
            type: 'bar',
            data: {
                labels: entries.map(e => e[0]),
                datasets: [{
                    label: 'Mentions',
                    data: entries.map(e => e[1]),
                    backgroundColor: entries.map((_, i) => getColorAlpha(i + 5, 0.65)),
                    borderColor: entries.map((_, i) => getColor(i + 5)),
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.03)' } },
                    y: { grid: { display: false }, ticks: { font: { size: 10 } } },
                },
            },
        });
    }

    // Agency involvement
    if (s.document_stats?.top_agencies) {
        const entries = Object.entries(s.document_stats.top_agencies).slice(0, 10);
        destroyChart('docsAgencies');
        state.charts.docsAgencies = new Chart(document.getElementById('chart-docs-agencies'), {
            type: 'doughnut',
            data: {
                labels: entries.map(e => e[0]),
                datasets: [{
                    data: entries.map(e => e[1]),
                    backgroundColor: entries.map((_, i) => getColor(i + 4)),
                    borderColor: '#111118',
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '50%',
                plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } },
            },
        });
    }
}

function renderDocsTable() {
    const data = getFilteredDocs();
    const { page, perPage } = state.pagination.documents;
    const start = (page - 1) * perPage;
    const pageData = data.slice(start, start + perPage);

    document.getElementById('docs-count').textContent = `${data.length} documents`;

    const tbody = document.getElementById('docs-tbody');
    tbody.innerHTML = pageData.map((d, i) => {
        const tagsHtml = (d.tags || []).slice(0, 3).map(t => `<span class="tag-pill">${escapeHtml(t)}</span>`).join('');
        const powerHtml = (d.power_mentions || []).slice(0, 3).map(p => `<span class="tag-pill pink">${escapeHtml(p)}</span>`).join('');
        const leadHtml = (d.lead_types || []).slice(0, 2).map(l => `<span class="tag-pill green">${escapeHtml(l)}</span>`).join('');
        const scoreWidth = Math.min(d.importance_score, 100);

        return `<tr>
            <td>${start + i + 1}</td>
            <td title="${escapeHtml(d.headline)}">${escapeHtml(truncate(d.headline, 60))}</td>
            <td>
                <div class="score-bar">
                    <div class="score-fill" style="width:${scoreWidth}px"></div>
                    <span>${d.importance_score}</span>
                </div>
            </td>
            <td>${tagsHtml || '—'}</td>
            <td>${powerHtml || '—'}</td>
            <td>${leadHtml || '—'}</td>
        </tr>`;
    }).join('');

    renderPagination('documents', data.length);
}

// ══════════════════════════════════════════════════════════════
//  NETWORK TAB
// ══════════════════════════════════════════════════════════════

let networkInited = false;
let simulation = null;

function renderNetwork() {
    if (!state.network || (!state.network.nodes.length && !state.network.links.length)) {
        document.getElementById('network-stats').textContent = 'No network data available';
        return;
    }

    if (!networkInited) {
        document.getElementById('network-min-conn').addEventListener('input', function () {
            document.getElementById('network-conn-value').textContent = this.value;
            renderNetworkGraph();
        });
        document.getElementById('network-search').addEventListener('input', highlightNetworkNode);
        document.getElementById('network-reset').addEventListener('click', renderNetworkGraph);
        networkInited = true;
    }

    renderNetworkGraph();
}

function renderNetworkGraph() {
    const svg = d3.select('#network-svg');
    svg.selectAll('*').remove();

    const container = document.querySelector('.network-container');
    const width = container.clientWidth;
    const height = container.clientHeight;

    const minConn = parseInt(document.getElementById('network-min-conn').value) || 1;

    // Filter links by weight
    const links = state.network.links.filter(l => l.weight >= minConn).map(l => ({ ...l }));
    const nodeIds = new Set();
    links.forEach(l => { nodeIds.add(l.source); nodeIds.add(l.target); });
    const nodes = state.network.nodes.filter(n => nodeIds.has(n.id)).map(n => ({ ...n }));

    document.getElementById('network-stats').textContent = `${nodes.length} nodes, ${links.length} links`;

    if (!nodes.length) return;

    // Color scale
    const maxConn = Math.max(...nodes.map(n => n.connections || 0), 1);
    function nodeColor(d) {
        const conn = d.connections || 0;
        if (conn > maxConn * 0.6) return '#ff6b6b';
        if (conn > maxConn * 0.3) return '#ffd93d';
        if (conn > 0) return '#6bcb77';
        return '#4d96ff';
    }

    function nodeRadius(d) {
        return Math.max(4, Math.min(16, 4 + (d.connections || d.flights || 0) / 3));
    }

    const g = svg.append('g');

    // Zoom
    const zoom = d3.zoom()
        .scaleExtent([0.3, 5])
        .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    // Simulation
    simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-120))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 4));

    // Links
    const link = g.append('g')
        .selectAll('line')
        .data(links)
        .join('line')
        .attr('stroke', 'rgba(255,255,255,0.08)')
        .attr('stroke-width', d => Math.max(1, Math.min(4, d.weight / 2)));

    // Nodes
    const node = g.append('g')
        .selectAll('circle')
        .data(nodes)
        .join('circle')
        .attr('r', d => nodeRadius(d))
        .attr('fill', d => nodeColor(d))
        .attr('stroke', 'rgba(255,255,255,0.15)')
        .attr('stroke-width', 1)
        .style('cursor', 'pointer')
        .call(d3.drag()
            .on('start', (event, d) => {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x; d.fy = d.y;
            })
            .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
            .on('end', (event, d) => {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null; d.fy = null;
            })
        );

    // Labels (for larger nodes)
    const labels = g.append('g')
        .selectAll('text')
        .data(nodes.filter(n => nodeRadius(n) > 7))
        .join('text')
        .text(d => d.id)
        .attr('font-size', '9px')
        .attr('fill', 'rgba(255,255,255,0.6)')
        .attr('dx', d => nodeRadius(d) + 4)
        .attr('dy', 3)
        .style('pointer-events', 'none');

    // Tooltip
    const tooltip = document.getElementById('network-tooltip');

    node.on('mouseover', (event, d) => {
        tooltip.innerHTML = `
            <h4>${escapeHtml(d.id)}</h4>
            <p>Group: ${escapeHtml(d.group || 'Unknown')}</p>
            <p>Flights: ${d.flights || 0}</p>
            <p>Connections: ${d.connections || 0}</p>
            ${d.nationality ? `<p>Nationality: ${escapeHtml(d.nationality)}</p>` : ''}
            ${d.in_black_book ? '<p style="color:#f43f5e">⚠ In Black Book</p>' : ''}
        `;
        tooltip.classList.add('visible');
        tooltip.style.left = (event.offsetX + 15) + 'px';
        tooltip.style.top = (event.offsetY - 10) + 'px';

        // Highlight connected
        const connectedIds = new Set();
        links.forEach(l => {
            const sid = typeof l.source === 'object' ? l.source.id : l.source;
            const tid = typeof l.target === 'object' ? l.target.id : l.target;
            if (sid === d.id) connectedIds.add(tid);
            if (tid === d.id) connectedIds.add(sid);
        });
        connectedIds.add(d.id);

        node.attr('opacity', n => connectedIds.has(n.id) ? 1 : 0.15);
        link.attr('opacity', l => {
            const sid = typeof l.source === 'object' ? l.source.id : l.source;
            const tid = typeof l.target === 'object' ? l.target.id : l.target;
            return (sid === d.id || tid === d.id) ? 0.7 : 0.03;
        });
        labels.attr('opacity', n => connectedIds.has(n.id) ? 1 : 0.1);
    })
    .on('mousemove', (event) => {
        tooltip.style.left = (event.offsetX + 15) + 'px';
        tooltip.style.top = (event.offsetY - 10) + 'px';
    })
    .on('mouseout', () => {
        tooltip.classList.remove('visible');
        node.attr('opacity', 1);
        link.attr('opacity', 1);
        labels.attr('opacity', 1);
    })
    .on('click', (event, d) => {
        // Open modal if it's a person
        if (d.images && d.images.length > 0) {
            openModalForNode(d);
        }
    });

    // Tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        node
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);
        labels
            .attr('x', d => d.x)
            .attr('y', d => d.y);
    });
}

function highlightNetworkNode() {
    const query = document.getElementById('network-search').value.toLowerCase().trim();
    if (!query) {
        d3.select('#network-svg').selectAll('circle').attr('opacity', 1);
        d3.select('#network-svg').selectAll('text').attr('opacity', 1);
        return;
    }

    d3.select('#network-svg').selectAll('circle')
        .attr('opacity', d => d.id.toLowerCase().includes(query) ? 1 : 0.1)
        .attr('stroke-width', d => d.id.toLowerCase().includes(query) ? 3 : 1)
        .attr('stroke', d => d.id.toLowerCase().includes(query) ? '#ffd93d' : 'rgba(255,255,255,0.15)');

    d3.select('#network-svg').selectAll('text')
        .attr('opacity', d => d.id.toLowerCase().includes(query) ? 1 : 0.05);
}

// ══════════════════════════════════════════════════════════════
//  IMAGE MODAL
// ══════════════════════════════════════════════════════════════

function setupModal() {
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('image-modal').addEventListener('click', (e) => {
        if (e.target.id === 'image-modal') closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
}

function closeModal() {
    document.getElementById('image-modal').classList.remove('visible');
}

window.openPersonModal = function (filteredIndex) {
    const data = getFilteredPersons();
    const person = data[filteredIndex];
    if (!person) return;

    const modal = document.getElementById('image-modal');
    document.getElementById('modal-name').textContent = person.name;

    // Meta badges
    document.getElementById('modal-meta').innerHTML = `
        ${person.nationality ? `<span class="tag-pill">${escapeHtml(person.nationality)}</span>` : ''}
        ${person.category ? `<span class="tag-pill green">${escapeHtml(person.category)}</span>` : ''}
        ${person.in_black_book ? '<span class="tag-pill rose">In Black Book</span>' : ''}
    `;

    // Images
    const imgContainer = document.getElementById('modal-images');
    if (person.images && person.images.length > 0) {
        imgContainer.innerHTML = person.images.map(img =>
            `<img src="../${img.path}" alt="${escapeHtml(person.name)}" onerror="this.style.display='none'">`
        ).join('');
    } else {
        imgContainer.innerHTML = '<p style="color: var(--text-muted); font-style: italic; padding: 20px;">No images available. Place images in data/images/victims/ and re-run process_data.py</p>';
    }

    // Details
    document.getElementById('modal-details').innerHTML = `
        <div class="detail-item">
            <div class="detail-label">Flights</div>
            <div class="detail-value">${person.flights || 0}</div>
        </div>
        <div class="detail-item">
            <div class="detail-label">Documents</div>
            <div class="detail-value">${person.documents || 0}</div>
        </div>
        <div class="detail-item">
            <div class="detail-label">Connections</div>
            <div class="detail-value">${person.connections || 0}</div>
        </div>
        <div class="detail-item">
            <div class="detail-label">In Black Book</div>
            <div class="detail-value">${person.in_black_book ? '✅ Yes' : '❌ No'}</div>
        </div>
    `;

    modal.classList.add('visible');
};

function openModalForNode(d) {
    const modal = document.getElementById('image-modal');
    document.getElementById('modal-name').textContent = d.id;

    document.getElementById('modal-meta').innerHTML = `
        ${d.group ? `<span class="tag-pill">${escapeHtml(d.group)}</span>` : ''}
        ${d.nationality ? `<span class="tag-pill green">${escapeHtml(d.nationality)}</span>` : ''}
        ${d.in_black_book ? '<span class="tag-pill rose">In Black Book</span>' : ''}
    `;

    const imgContainer = document.getElementById('modal-images');
    if (d.images && d.images.length > 0) {
        imgContainer.innerHTML = d.images.map(img =>
            `<img src="../${img.path}" alt="${escapeHtml(d.id)}" onerror="this.style.display='none'">`
        ).join('');
    } else {
        imgContainer.innerHTML = '<p style="color: var(--text-muted); font-style: italic;">No images available</p>';
    }

    document.getElementById('modal-details').innerHTML = `
        <div class="detail-item">
            <div class="detail-label">Flights</div>
            <div class="detail-value">${d.flights || 0}</div>
        </div>
        <div class="detail-item">
            <div class="detail-label">Connections</div>
            <div class="detail-value">${d.connections || 0}</div>
        </div>
    `;

    modal.classList.add('visible');
}

// ── Boot ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
