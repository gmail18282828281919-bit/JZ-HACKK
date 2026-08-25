/* Enregistre une démo du VRAI dashboard : vrais écrans, vraie souris, vrais clics.
   L'API du bot est simulée avec les vrais salons et rôles du serveur. */
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs'), path = require('path');

const DIR    = '/home/user/JZ-HACKK';
const OUT    = '/tmp/claude-0/-home-user-JZ-HACKK/94986eff-3085-57c3-be49-20a04d5308df/scratchpad/rec2';
const ORIGIN = 'https://dashboard.moderabot.xyz';
const GUILD  = '1539309331386867742';
const VW = 630, VH = 1120;              // fenêtre 9:16 — plus étroite = texte plus gros une fois agrandi

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
  #__cap{position:fixed;left:16px;right:16px;bottom:34px;z-index:2147483645;text-align:center;
    font-family:system-ui,sans-serif;font-size:24px;font-weight:800;color:#fff;
    opacity:0;transform:translateY(12px);transition:.35s}
  #__cap.on{opacity:1;transform:none}
  #__cap span{display:inline-block;background:rgba(8,11,22,.9);border:2px solid #2e3f68;
    padding:13px 24px;border-radius:18px;backdrop-filter:blur(8px)}`;
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
  window.__cap = t => { const c=document.getElementById('__cap');
    if(!c) return;
    if(!t){c.classList.remove('on');return;} c.querySelector('span').textContent=t; c.classList.add('on'); };
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
    const x=b.x+b.width/2+dx, y=b.y+b.height/2+dy;
    await M.move(x,y,{steps}); mx=x; my=y; return {x,y};
  }
  async function clickAt(sel,opt={}){ await moveTo(sel,opt); await sleep(180); await M.down(); await sleep(90); await M.up(); }

  /* ─────────── 1. LISTE DES SERVEURS ─────────── */
  await page.goto(ORIGIN+'/servers.html',{waitUntil:'domcontentloaded'});
  await page.waitForSelector('.srv',{timeout:8000});
  await sleep(400);
  await cap('Tu te connectes avec Discord');
  await sleep(1400);
  await cap('Tu choisis ton serveur');
  await clickAt('.srv.clickable');
  await sleep(700);

  /* ─────────── 2. DASHBOARD ─────────── */
  await page.waitForURL(/dash\.html/,{timeout:8000});
  await page.waitForSelector('#app:not(.hidden)',{timeout:9000});
  await sleep(600);
  await cap('Ton serveur, en un écran');
  await sleep(1900);

  /* ─────────── 3. MENU → TICKETS ─────────── */
  await clickAt('#burger');
  await sleep(700);
  await cap('Tout se règle au clic');
  await clickAt('.nav[data-p="tickets"]');
  await sleep(900);

  /* ─────────── 4. CONFIG DU PANNEAU ─────────── */
  await cap('Le panneau de tickets');
  await clickAt('[data-k="tickets.panel.titre"]');
  await page.keyboard.type('Support ModeraBot',{delay:55});
  await sleep(500);

  await clickAt('#tkAdd');
  await sleep(700);
  await cap('Un type de ticket, en 4 champs');

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

  await cap('Réponse automatique par IA');
  await clickAt('[data-k="tickets.choix.0.ia_enabled"] + i');
  await sleep(700);

  /* ─────────── 5. ENREGISTRER ─────────── */
  await cap('Un clic, et le bot est réglé');
  await clickAt('#btnSave');
  await sleep(1500);

  /* ─────────── 6. DISCORD ─────────── */
  await page.goto(ORIGIN+'/promo/discord.html',{waitUntil:'domcontentloaded'});
  await sleep(500);
  await cap('Le panneau arrive sur Discord');
  await page.evaluate(()=>document.getElementById('panel').classList.add('in'));
  await sleep(1400);
  await clickAt('#btnSupport');
  await page.evaluate(()=>document.getElementById('btnSupport').classList.add('press'));
  await sleep(160);
  await page.evaluate(()=>document.getElementById('btnSupport').classList.remove('press'));
  await sleep(400);
  await cap('Le ticket se crée tout seul');
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
