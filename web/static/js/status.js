/* Affiche l'etat reel du bot (heartbeat ecrit en base par la task du bot). */
(async function () {
  const el = document.getElementById('botStatus');
  if (!el) return;
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.online) {
      el.innerHTML = `<span class="dot"></span>Bot en ligne · ${data.latency_ms} ms`;
    } else {
      el.innerHTML = '<span class="dot off"></span>Bot hors ligne';
    }
  } catch {
    el.innerHTML = '<span class="dot off"></span>État inconnu';
  }
})();
