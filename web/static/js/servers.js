/* Page "Mes serveurs" : finalise l'OAuth2 puis liste les guildes. */
const CLIENT_ID = document.body.dataset.clientId;

const SVG = {
  bot:    `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="3"/><line x1="12" y1="8" x2="12" y2="11"/><line x1="8" y1="15" x2="8" y2="17"/><line x1="16" y1="15" x2="16" y2="17"/></svg>`,
  star:   `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  user:   `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  lock:   `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
  plus:   `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  cirOn:  `<svg width="7" height="7" viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="currentColor"/></svg>`,
  cirOff: `<svg width="7" height="7" viewBox="0 0 8 8"><circle cx="4" cy="4" r="3" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`,
};

function logout() {
  fetch('/api/logout', { method: 'POST' }).finally(() => location.href = '/');
}
function initials(n) { return n.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase(); }
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

function hasAdmin(g) {
  if (!g) return false;
  if (g.owner) return true;
  try {
    const p = BigInt(g.permissions || '0');
    return (p & 0x8n) !== 0n || (p & 0x20n) !== 0n;
  } catch { return false; }
}

function addRipple(el, e) {
  const r = document.createElement('span');
  r.className = 'ripple';
  const rect = el.getBoundingClientRect();
  const s = Math.max(rect.width, rect.height);
  r.style.cssText = `width:${s}px;height:${s}px;left:${e.clientX - rect.left - s / 2}px;top:${e.clientY - rect.top - s / 2}px`;
  el.appendChild(r);
  setTimeout(() => r.remove(), 600);
}

window.addEventListener('load', async () => {
  const params = new URLSearchParams(location.search);
  const code = params.get('code');

  if (code) {
    history.replaceState({}, '', '/servers.html');
    try {
      const r = await fetch('/api/oauth-exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, state: params.get('state') })
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
    } catch (err) {
      document.getElementById('grid').innerHTML =
        `<div class="loading" style="color:var(--red)">Erreur de connexion : ${esc(err.message || err)}<br><a href="/" style="color:var(--accent)">Réessayer</a></div>`;
      return;
    }
  }

  try {
    const res = await fetch('/api/my-guilds');
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.error) {
      if (res.status === 401) { location.href = '/'; return; }
      throw new Error(data.error || ('HTTP ' + res.status));
    }

    document.getElementById('uName').textContent = data.user.username;
    if (data.user.avatar) {
      document.getElementById('uAvatar').src =
        `https://cdn.discordapp.com/avatars/${data.user.id}/${data.user.avatar}.png`;
    }
    render(data.guilds, new Set((data.bot_guild_ids || []).map(String)));
  } catch (err) {
    document.getElementById('grid').innerHTML =
      `<div class="loading" style="color:var(--red)">Erreur de chargement : ${esc(err.message || err)}</div>`;
  }
});

function render(guilds, botIds) {
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  let cBot = 0, cAdm = 0;

  const score = g => {
    const a = hasAdmin(g), b = botIds.has(String(g.id));
    if (b && a) return 0;
    if (b && !a) return 1;
    if (!b && a) return 2;
    return 3;
  };

  const sorted = [...guilds].sort((a, b) => score(a) - score(b));
  let lastGroup = -1;

  sorted.forEach((g, i) => {
    const isAdmin = hasAdmin(g);
    const hasBot = botIds.has(String(g.id));
    const grp = score(g);
    if (hasBot) cBot++;
    if (isAdmin) cAdm++;

    if (grp !== lastGroup) {
      lastGroup = grp;
      const sep = document.createElement('div');
      sep.className = 'section-sep';
      const labels = [
        [SVG.bot, 'Bot actif · Administrateur'],
        [SVG.bot, 'Bot actif · Membre'],
        [SVG.star, 'Administrateur · Bot absent'],
        [SVG.user, 'Autres serveurs'],
      ];
      sep.innerHTML = labels[grp][0] + labels[grp][1];
      grid.appendChild(sep);
    }

    let cls = 'srv';
    if (hasBot && isAdmin) cls += ' clickable';
    else if (!hasBot && !isAdmin) cls += ' greyed';
    else if (!hasBot && isAdmin) cls += ' invite-me';

    const el = document.createElement(hasBot && isAdmin ? 'a' : 'div');
    el.className = cls;
    el.style.animationDelay = Math.min(i * 0.035, 0.6) + 's';
    if (hasBot && isAdmin) el.href = `/dash.html?guild=${g.id}`;

    const iconHTML = g.icon
      ? `<img class="srv-icon" src="https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png?size=64" alt="" loading="lazy">`
      : `<div class="srv-initials">${esc(initials(g.name))}</div>`;

    const lock = (hasBot && !isAdmin)
      ? `<div class="badge-lock" title="Tu n'es pas admin">${SVG.lock}</div>` : '';

    const overlay = (!hasBot && isAdmin) ? `
      <div class="srv-overlay">
        <div class="overlay-txt">Bot absent de ce serveur</div>
        <a class="btn-add" href="https://discord.com/oauth2/authorize?client_id=${CLIENT_ID}&permissions=8&guild_id=${g.id}&scope=bot+applications.commands" target="_blank" rel="noopener" onclick="event.stopPropagation()">
          ${SVG.plus} Ajouter le bot
        </a>
      </div>` : '';

    el.innerHTML = `
      ${overlay}
      <div class="icon-wrap">${iconHTML}${lock}</div>
      <div class="srv-name" title="${esc(g.name)}">${esc(g.name)}</div>
      <span class="srv-badge ${hasBot ? 'badge-on' : 'badge-off'}">${hasBot ? SVG.cirOn : SVG.cirOff}${hasBot ? 'Actif' : 'Inactif'}</span>
    `;

    if (hasBot && isAdmin) el.addEventListener('click', e => addRipple(el, e));
    grid.appendChild(el);
  });

  document.getElementById('sTot').textContent = guilds.length;
  document.getElementById('sBot').textContent = cBot;
  document.getElementById('sAdm').textContent = cAdm;
  document.getElementById('stats').style.display = 'flex';
}
