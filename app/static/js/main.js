/* BauNavigator — main.js */

// ─── AI Chat ──────────────────────────────────────────────────────────────────

const AiChat = {
  projectId: null,
  stageKey: null,
  browserEnabled: true,
  attachedFile: null,

  init(projectId, stageKey) {
    this.projectId = projectId;
    this.stageKey = stageKey;

    // Textarea: Enter sends, Shift+Enter = newline
    const textarea = document.getElementById('ai-input');
    if (textarea) {
      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.send();
        }
      });
    }

    // File input
    const fileInput = document.getElementById('chat-file-input');
    if (fileInput) {
      fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        this.attachedFile = file;
        const bar = document.getElementById('chat-attach-bar');
        const nameEl = document.getElementById('chat-attach-name');
        if (bar) bar.style.display = 'flex';
        if (nameEl) nameEl.textContent = file.name + ' (' + (file.size > 1024 ? Math.round(file.size/1024) + ' KB' : file.size + ' B') + ')';
        // Reset so same file can be re-selected
        fileInput.value = '';
      });
    }

    // Drag-drop on chat body
    const body = document.getElementById('ai-chat-body');
    if (body) {
      body.addEventListener('dragover', (e) => { e.preventDefault(); body.classList.add('drag-over'); });
      body.addEventListener('dragleave', () => body.classList.remove('drag-over'));
      body.addEventListener('drop', (e) => {
        e.preventDefault();
        body.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (!file) return;
        this.attachedFile = file;
        const bar = document.getElementById('chat-attach-bar');
        const nameEl = document.getElementById('chat-attach-name');
        if (bar) bar.style.display = 'flex';
        if (nameEl) nameEl.textContent = file.name;
      });
    }
  },

  async send() {
    const textarea = document.getElementById('ai-input');
    const message = (textarea?.value || '').trim();
    const file = this.attachedFile;

    if (!message && !file) return;

    // Show user message (with file indicator if attached)
    let userText = message || '(Datei hochgeladen)';
    if (file && message) userText = message;
    const userMsgEl = this.addMessage(userText, 'user');
    if (file && userMsgEl) {
      const chip = document.createElement('div');
      chip.style.cssText = 'font-size:11px;margin-top:4px;color:rgba(255,255,255,.8);';
      chip.textContent = '📎 ' + file.name;
      userMsgEl.appendChild(chip);
    }

    if (textarea) textarea.value = '';
    this.clearFile();
    this.addMessage('…', 'bot', 'loading');

    try {
      let resp;
      if (file) {
        const fd = new FormData();
        fd.append('message', message || '');
        fd.append('project_id', this.projectId);
        fd.append('stage_key', this.stageKey);
        fd.append('use_browser', this.browserEnabled ? 'true' : 'false');
        fd.append('file', file);
        resp = await fetch('/ai/chat', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() },
          body: fd,
        });
      } else {
        resp = await fetch('/ai/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify({
            message,
            project_id: this.projectId,
            stage_key: this.stageKey,
            use_browser: this.browserEnabled,
          }),
        });
      }

      const data = await resp.json();
      this.removeLoading();

      if (data.success) {
        const botEl = this.addMessage(data.response, 'bot');
        // Show agent + tool badges inside the message
        if (botEl && (data.agent_name || (data.tool_calls && data.tool_calls.length))) {
          const meta = document.createElement('div');
          meta.style.cssText = 'margin-top:6px;display:flex;flex-wrap:wrap;gap:4px;';
          if (data.agent_name) {
            const agentIcons = { LandAgent:'🏗', PermitAgent:'📋', ConstructionAgent:'🔨', FinishingAgent:'🪟', GeneralAgent:'🤖' };
            const ab = document.createElement('span');
            ab.style.cssText = 'font-size:10px;background:var(--c-blue-l);color:var(--c-blue);border-radius:10px;padding:1px 8px;';
            ab.textContent = (agentIcons[data.agent_name] || '🤖') + ' ' + data.agent_name;
            meta.appendChild(ab);
          }
          if (data.tool_calls && data.tool_calls.length) {
            const tb = document.createElement('span');
            tb.style.cssText = 'font-size:10px;background:#e0f2fe;color:#0369a1;border-radius:10px;padding:1px 8px;';
            tb.textContent = '🔍 ' + data.tool_calls.length + ' Suche(n)';
            meta.appendChild(tb);
          }
          botEl.appendChild(meta);
        }
      } else {
        this.addMessage('Fehler: ' + (data.response || 'Unbekannter Fehler'), 'bot', 'error');
      }
    } catch (err) {
      this.removeLoading();
      this.addMessage('Verbindungsfehler. Bitte versuchen Sie es erneut.', 'bot', 'error');
    }
  },

  addMessage(text, type, extra) {
    const body = document.getElementById('ai-chat-body');
    if (!body) return null;

    const div = document.createElement('div');
    div.className = `ai-msg ai-msg-${type}${extra ? ' ' + extra : ''}`;

    div.innerHTML = text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>')
      .replace(/^- (.+)$/gm, '• $1');

    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
  },

  removeLoading() {
    const loading = document.querySelector('.ai-chat-body .loading');
    if (loading) loading.remove();
  },

  toggleBrowser() {
    this.browserEnabled = !this.browserEnabled;
    const btn = document.getElementById('btn-browser');
    if (btn) {
      btn.classList.toggle('chat-tool-active', this.browserEnabled);
      btn.title = this.browserEnabled ? 'Websuche deaktivieren' : 'Websuche aktivieren';
    }
  },

  clearFile() {
    this.attachedFile = null;
    const bar = document.getElementById('chat-attach-bar');
    if (bar) bar.style.display = 'none';
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
      showResult(data.response, data.mode, data.tool_calls, data.agent_name);
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

function showResult(text, mode, toolCalls, agentName) {
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

  const agentIcons = { LandAgent: '🏗', PermitAgent: '📋', ConstructionAgent: '🔨', FinishingAgent: '🪟', GeneralAgent: '🤖' };
  const agentLabel = agentName ? `<span style="font-size:10px;background:var(--c-blue-l);color:var(--c-blue);border-radius:10px;padding:1px 8px;margin-left:8px;">${agentIcons[agentName] || '🤖'} ${agentName}</span>` : '';

  // Build tool-calls trace badge
  let toolBadge = '';
  if (toolCalls && toolCalls.length > 0) {
    const toolNames = { web_search: '🔍', fetch_page: '🌐' };
    const items = toolCalls.map(t => {
      const icon = toolNames[t.tool] || '🔧';
      const label = t.tool === 'web_search'
        ? escapeHtml(t.input.query || '')
        : escapeHtml((t.input.url || '').replace(/^https?:\/\//, '').slice(0, 60));
      return `<span style="opacity:.85;">${icon} ${label}</span>`;
    }).join(' · ');
    toolBadge = `<div style="margin-bottom:10px;font-size:11px;color:#0369a1;background:#e0f2fe;border-radius:4px;padding:4px 10px;border-left:3px solid #0369a1;">
      🤖 Agent hat ${toolCalls.length} Suche(n) durchgeführt: ${items}
    </div>`;
  }

  panel.innerHTML = `
    <div class="card-header" style="display:flex;align-items:center;gap:6px;">
      <div class="badge ${mode === 'autonomous' ? 'badge-done' : mode === 'human_required' ? 'badge-draft' : 'badge-active'}">
        ${modeLabel}
      </div>${agentLabel}
    </div>
    ${toolBadge}
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
