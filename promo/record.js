/* Enregistre une démo du VRAI dashboard : vrais écrans, vraie souris, vrais clics.
   L'API du bot est simulée avec les vrais salons et rôles du serveur. */
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs'), path = require('path');

const DIR    = '/home/user/JZ-HACKK';
const OUT    = '/tmp/claude-0/-home-user-JZ-HACKK/94986eff-3085-57c3-be49-20a04d5308df/scratchpad/rec2';
const ORIGIN = 'https://dashboard.moderabot.xyz';
const GUILD  = '1539309331386867742';
const VW = 1080, VH = 1920;             // rendu natif 1080x1920 (pas d'agrandissement)
const CSSW = 600, SCALE = VW / CSSW;    // la page se calcule en 600 px puis est agrandie x1.8

/* ---- données réelles du serveur (relevées sur Discord) ---- */
const USER   = { id:'331', username:'jz', global_name:'JZ | NYaka', avatar:null, discriminator:'0' };
const GUILDS = [{ id:GUILD, name:'ModeraBot | Votre Bot Personnaliser', icon:'abc',
                  owner:true, permissions:'8', approximate_member_count:60, approximate_presence_count:11 }];
const CHANNELS = [
  {id:'101',name:'🔍・besoin-daide'},   {id:'102',name:'📄・suggestion'},
  {id:'103',name:'📬・moderabot-support'}, {id:'104',name:'💭・chat-staff'},
  {id:'105',name:'ticket-sasha-yt-pro'},   {id:'106',name:'ticket-valtmanagement'},
];
const CATEGORIES = [
  {id:'201',name:'Espace Support'}, {id:'202',name:'Espace Vocal'},
  {id:'203',name:'Espace Moderateur'}, {id:'204',name:'Logs AyetherBot'},
];
const ROLES = [
  {id:'301',name:'Owner'}, {id:'302',name:'Staff'}, {id:'303',name:'Modérateur'},
  {id:'304',name:'Support'}, {id:'305',name:'Membre'},
];
const CONFIG = {
  prefix:'+',
  tickets:{panel:{titre:'',description:'',logs:null,couleur:'#5865F2',mode:'bouton'},choix:[]},
  logs:{msg:{enabled:true,channel:104},ticket:{enabled:true,channel:104}},
  antiraid:{enabled:true,modlog:104}, antilink:{enabled:true,action:'warn',whitelist:[]},
  welcome:{enabled:true,channel_id:101,mode:'texte',message:'Bienvenue {user} !'},
  levels:{xp_min:5,xp_max:15}, captcha:{enabled:true,channel_id:101},
};
const CORS = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'};

/* ---- curseur visible + légendes, injectés dans chaque page ---- */
const OVERLAY = () => {
 const build = () => {
  const css = document.createElement('style');
  css.textContent = `
  #__cur{position:fixed;left:0;top:0;width:30px;height:30px;z-index:2147483647;pointer-events:none;
    transform:translate(-100px,-100px);filter:drop-shadow(0 3px 7px rgba(0,0,0,.75));transition:transform .05s linear}
  #__ring{position:fixed;left:0;top:0;width:34px;height:34px;border-radius:50%;border:3px solid #22d3ee;
    z-index:2147483646;pointer-events:none;opacity:0;transform:translate(-50%,-50%) scale(.2)}
  #__ring.go{animation:__rg .5s ease-out}
  @keyframes __rg{0%{opacity:.95;transform:translate(-50%,-50%) scale(.2)}100%{opacity:0;transform:translate(-50%,-50%) scale(3)}}
  #__cap{position:fixed;left:40px;right:40px;bottom:300px;z-index:2147483645;text-align:center;
    font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
    display:flex;flex-wrap:wrap;gap:0 14px;justify-content:center;align-items:baseline;pointer-events:none}
  #__cap w{display:inline-block;font-size:58px;font-weight:900;letter-spacing:-.02em;color:#fff;
    line-height:1.24;-webkit-text-stroke:9px #05070d;paint-order:stroke fill;
    text-shadow:0 6px 18px rgba(0,0,0,.85);
    opacity:0;transform:translateY(16px) scale(.82);
    animation:__pop .26s cubic-bezier(.2,1.7,.4,1) forwards}
  #__cap w.hot{color:#38bdf8}
  #__cap w.out{animation:__out .18s ease forwards}
  @keyframes __pop{to{opacity:1;transform:none}}
  @keyframes __out{to{opacity:0;transform:translateY(-10px) scale(.94)}}`;
  document.head.appendChild(css);
  const cur = document.createElement('div'); cur.id='__cur';
  cur.innerHTML = `<svg viewBox="0 0 24 24" fill="#fff" stroke="#0b1020" stroke-width="1.5"><path d="M5 2l14 10-6 1.2 3.2 6.4-2.6 1.3L10.4 14 5 18z"/></svg>`;
  const ring = document.createElement('div'); ring.id='__ring';
  const cap  = document.createElement('div'); cap.id='__cap'; cap.innerHTML='<span></span>';
  document.documentElement.append(cur, ring, cap);
  addEventListener('mousemove', e => { cur.style.transform = `translate(${e.clientX-4}px,${e.clientY-3}px)`; }, true);
  addEventListener('mousedown', e => {
    ring.style.left=e.clientX+'px'; ring.style.top=e.clientY+'px';
    ring.classList.remove('go'); void ring.offsetWidth; ring.classList.add('go');
    cur.style.transform = `translate(${e.clientX-4}px,${e.clientY-3}px) scale(.8)`;
  }, true);
  addEventListener('mouseup', e => { cur.style.transform = `translate(${e.clientX-4}px,${e.clientY-3}px)`; }, true);
  // Sous-titre façon CapCut : les mots apparaissent un par un.
  // Un mot entouré de *étoiles* est mis en avant en bleu.
  window.__cap = t => {
    const c=document.getElementById('__cap'); if(!c) return;
    const old=[...c.children];
    old.forEach((w,i)=>{ w.classList.add('out'); setTimeout(()=>w.remove(), 200+i*8); });
    if(!t) return;
    setTimeout(()=>{
      c.innerHTML='';
      // On isole les segments *mis en avant*, puis on découpe en mots.
      // La ponctuation qui suit un segment coloré est recollée au mot précédent.
      const mots=[];
      t.split(/(\*[^*]+\*)/g).filter(Boolean).forEach(seg=>{
        const hot = seg.startsWith('*') && seg.endsWith('*');
        const txt = hot ? seg.slice(1,-1) : seg;
        txt.split(/\s+/).filter(Boolean).forEach((w,j)=>{
          if(!hot && j===0 && /^[,.!?…:;]/.test(w) && mots.length){
            mots[mots.length-1].w += w;          // « catégorie » + « , »
            return;
          }
          mots.push({w, hot});
        });
      });
      mots.forEach((m,i)=>{
        const el=document.createElement('w');
        el.textContent=m.w;
        if(m.hot) el.classList.add('hot');
        el.style.animationDelay=(i*0.085)+'s';
        c.appendChild(el);
      });
    }, 120);
  };
 };
 // addInitScript s'exécute avant le <head> : on attend que le DOM existe
 if (document.head && document.documentElement) build();
 else document.addEventListener('DOMContentLoaded', build, {once:true});
};

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  fs.rmSync(OUT,{recursive:true,force:true}); fs.mkdirSync(OUT,{recursive:true});
  const browser = await chromium.launch({args:['--no-sandbox','--no-proxy-server','--disable-lcd-text']});
  const ctx = await browser.newContext({
    viewport:{width:VW,height:VH}, deviceScaleFactor:1,
    // la taille d'enregistrement DOIT égaler la fenêtre, sinon la page est
    // rendue dans un coin et le reste du cadre reste gris. On agrandit ensuite avec ffmpeg.
    recordVideo:{dir:OUT, size:{width:VW, height:VH}},
  });
  const errs=[]; ctx.on('weberror',e=>errs.push(e.error().message));
  await ctx.addInitScript(OVERLAY);
  // La page est calculée en 600 px de large (mise en page mobile, donc lisible sur
  // téléphone) puis agrandie pour remplir un cadre 1080x1920 rendu nativement :
  // le texte reste net, sans agrandissement de la vidéo.
  await ctx.addInitScript(({w,h,scale})=>{
    const apply=()=>{
      const st=document.createElement('style');
      st.textContent=`
        html{background:#080b16;overflow:hidden}
        body{width:${w}px !important;height:${h}px !important;
             transform:scale(${scale});transform-origin:top left;overflow-y:auto}
        /* mise en page mobile forcée quelle que soit la largeur réelle */
        .side{transform:translateX(-100%);box-shadow:0 0 40px rgba(0,0,0,.6)}
        .side.open{transform:none}
        .main{margin-left:0}
        .burger{display:flex}
        .content{padding:18px 14px 90px}
        .top{padding:12px 14px}
        .savebar{left:14px;right:14px}
        .two{grid-template-columns:1fr}
        .row{flex-direction:column;align-items:flex-start;gap:10px}
        .row-c{width:100%}
        .w-md{max-width:none}
        .hero{padding:22px}
        .hero h2{font-size:21px}
        .grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
        .tk-grid,.grid2{grid-template-columns:1fr}`;
      document.head.appendChild(st);
    };
    if(document.head) apply(); else document.addEventListener('DOMContentLoaded',apply,{once:true});
  }, {w:CSSW, h:Math.round(VH/(VW/CSSW)), scale:VW/CSSW});
  await ctx.addInitScript(()=>{ try{
    sessionStorage.setItem('mb_discord_token',JSON.stringify({t:'demo-token-abcdefghijklmnop',exp:Date.now()+36e5}));
    localStorage.clear();
  }catch{} });

  await ctx.route('**', route => {
    const req=route.request(), url=new URL(req.url());
    if(url.hostname==='discord.com' && url.pathname.startsWith('/api'))
      return route.fulfill({status:200,contentType:'application/json',headers:CORS,
        body:JSON.stringify(url.pathname.includes('/guilds')?GUILDS:USER)});
    if(url.hostname==='cdn.discordapp.com')
      return route.fulfill({status:200,contentType:'image/png',headers:CORS,body:fs.readFileSync(DIR+'/promo/guild-icon.png')});
    if(url.origin===ORIGIN){
      if(/\/api\/guild\/.*\/dashboard/.test(url.pathname)){
        if(req.method()==='POST') return route.fulfill({status:200,contentType:'application/json',body:'{"ok":true}'});
        return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
          guild:{id:GUILD,name:GUILDS[0].name,members:60,online:11},
          channels:CHANNELS, categories:CATEGORIES, roles:ROLES,
          log_types:[{key:'msg',label:'Logs messages',emoji:'📨'},{key:'ticket',label:'Logs ticket',emoji:'🎫'},
                     {key:'flux',label:'Logs Flux',emoji:'📡'},{key:'mod',label:'Logs mods',emoji:'🛡️'}],
          config:CONFIG})});
      }
      if(/\/stats/.test(url.pathname))
        return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({members:60,online:11,recent:[]})});
      if(url.pathname.startsWith('/api/')) return route.fulfill({status:404,body:'{}'});
      const f=DIR+url.pathname.replace(/^\/promo\//,'/promo/');
      if(fs.existsSync(f)&&fs.statSync(f).isFile()){
        const ext=path.extname(f);
        return route.fulfill({status:200,
          contentType: ext==='.png'?'image/png':'text/html; charset=utf-8',
          body: fs.readFileSync(f)});
      }
      return route.fulfill({status:404,body:'introuvable'});
    }
    if(url.hostname.includes('fonts.googleapis.com')) return route.fulfill({status:200,contentType:'text/css',body:''});
    return route.fulfill({status:200,contentType:'text/plain',body:''});
  });

  const page = await ctx.newPage();
  page.on('console',m=>{ if(m.type()==='error'&&!/Failed to load/.test(m.text())) errs.push(m.text()); });

  const cap = t => page.evaluate(t=>window.__cap&&window.__cap(t), t).catch(()=>{});
  const M = page.mouse;
  let mx=VW/2, my=VH-80;
  async function moveTo(sel,{dx=0,dy=0,steps=26}={}){
    const el=page.locator(sel).first();
    await el.scrollIntoViewIfNeeded().catch(()=>{});
    const b=await el.boundingBox();
    if(!b) throw new Error('introuvable : '+sel);
    const x=b.x+b.width/2+dx, y=b.y+b.height/2+dy;   // boundingBox est déjà en pixels écran
    await M.move(x,y,{steps}); mx=x; my=y; return {x,y};
  }
  async function clickAt(sel,opt={}){ await moveTo(sel,opt); await sleep(180); await M.down(); await sleep(90); await M.up(); }

  /* ─────────── 1. LISTE DES SERVEURS ─────────── */
  await page.goto(ORIGIN+'/servers.html',{waitUntil:'domcontentloaded'});
  await page.waitForSelector('.srv',{timeout:8000});
  await sleep(400);
  await cap('Tu te connectes *avec Discord*');
  await sleep(1400);
  await cap('Tu choisis *ton serveur*');
  await clickAt('.srv.clickable');
  await sleep(700);

  /* ─────────── 2. DASHBOARD ─────────── */
  await page.waitForURL(/dash\.html/,{timeout:8000});
  await page.waitForSelector('#app:not(.hidden)',{timeout:9000});
  await sleep(600);
  await cap('Et là tu vois *tout* ton serveur');
  await sleep(1900);

  /* ─────────── 3. MENU → TICKETS ─────────── */
  await clickAt('#burger');
  await sleep(700);
  await cap('Tout est là. *Zéro commande.*');
  await clickAt('.nav[data-p="tickets"]');
  await sleep(900);

  /* ─────────── 4. CONFIG DU PANNEAU ─────────── */
  await cap('Les tickets ? *Tu cliques.*');
  await clickAt('[data-k="tickets.panel.titre"]');
  await page.keyboard.type('Support ModeraBot',{delay:55});
  await sleep(500);

  await clickAt('#tkAdd');
  await sleep(700);
  await cap('Le salon, la *catégorie*, les rôles staff');

  await clickAt('[data-k="tickets.choix.0.nom"]');
  await page.keyboard.press('Control+A'); await page.keyboard.type('Support',{delay:60});
  await sleep(400);

  // catégorie : vrai <select>, vrai clic, vraie sélection
  await moveTo('[data-sk="tickets.choix.0.categorie"] select'); await sleep(200);
  await M.down(); await sleep(90); await M.up();
  await page.selectOption('[data-sk="tickets.choix.0.categorie"] select','201');
  await sleep(600);

  await moveTo('[data-roles="tickets.choix.0.roles"] select'); await sleep(200);
  await M.down(); await sleep(90); await M.up();
  await page.selectOption('[data-roles="tickets.choix.0.roles"] select','302');
  await sleep(700);

  await cap("Tu actives *l'IA* qui répond toute seule");
  await clickAt('[data-k="tickets.choix.0.ia_enabled"] + i');
  await sleep(700);

  /* ─────────── 5. ENREGISTRER ─────────── */
  await cap("Tu enregistres. *C'est envoye au bot.*".replace("envoye","envoyé"));
  await clickAt('#btnSave');
  await sleep(1500);

  /* ─────────── 6. DISCORD ─────────── */
  await page.goto(ORIGIN+'/promo/discord.html',{waitUntil:'domcontentloaded'});
  await sleep(500);
  await cap('Et sur Discord... *le panneau est là*');
  await page.evaluate(()=>document.getElementById('panel').classList.add('in'));
  await sleep(1400);
  await clickAt('#btnSupport');
  await page.evaluate(()=>document.getElementById('btnSupport').classList.add('press'));
  await sleep(160);
  await page.evaluate(()=>document.getElementById('btnSupport').classList.remove('press'));
  await sleep(400);
  await cap('Un clic → le ticket se crée *tout seul*');
  await page.evaluate(()=>document.getElementById('chNew').classList.add('in'));
  await sleep(700);
  await page.evaluate(()=>document.getElementById('created').classList.add('in'));
  await sleep(2200);

  /* ─────────── 7. FIN ─────────── */
  await page.goto(ORIGIN+'/promo/end.html',{waitUntil:'domcontentloaded'});
  await sleep(2600);

  console.log(errs.length?'ERREURS: '+errs.join(' | '):'aucune erreur JS');
  await ctx.close(); await browser.close();
  const f=fs.readdirSync(OUT).find(x=>x.endsWith('.webm'));
  console.log('webm :', f, (fs.statSync(path.join(OUT,f)).size/1048576).toFixed(1)+' Mo');
})();
