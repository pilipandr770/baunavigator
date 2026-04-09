/* BauNavigator — main.js */

// ─── AI Chat ──────────────────────────────────────────────────────────────────

const AiChat = {
  projectId: null,
  stageKey: null,

  init(projectId, stageKey) {
    this.projectId = projectId;
    this.stageKey = stageKey;
    const form = document.getElementById('ai-chat-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.send();
      });
    }
  },

  async send() {
    const input = document.getElementById('ai-input');
    const message = (input?.value || '').trim();
    if (!message) return;

    this.addMessage(message, 'user');
    input.value = '';
    this.addMessage('...', 'bot', 'loading');

    try {
      const resp = await fetch('/ai/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          message,
          project_id: this.projectId,
          stage_key: this.stageKey,
        }),
      });
      const data = await resp.json();
      this.removeLoading();

      if (data.success) {
        const modeClass = data.mode === 'confirmation_required' ? 'mode-confirm'
          : data.mode === 'human_required' ? 'mode-human' : '';
        this.addMessage(data.response, 'bot', modeClass);
      } else {
        this.addMessage('Fehler: ' + data.response, 'bot', 'error');
      }
    } catch (err) {
      this.removeLoading();
      this.addMessage('Verbindungsfehler. Bitte versuche es erneut.', 'bot', 'error');
    }
  },

  addMessage(text, type, extra) {
    const body = document.getElementById('ai-chat-body');
    if (!body) return;

    const div = document.createElement('div');
    div.className = `ai-msg ai-msg-${type} ${extra || ''}`;

    // Парсим markdown-подобный текст
    div.innerHTML = text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>')
      .replace(/^- (.+)$/gm, '• $1');

    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
  },

  removeLoading() {
    const loading = document.querySelector('.loading');
    if (loading) loading.remove();
  },
};


// ─── Stage quick actions ───────────────────────────────────────────────────────

async function requestAiAction(action, projectId, stageKey) {
  const endpoints = {
    zone:      `/ai/zone-analysis/${projectId}`,
    kfw:       `/ai/kfw-calc/${projectId}`,
    checklist: `/ai/checklist/${projectId}/${stageKey}`,
    providers: `/ai/providers/${projectId}/${stageKey}`,
    letter:    `/ai/draft-letter/${projectId}/${stageKey}`,
  };

  const url = endpoints[action];
  if (!url) return;

  const btn = event.currentTarget;
  btn.disabled = true;
  btn.textContent = '...';

  try {
    const body = action === 'letter'
      ? JSON.stringify({ subject: `Anfrage — ${stageKey}` })
      : '{}';

    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body,
    });
    const data = await resp.json();

    if (data.success) {
      showResult(data.response, data.mode);
      if (data.outbox_id) {
        showToast('Entwurf in Postausgang gespeichert', 'success');
      }
      if (data.reload) {
        showToast(`Checkliste gespeichert (${data.checklist_count} Aufgaben)`, 'success');
        setTimeout(() => location.reload(), 1500);
      }
    } else {
      showToast('Fehler: ' + data.response, 'danger');
    }
  } catch {
    showToast('Verbindungsfehler', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = btn.dataset.label || 'KI anfragen';
  }
}

function showResult(text, mode) {
  let panel = document.getElementById('ai-result-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'ai-result-panel';
    panel.className = 'card mt-16';
    const container = document.querySelector('.ai-result-container');
    if (container) container.appendChild(panel);
  }

  const modeLabel = mode === 'autonomous' ? '✓ Automatisch erledigt'
    : mode === 'confirmation_required' ? '⟳ Entwurf — bitte prüfen und bestätigen'
    : '! Fachmann erforderlich';

  panel.innerHTML = `
    <div class="card-header">
      <div class="badge ${mode === 'autonomous' ? 'badge-done' : mode === 'human_required' ? 'badge-draft' : 'badge-active'}">
        ${modeLabel}
      </div>
    </div>
    <div style="font-size:13px;line-height:1.7;white-space:pre-wrap">${escapeHtml(text)}</div>
    <div style="margin-top:12px;padding:8px 12px;background:var(--c-gray-l);border-radius:6px;font-size:11px;color:var(--text-m);border-left:3px solid var(--c-yellow,#f59e0b);">
      ⚠️ <strong>Rechtlicher Hinweis:</strong> Diese KI-Auskunft ersetzt keine Rechts-, Steuer- oder Fachberatung. 
      Alle Angaben ohne Gewähr. Für verbindliche Entscheidungen konsultieren Sie bitte 
      einen zugelassenen Architekten, Fachanwalt oder zuständigen Behördenvertreter.
    </div>
  `;
}


// ─── Helpers ──────────────────────────────────────────────────────────────────

async function generateAiDocument(projectId, stageKey) {
  const docType = prompt(
    'Dokumenttyp wählen:\nBAUANTRAG, BAUGENEHMIGUNG, VERTRAG, GUTACHTEN, SONSTIGES',
    'SONSTIGES'
  );
  if (!docType) return;

  const btn = event.currentTarget;
  btn.disabled = true;
  btn.textContent = 'KI erstellt Dokument...';

  try {
    const resp = await fetch(`/ai/generate-document/${projectId}/${stageKey}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ doc_type: docType.trim().toUpperCase() }),
    });
    const data = await resp.json();

    if (data.answer) {
      showResult(data.answer, 'confirmation_required');
      if (data.saved) {
        showToast('Dokument wurde gespeichert (KI-Entwurf)', 'success');
      }
    } else {
      showToast('Fehler: ' + (data.error || 'Unbekannt'), 'danger');
    }
  } catch {
    showToast('Verbindungsfehler', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = '📄 Dokument per KI erstellen';
  }
}

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `flash flash-${type}`;
  toast.style.cssText = 'position:fixed;top:70px;right:20px;z-index:1000;max-width:350px;';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}


// ─── Leaflet Map ───────────────────────────────────────────────────────────────

function initMap(containerId, options) {
  const mapEl = document.getElementById(containerId);
  if (!mapEl) return null;

  const map = L.map(containerId, {
    center: options.center || [50.5, 9.0],
    zoom: options.zoom || 8,
  });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
  }).addTo(map);

  if (options.gemeinden) {
    options.gemeinden.forEach(g => {
      if (g.lat && g.lng) {
        const marker = L.marker([g.lat, g.lng])
          .addTo(map)
          .bindPopup(`<strong>${g.name}</strong><br>${g.landkreis}<br>
            <a href="${g.bauamt_url || '#'}" target="_blank">Bauamt</a>`);
      }
    });
  }

  return map;
}


// ─── Financing calculator ──────────────────────────────────────────────────────

function calcMonthlyRate() {
  const loan    = parseFloat(document.getElementById('bank_loan_amount')?.value || 0);
  const rate    = parseFloat(document.getElementById('bank_zinssatz')?.value || 0);
  const years   = parseFloat(document.getElementById('laufzeit_years')?.value || 0);
  const display = document.getElementById('monthly-rate-preview');
  if (!display) return;

  if (!loan || !rate || !years) { display.textContent = '—'; return; }

  const r = rate / 100 / 12;
  const n = years * 12;
  const monthly = loan * r * Math.pow(1 + r, n) / (Math.pow(1 + r, n) - 1);
  display.textContent = monthly.toLocaleString('de-DE', {
    style: 'currency', currency: 'EUR', maximumFractionDigits: 2
  });
}


// ─── Init on DOM ready ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // CSRF meta tag для AJAX
  if (!document.querySelector('meta[name="csrf-token"]')) {
    const meta = document.createElement('meta');
    meta.name = 'csrf-token';
    const tokenEl = document.querySelector('[data-csrf]');
    meta.content = tokenEl ? tokenEl.dataset.csrf : '';
    document.head.appendChild(meta);
  }

  // Финансовый калькулятор — live update
  ['bank_loan_amount', 'bank_zinssatz', 'laufzeit_years'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', calcMonthlyRate);
  });
});
