/* Dashboard serveur : lit l'etat via l'API, ecrit la config et pousse des
   actions dans la file que le bot consomme (cog bridge). */

const GUILD = document.body.dataset.guildId;
let CSRF = document.body.dataset.csrf;
let DATA = null;                 // dernier etat renvoye par l'API
const DIRTY = new Set();         // modules modifies mais pas encore enregistres
const DRAFT = {};                // config en cours d'edition

const ICONS = {
  home:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  ticket:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9a3 3 0 0 1 0 6v3a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3a3 3 0 0 1 0-6V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2z"/></svg>',
  shield:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
  filter:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>',
  wave:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
  list:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>',
  chart: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
  term:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
  book:  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
};

// ── Utilitaires ────────────────────────────────────────────────────────
const $ = sel => document.querySelector(sel);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(message, kind = '') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

function logout() {
  fetch('/api/logout', { method: 'POST' }).finally(() => location.href = '/');
}

function timeAgo(seconds) {
  const diff = Date.now() / 1000 - seconds;
  if (diff < 60) return "a l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  return `il y a ${Math.floor(diff / 86400)} j`;
}

async function api(path, options = {}) {
  const opts = { headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': CSRF }, ...options };
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({}));
  if (res.status === 401) { location.href = '/'; throw new Error('non authentifié'); }
  if (!res.ok) throw new Error(body.error || body.detail || `HTTP ${res.status}`);
  return body;
}

// ── Chargement ─────────────────────────────────────────────────────────
async function boot() {
  try {
    const [me, state] = await Promise.all([
      api('/api/my-guilds'),
      api(`/api/guild/${GUILD}`),
    ]);
    DATA = state;
    CSRF = state.csrf || CSRF;

    $('#uName').textContent = me.user.username;
    if (me.user.avatar) {
      $('#uAvatar').src = `https://cdn.discordapp.com/avatars/${me.user.id}/${me.user.avatar}.png`;
    }

    Object.entries(state.config).forEach(([key, conf]) => DRAFT[key] = { ...conf });
    renderSide();
    renderAll();
    select(location.hash.slice(1) || 'overview');
  } catch (err) {
    $('#main').innerHTML = `<div class="loading" style="color:var(--red)">
      Impossible de charger ce serveur : ${esc(err.message)}<br>
      <a href="/servers.html" style="color:var(--accent)">Retour à mes serveurs</a></div>`;
  }
}

function renderSide() {
  const g = DATA.guild;
  $('#sideHead').innerHTML = `
    ${g.icon
      ? `<img src="https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png?size=64" alt="">`
      : `<div class="ini">${esc(g.name.slice(0, 2).toUpperCase())}</div>`}
    <div class="meta">
      <div class="gname" title="${esc(g.name)}">${esc(g.name)}</div>
      <div class="gsub">${g.member_count} membres</div>
    </div>`;

  const items = [
    ['overview', 'Vue d\'ensemble', ICONS.home, null],
    ['sep', 'Modules', '', null],
    ...Object.entries(window.MODULES).map(([key, mod]) =>
      [key, mod.label, ICONS[mod.icon] || ICONS.list, key]),
    ['sep2', 'Gestion', '', null],
    ['tickets_list', 'Tickets ouverts', ICONS.ticket, null],
    ['console', 'Console', ICONS.term, null],
    ['journal', 'Journal', ICONS.book, null],
  ];

  $('#sideNav').innerHTML = items.map(([id, label, icon, moduleKey]) => {
    if (id.startsWith('sep')) return `<div class="nav-sep">${esc(label)}</div>`;
    const on = moduleKey && DATA.config[moduleKey]?.enabled;
    return `<button class="nav-item" data-panel="${id}">${icon}<span>${esc(label)}</span>
      ${moduleKey ? `<i class="pip ${on ? 'on' : ''}"></i>` : ''}</button>`;
  }).join('');

  $('#sideNav').querySelectorAll('.nav-item').forEach(button =>
    button.addEventListener('click', () => select(button.dataset.panel)));
}

function select(id) {
  if (!document.getElementById(`panel-${id}`)) id = 'overview';
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`panel-${id}`).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(b =>
    b.classList.toggle('active', b.dataset.panel === id));
  history.replaceState({}, '', `#${id}`);
}

function renderAll() {
  $('#main').innerHTML = [
    overviewPanel(),
    ...Object.keys(window.MODULES).map(modulePanel),
    ticketsPanel(),
    consolePanel(),
    journalPanel(),
  ].join('');

  Object.keys(window.MODULES).forEach(bindModule);
  bindConsole();
  bindOverview();
}

// ── Vue d'ensemble ─────────────────────────────────────────────────────
function overviewPanel() {
  const c = DATA.counters, g = DATA.guild;
  const stats = DATA.stats;
  const max = Math.max(1, ...stats.map(s => s.messages));

  const bars = stats.map(s => `
    <div class="bar-col" title="${s.day} · ${s.messages} messages, ${s.joins} arrivées, ${s.leaves} départs">
      <div class="bar msg" style="height:${(s.messages / max * 100).toFixed(1)}%"></div>
      <div class="bar join" style="height:${(s.joins / max * 100).toFixed(1)}%"></div>
      <div class="bar leave" style="height:${(s.leaves / max * 100).toFixed(1)}%"></div>
    </div>`).join('');

  const today = stats[stats.length - 1] || { messages: 0, joins: 0, sanctions: 0 };

  return `<section class="panel" id="panel-overview">
    <div class="panel-head">
      <div>
        <h1>Vue d'ensemble</h1>
        <p>État en direct de <b>${esc(g.name)}</b>. Les compteurs sont écrits par le bot,
           le dashboard ne fait que les lire.</p>
      </div>
      <button class="btn small" id="btnRefresh">Rafraîchir le cache</button>
    </div>

    <div class="tiles">
      <div class="tile"><div class="v">${g.member_count}</div><div class="l">Membres</div></div>
      <div class="tile"><div class="v">${c.open_tickets}</div><div class="l">Tickets ouverts</div></div>
      <div class="tile"><div class="v">${c.warnings}</div><div class="l">Avertissements</div></div>
      <div class="tile"><div class="v">${today.messages}</div><div class="l">Messages aujourd'hui</div></div>
      <div class="tile ${c.lockdown ? 'alert' : ''}">
        <div class="v">${c.lockdown ? 'ON' : 'OFF'}</div><div class="l">Lockdown</div></div>
    </div>

    <div class="card">
      <h2>Activité — 14 derniers jours</h2>
      <div class="hint">Messages, arrivées et départs enregistrés par les tasks du bot.</div>
      ${stats.length ? `<div class="chart">${bars}</div>
        <div class="chart-x">${stats.map(s => `<span>${s.day.slice(8)}</span>`).join('')}</div>
        <div class="legend">
          <span><i style="background:var(--accent)"></i>Messages</span>
          <span><i style="background:var(--green)"></i>Arrivées</span>
          <span><i style="background:var(--muted)"></i>Départs</span>
        </div>` : '<div class="empty">Pas encore de données.</div>'}
    </div>

    <div class="card">
      <h2>Actions rapides</h2>
      <div class="hint">Chaque bouton dépose un ordre dans la file ; le bot l'exécute en moins de 2 s.</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn ${c.lockdown ? '' : 'danger'}" data-quick="lockdown" data-enable="${c.lockdown ? 0 : 1}">
          ${c.lockdown ? 'Déverrouiller le serveur' : 'Verrouiller le serveur'}
        </button>
        <button class="btn" data-quick="post_ticket_panel">Publier le panneau de tickets</button>
        <button class="btn" data-quick="raid_reset">Réinitialiser le mode raid</button>
      </div>
    </div>
  </section>`;
}

function bindOverview() {
  $('#btnRefresh')?.addEventListener('click', () => runAction('refresh', {}));
  document.querySelectorAll('[data-quick]').forEach(button => {
    button.addEventListener('click', () => {
      const name = button.dataset.quick;
      if (name === 'lockdown') {
        const enable = button.dataset.enable === '1';
        if (enable && !confirm('Verrouiller tous les salons du serveur ?')) return;
        runAction('lockdown', { enable });
      } else if (name === 'post_ticket_panel') {
        runAction('post_ticket_panel', { channel_id: DRAFT.tickets.panel_channel_id });
      } else {
        runAction(name, {});
      }
    });
  });
}

// ── Panneaux de modules (generes depuis le schema) ─────────────────────
function modulePanel(key) {
  const mod = window.MODULES[key];
  const conf = DRAFT[key];
  const fields = Object.entries(mod.fields).filter(([name]) => name !== 'enabled');

  return `<section class="panel" id="panel-${key}">
    <div class="panel-head">
      <div><h1>${esc(mod.label)}</h1><p>${esc(mod.description)}</p></div>
    </div>

    <div class="module-toggle">
      <div class="txt">
        <b>Activer le module</b>
        <span>Le bot ignore complètement ce module tant qu'il est désactivé.</span>
      </div>
      <label class="switch">
        <input type="checkbox" data-module="${key}" data-field="enabled" ${conf.enabled ? 'checked' : ''}>
        <span class="slider"></span>
      </label>
    </div>

    <div class="card">
      <h2>Configuration</h2>
      <div class="hint">Ces valeurs sont relues par le bot à chaque événement : aucun redémarrage nécessaire.</div>
      <div class="card-row">
        ${fields.map(([name, spec]) => renderField(key, name, spec, conf[name])).join('')}
      </div>
    </div>

    <div class="savebar" id="save-${key}">
      <span class="t">Modifications non enregistrées</span>
      <button class="btn small" data-reset="${key}">Annuler</button>
      <button class="btn primary small" data-save="${key}">Enregistrer</button>
    </div>
  </section>`;
}

function channelOptions(selected, kind) {
  const list = DATA.guild.channels
    .filter(c => kind === 'category' ? c.type === 'category' : c.type === 'text')
    .sort((a, b) => a.position - b.position);
  return [`<option value="0">— aucun —</option>`,
    ...list.map(c => `<option value="${c.id}" ${String(c.id) === String(selected) ? 'selected' : ''}>
      ${kind === 'category' ? '' : '#'}${esc(c.name)}</option>`)].join('');
}

function roleOptions(selected) {
  return [`<option value="0">— aucun —</option>`,
    ...DATA.guild.roles.filter(r => r.name !== '@everyone').map(r =>
      `<option value="${r.id}" ${String(r.id) === String(selected) ? 'selected' : ''}>
        @${esc(r.name)}${r.assignable ? '' : ' (hors portée du bot)'}</option>`)].join('');
}

function renderField(module, name, spec, value) {
  const attr = `data-module="${module}" data-field="${name}"`;

  switch (spec.type) {
    case 'bool':
      return `<label class="field" style="display:flex;align-items:center;gap:12px">
        <span class="lbl" style="margin:0;flex:1">${esc(spec.label)}</span>
        <span class="switch"><input type="checkbox" ${attr} ${value ? 'checked' : ''}><span class="slider"></span></span>
      </label>`;

    case 'int':
      return `<label class="field"><span class="lbl">${esc(spec.label)}</span>
        <input type="number" ${attr} value="${value}" min="${spec.min ?? 0}" max="${spec.max ?? 999999}"></label>`;

    case 'text':
      return `<label class="field"><span class="lbl">${esc(spec.label)}</span>
        <input type="text" ${attr} value="${esc(value)}"></label>`;

    case 'textarea':
      return `<label class="field"><span class="lbl">${esc(spec.label)}</span>
        <textarea ${attr}>${esc(value)}</textarea></label>`;

    case 'select':
      return `<label class="field"><span class="lbl">${esc(spec.label)}</span>
        <select ${attr}>${spec.options.map(([v, l]) =>
          `<option value="${v}" ${v === value ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></label>`;

    case 'channel':
      return `<label class="field"><span class="lbl">${esc(spec.label)}</span>
        <select ${attr}>${channelOptions(value, spec.channel_type)}</select></label>`;

    case 'role':
      return `<label class="field"><span class="lbl">${esc(spec.label)}</span>
        <select ${attr}>${roleOptions(value)}</select></label>`;

    case 'multirole': {
      const picked = (value || []).map(String);
      return `<div class="field"><span class="lbl">${esc(spec.label)}</span>
        <div class="chips" ${attr} data-multi="role">
          ${DATA.guild.roles.filter(r => r.name !== '@everyone').map(r =>
            `<span class="chip ${picked.includes(String(r.id)) ? 'on' : ''}" data-id="${r.id}">
              <i style="background:${r.color}"></i>${esc(r.name)}</span>`).join('') || '<span class="lbl">Aucun rôle</span>'}
        </div></div>`;
    }

    case 'multichannel': {
      const picked = (value || []).map(String);
      return `<div class="field"><span class="lbl">${esc(spec.label)}</span>
        <div class="chips" ${attr} data-multi="channel">
          ${DATA.guild.channels.filter(c => c.type === 'text').map(c =>
            `<span class="chip ${picked.includes(String(c.id)) ? 'on' : ''}" data-id="${c.id}">#${esc(c.name)}</span>`).join('')}
        </div></div>`;
    }

    default:
      return '';
  }
}

function bindModule(key) {
  const panel = document.getElementById(`panel-${key}`);

  panel.querySelectorAll('[data-field]').forEach(input => {
    if (input.classList.contains('chips')) {
      input.querySelectorAll('.chip').forEach(chip => chip.addEventListener('click', () => {
        chip.classList.toggle('on');
        DRAFT[key][input.dataset.field] =
          [...input.querySelectorAll('.chip.on')].map(c => c.dataset.id);
        markDirty(key);
      }));
      return;
    }
    const event = input.tagName === 'SELECT' || input.type === 'checkbox' ? 'change' : 'input';
    input.addEventListener(event, () => {
      DRAFT[key][input.dataset.field] =
        input.type === 'checkbox' ? input.checked
        : input.type === 'number' ? Number(input.value)
        : input.value;
      markDirty(key);
    });
  });

  panel.querySelector(`[data-save="${key}"]`).addEventListener('click', () => saveModule(key));
  panel.querySelector(`[data-reset="${key}"]`).addEventListener('click', () => {
    DRAFT[key] = { ...DATA.config[key] };
    DIRTY.delete(key);
    renderAll();
    select(key);
  });
}

function markDirty(key) {
  DIRTY.add(key);
  document.getElementById(`save-${key}`).classList.add('show');
}

async function saveModule(key) {
  const button = document.querySelector(`[data-save="${key}"]`);
  button.disabled = true;
  try {
    const body = await api(`/api/guild/${GUILD}/config/${key}`, {
      method: 'POST',
      body: JSON.stringify({ config: DRAFT[key], csrf: CSRF }),
    });
    DATA.config[key] = body.config;
    DRAFT[key] = { ...body.config };
    DIRTY.delete(key);
    document.getElementById(`save-${key}`).classList.remove('show');
    renderSide();
    toast(`${window.MODULES[key].label} enregistré.`, 'ok');
  } catch (err) {
    toast(`Échec : ${err.message}`, 'err');
  } finally {
    button.disabled = false;
  }
}

// ── Tickets ────────────────────────────────────────────────────────────
function ticketsPanel() {
  const rows = DATA.tickets.map(t => `<tr>
    <td>#${t.id}</td>
    <td>&lt;@${t.user_id}&gt;</td>
    <td><span class="pill ${t.status}">${t.status === 'open' ? 'ouvert' : 'fermé'}</span></td>
    <td>${timeAgo(t.opened_at)}</td>
    <td>${t.claimed_by ? `&lt;@${t.claimed_by}&gt;` : '—'}</td>
    <td style="text-align:right">${t.status === 'open'
      ? `<button class="btn small danger" data-close-ticket="${t.id}">Fermer</button>` : ''}</td>
  </tr>`).join('');

  return `<section class="panel" id="panel-tickets_list">
    <div class="panel-head">
      <div><h1>Tickets</h1><p>Les 20 derniers tickets du serveur. Fermer ici supprime le salon et archive le transcript.</p></div>
    </div>
    <div class="card">
      ${DATA.tickets.length ? `<table>
        <thead><tr><th>ID</th><th>Auteur</th><th>État</th><th>Ouvert</th><th>Pris par</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table>` : '<div class="empty">Aucun ticket pour le moment.</div>'}
    </div>
  </section>`;
}

// ── Console ────────────────────────────────────────────────────────────
function consolePanel() {
  const channelSelect = `<select id="cChannel">${channelOptions(0)}</select>`;
  const roleSelect = `<select id="cRole">${roleOptions(0)}</select>`;

  return `<section class="panel" id="panel-console">
    <div class="panel-head">
      <div><h1>Console</h1>
        <p>Commande le bot depuis le site. Chaque ordre est revérifié côté bot
           (tes permissions et la hiérarchie des rôles) avant exécution.</p></div>
    </div>

    <div class="console-grid">
      <div class="card">
        <h2>Envoyer un message</h2>
        <div class="hint">Le bot poste le message dans le salon choisi.</div>
        <label class="field"><span class="lbl">Salon</span>${channelSelect}</label>
        <label class="field"><span class="lbl">Message</span><textarea id="cMessage" maxlength="2000"></textarea></label>
        <div style="display:flex;gap:9px">
          <button class="btn primary" id="btnSend">Envoyer</button>
          <button class="btn" id="btnAnnounce">Envoyer en embed</button>
        </div>
      </div>

      <div class="card">
        <h2>Modération</h2>
        <div class="hint">Identifiant Discord du membre (clic droit → Copier l'identifiant).</div>
        <label class="field"><span class="lbl">ID du membre</span><input type="text" id="cUser" placeholder="123456789012345678"></label>
        <label class="field"><span class="lbl">Raison</span><input type="text" id="cReason" placeholder="Comportement inapproprié"></label>
        <label class="field"><span class="lbl">Durée du timeout (minutes)</span><input type="number" id="cMinutes" value="10" min="1" max="40320"></label>
        <div style="display:flex;gap:9px;flex-wrap:wrap">
          <button class="btn" data-mod="warn">Avertir</button>
          <button class="btn" data-mod="timeout">Exclure</button>
          <button class="btn" data-mod="untimeout">Lever l'exclusion</button>
          <button class="btn danger" data-mod="kick">Expulser</button>
          <button class="btn danger" data-mod="ban">Bannir</button>
          <button class="btn" data-mod="unban">Débannir</button>
        </div>
      </div>

      <div class="card">
        <h2>Rôles</h2>
        <div class="hint">Ajoute ou retire un rôle. Un rôle au-dessus du tien est refusé.</div>
        <label class="field"><span class="lbl">Rôle</span>${roleSelect}</label>
        <div style="display:flex;gap:9px">
          <button class="btn" data-mod="role_add">Ajouter le rôle</button>
          <button class="btn" data-mod="role_remove">Retirer le rôle</button>
        </div>
      </div>

      <div class="card">
        <h2>Nettoyage</h2>
        <div class="hint">Supprime les N derniers messages d'un salon (200 max).</div>
        <label class="field"><span class="lbl">Salon</span><select id="cPurgeChannel">${channelOptions(0)}</select></label>
        <label class="field"><span class="lbl">Nombre de messages</span><input type="number" id="cAmount" value="10" min="1" max="200"></label>
        <button class="btn danger" id="btnPurge">Supprimer</button>
      </div>
    </div>

    <div class="card">
      <h2>Dernières actions</h2>
      <div class="hint">Résultat renvoyé par le bot après exécution.</div>
      <div class="actions-feed" id="actionsFeed">${actionsFeed()}</div>
    </div>
  </section>`;
}

function actionsFeed() {
  if (!DATA.actions.length) return '<div class="empty">Aucune action pour l\'instant.</div>';
  return DATA.actions.map(a => `<div class="feed-item">
    <span class="pill ${a.status}">${a.status}</span>
    <div style="flex:1">
      <span class="act">${esc(a.action)}</span> — ${esc(a.result || 'en attente…')}
      <div class="who">demandé par &lt;@${a.requested_by}&gt; · ${timeAgo(a.created_at)}</div>
    </div>
  </div>`).join('');
}

function bindConsole() {
  const val = id => document.getElementById(id)?.value ?? '';

  $('#btnSend')?.addEventListener('click', () =>
    runAction('send_message', { channel_id: val('cChannel'), content: val('cMessage') }));

  $('#btnAnnounce')?.addEventListener('click', () =>
    runAction('announce', { channel_id: val('cChannel'), content: val('cMessage'), title: '' }));

  $('#btnPurge')?.addEventListener('click', () => {
    if (!confirm(`Supprimer ${val('cAmount')} messages ?`)) return;
    runAction('purge', { channel_id: val('cPurgeChannel'), amount: Number(val('cAmount')) });
  });

  document.querySelectorAll('[data-mod]').forEach(button =>
    button.addEventListener('click', () => {
      const action = button.dataset.mod;
      const userId = val('cUser').trim();
      if (!/^\d{15,25}$/.test(userId)) return toast('Identifiant Discord invalide.', 'warn');
      const payload = { user_id: userId, reason: val('cReason') };
      if (action === 'timeout') payload.minutes = Number(val('cMinutes'));
      if (action.startsWith('role_')) payload.role_id = val('cRole');
      if ((action === 'ban' || action === 'kick') &&
          !confirm(`Confirmer : ${action} de ${userId} ?`)) return;
      runAction(action, payload);
    }));

  document.querySelectorAll('[data-close-ticket]').forEach(button =>
    button.addEventListener('click', () =>
      runAction('close_ticket', { ticket_id: Number(button.dataset.closeTicket) })));
}

// ── File d'actions ─────────────────────────────────────────────────────
async function runAction(action, payload) {
  try {
    const { id } = await api(`/api/guild/${GUILD}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, payload, csrf: CSRF }),
    });
    toast('Ordre envoyé au bot…');
    const outcome = await waitForAction(id);
    if (outcome.status === 'done') toast(outcome.result, 'ok');
    else if (outcome.status === 'timeout') toast('Le bot ne répond pas (hors ligne ?)', 'warn');
    else toast(outcome.result || 'Action refusée', 'err');
    await reload();
  } catch (err) {
    toast(`Échec : ${err.message}`, 'err');
  }
}

async function waitForAction(id, tries = 15) {
  for (let i = 0; i < tries; i++) {
    await new Promise(r => setTimeout(r, 700));
    const row = await api(`/api/guild/${GUILD}/action/${id}`);
    if (row.status !== 'pending' && row.status !== 'running') return row;
  }
  return { status: 'timeout' };
}

async function reload() {
  const state = await api(`/api/guild/${GUILD}`);
  DATA = state;
  Object.entries(state.config).forEach(([key, conf]) => {
    if (!DIRTY.has(key)) DRAFT[key] = { ...conf };
  });
  const current = document.querySelector('.panel.active')?.id.replace('panel-', '') || 'overview';
  renderSide();
  renderAll();
  select(current);
}

// ── Journal ────────────────────────────────────────────────────────────
function journalPanel() {
  const rows = DATA.audit.map(a => `<tr>
    <td>${timeAgo(a.created_at)}</td>
    <td>${esc(a.username)}</td>
    <td><b style="color:var(--accent)">${esc(a.action)}</b></td>
    <td>${esc(a.details)}</td>
  </tr>`).join('');

  return `<section class="panel" id="panel-journal">
    <div class="panel-head">
      <div><h1>Journal</h1><p>Tout ce qui a été fait depuis le dashboard, avec l'auteur.</p></div>
    </div>
    <div class="card">
      ${DATA.audit.length ? `<table>
        <thead><tr><th>Quand</th><th>Qui</th><th>Action</th><th>Détail</th></tr></thead>
        <tbody>${rows}</tbody></table>` : '<div class="empty">Journal vide.</div>'}
    </div>
  </section>`;
}

window.addEventListener('beforeunload', e => {
  if (DIRTY.size) { e.preventDefault(); e.returnValue = ''; }
});

boot();
