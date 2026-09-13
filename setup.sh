set -e
cat > index.html << 'PTEOF_index_html'
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PronosticiTop — Pronostici Calcio con Analisi Statistica Reale</title>
<meta name="description" content="Schedine di pronostici calcio ogni weekend, basate su analisi statistica reale (forma, gol fatti/subiti, classifica, infortuni). 4 livelli di rischio, probabilità e quota indicate per ogni evento.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://www.pronosticitop.it/">
<meta property="og:title" content="PronosticiTop — Pronostici Calcio con Analisi Statistica">
<meta property="og:description" content="Schedine settimanali di pronostici calcio basate su statistiche reali: forma, gol fatti/subiti, classifica. Aggiornate ogni weekend.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://www.pronosticitop.it/">
<style>
  :root{
    --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --border:#2a2f3a;
    --text:#e8eaed; --muted:#9aa3b2; --accent:#3b82f6; --green:#22c55e;
    --red:#ef4444; --amber:#f59e0b; --radius:12px;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.5}
  a{color:#7ab3ff}
  header{position:sticky;top:0;z-index:10;background:rgba(15,17,21,.95);backdrop-filter:blur(6px);border-bottom:1px solid var(--border)}
  .wrap{max-width:960px;margin:0 auto;padding:0 16px}
  .headrow{display:flex;align-items:center;justify-content:space-between;padding:14px 0;gap:12px;flex-wrap:wrap}
  .brand{font-weight:800;font-size:19px;display:flex;align-items:center;gap:8px}
  .brand a{color:var(--text);text-decoration:none}
  nav a{color:var(--muted);text-decoration:none;font-size:14px;margin-left:16px}
  nav a:hover{color:var(--text)}
  .hero{padding:36px 0 20px;text-align:center}
  .hero h1{font-size:28px;margin:0 0 10px}
  .hero p{color:var(--muted);font-size:15px;max-width:640px;margin:0 auto}
  main{max-width:960px;margin:0 auto;padding:0 16px 60px}
  .subtitle{color:var(--muted);font-size:14px;margin-bottom:20px;text-align:center}
  select{background:var(--panel2);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:8px 10px;font-size:14px}
  .selectrow{text-align:center;margin-bottom:22px}
  .banner{background:var(--panel2);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;margin-bottom:20px;font-size:14px;color:var(--muted)}
  .ad-slot{background:var(--panel2);border:1px dashed var(--border);border-radius:var(--radius);padding:18px;margin:22px 0;text-align:center;color:var(--muted);font-size:13px}
  .risk-group{margin-bottom:28px}
  .risk-title{display:flex;align-items:center;gap:10px;margin:22px 0 12px}
  .risk-title h2{font-size:16px;margin:0}
  .risk-pill{font-size:12px;padding:3px 9px;border-radius:20px;border:1px solid var(--border);color:var(--muted)}
  .cards{display:grid;gap:14px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:16px}
  .card-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:10px;flex-wrap:wrap}
  .card-head .name{font-weight:600;font-size:14px}
  .prob{font-size:13px;padding:4px 10px;border-radius:20px;background:rgba(59,130,246,.15);color:#7ab3ff;font-weight:600;white-space:nowrap}
  .status-pill{font-size:12px;padding:3px 10px;border-radius:20px;font-weight:600}
  .status-pending{background:rgba(245,158,11,.15);color:var(--amber)}
  .status-win{background:rgba(34,197,94,.15);color:var(--green)}
  .status-lose{background:rgba(239,68,68,.15);color:var(--red)}
  table.events{width:100%;border-collapse:collapse;font-size:13px}
  table.events td{padding:7px 4px;border-top:1px solid var(--border);vertical-align:top}
  table.events tr:first-child td{border-top:none}
  .ev-match{font-weight:500}
  .ev-league{color:var(--muted);font-size:11px}
  .ev-pick{color:#7ab3ff;font-weight:600;white-space:nowrap}
  .ev-p{color:var(--muted);white-space:nowrap;text-align:right}
  .ev-res{text-align:right;white-space:nowrap}
  .empty{color:var(--muted);padding:30px 0;text-align:center;font-size:14px}
  .stats-table{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}
  .stats-table th,.stats-table td{padding:8px;border-bottom:1px solid var(--border);text-align:left}
  .stats-table th{color:var(--muted);font-weight:500;font-size:12px}
  details{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);margin-top:30px}
  summary{padding:14px 16px;cursor:pointer;font-weight:600;font-size:14px;list-style:none}
  summary::-webkit-details-marker{display:none}
  details[open] summary{border-bottom:1px solid var(--border)}
  .details-body{padding:16px;font-size:14px;color:var(--muted)}
  .disclaimer{color:var(--muted);font-size:12px;margin-top:30px;border-top:1px solid var(--border);padding-top:16px}
  .disclaimer b{color:var(--text)}
  footer{border-top:1px solid var(--border);margin-top:40px;padding:24px 0;text-align:center;font-size:13px;color:var(--muted)}
  footer a{margin:0 8px}
  .badge18{display:inline-block;border:1px solid var(--border);border-radius:6px;padding:2px 6px;font-size:11px;color:var(--muted);margin-left:6px}
</style>
</head>
<body>
<header>
  <div class="wrap headrow">
    <div class="brand"><a href="/">⚽ PronosticiTop</a></div>
    <nav>
      <a href="/chi-siamo.html">Metodo</a>
      <a href="/termini.html">Termini</a>
      <a href="/privacy.html">Privacy</a>
    </nav>
  </div>
</header>

<div class="hero">
  <div class="wrap">
    <h1>Pronostici calcio con analisi statistica reale <span class="badge18">18+</span></h1>
    <p>Ogni weekend pubblichiamo 16 schedine su 4 livelli di rischio, basate su forma, gol fatti/subiti, classifica e infortuni reali — non solo sulle quote di mercato. Probabilità e confidenza dei dati indicate per ogni evento.</p>
  </div>
</div>

<main>
  <div class="ad-slot" id="ad-top">Spazio pubblicitario</div>

  <div class="selectrow">
    <select id="weekSelect"></select>
  </div>

  <div id="banner" class="banner" style="display:none"></div>

  <div id="content"></div>

  <div class="ad-slot" id="ad-mid">Spazio pubblicitario</div>

  <details id="storicoBox">
    <summary>📊 Storico &amp; percentuale di successo</summary>
    <div class="details-body" id="storicoBody">Caricamento…</div>
  </details>

  <details>
    <summary>ℹ️ Come funzionano i nostri pronostici</summary>
    <div class="details-body">
      <p>Ogni pronostico parte da un'analisi statistica reale della squadra: gol fatti e subiti, forma recente, precedenti scontri diretti, assenze/infortuni e classifica — non solo dalla quota di mercato. Usiamo mercati diversi (1X2, doppia chance, Under/Over, Gol/No Gol) scegliendo quello più supportato dai dati per ciascuna partita.</p>
      <p>Ogni evento riporta una probabilità stimata e un livello di confidenza dei dati (ALTA/MEDIA/BASSA): i pick a bassa confidenza vanno presi con più cautela. Trovi il dettaglio completo nella pagina <a href="/chi-siamo.html">Il nostro metodo</a>.</p>
    </div>
  </details>

  <div class="disclaimer">
    <b>Attenzione:</b> i contenuti di questo sito hanno finalità puramente informative e statistiche. Le probabilità indicate sono stime basate su analisi di forma, classifica e statistiche di gioco: <b>non costituiscono consigli di scommessa</b> e non garantiscono alcun risultato. Il gioco è vietato ai minori di 18 anni e può causare dipendenza patologica — gioca responsabilmente. Per informazioni e supporto: <a href="https://www.giocaresponsabile.gov.it" target="_blank" rel="noopener">giocaresponsabile.gov.it</a>. Consulta anche i nostri <a href="/termini.html">Termini di utilizzo</a>.
  </div>
</main>

<footer>
  <div><a href="/chi-siamo.html">Il nostro metodo</a> · <a href="/termini.html">Termini</a> · <a href="/privacy.html">Privacy</a> · <a href="/cookie-policy.html">Cookie</a></div>
  <div style="margin-top:8px">© <span id="year"></span> PronosticiTop — gioca responsabilmente, vietato ai minori di 18 anni</div>
</footer>

<script src="/cookie-banner.js"></script>
<script>
document.getElementById('year').textContent = new Date().getFullYear();

const MARKET_LABELS = { '1X2':'Esito finale', 'OU25':'Under/Over 2.5', 'GGNG':'Gol/No Gol', 'DC':'Doppia chance' };
const STATUS_LABELS = { pending:'In attesa', win:'Vinto', lose:'Perso' };

function fmtPct(x){ return Math.round(x*100) + '%'; }
function fmtDate(iso){
  try{
    const d = new Date(iso);
    const opts = { timeZone: 'Europe/Rome' };
    return d.toLocaleDateString('it-IT',{...opts,weekday:'short',day:'2-digit',month:'2-digit'}) + ' ' + d.toLocaleTimeString('it-IT',{...opts,hour:'2-digit',minute:'2-digit'});
  }
  catch(e){ return iso; }
}

function eventStatus(ev){ return ev.esito === 'vinto' ? 'win' : ev.esito === 'perso' ? 'lose' : 'pending'; }
function schedinaStatus(sch){
  if(sch.eventi.some(e=>eventStatus(e)==='lose')) return 'lose';
  if(sch.eventi.every(e=>eventStatus(e)==='win')) return 'win';
  return 'pending';
}

function renderWeek(week){
  const banner = document.getElementById('banner');
  if(week.stato === 'generazione_in_corso' || !week.schedine || !week.schedine.length){
    banner.style.display = 'block';
    banner.textContent = 'Le schedine per questo turno sono in fase di analisi e verranno pubblicate a breve.';
  } else {
    banner.style.display = 'none';
  }

  const byLevel = {};
  (week.schedine||[]).forEach(s => { (byLevel[s.livello_rischio] = byLevel[s.livello_rischio] || []).push(s); });

  const content = document.getElementById('content');
  content.innerHTML = '';

  const levels = Object.keys(byLevel).map(Number).sort((a,b)=>a-b);
  if(!levels.length){
    content.innerHTML = '<div class="empty">Nessuna schedina disponibile per questo turno.</div>';
    return;
  }

  levels.forEach(level => {
    const group = document.createElement('div');
    group.className = 'risk-group';
    const label = level<=4 ? 'Rischio basso' : level===5 ? 'Rischio medio-basso' : level===6 ? 'Rischio medio-alto' : 'Rischio alto';
    group.innerHTML = `<div class="risk-title"><h2>${level} eventi</h2><span class="risk-pill">${label}</span></div>`;

    const cards = document.createElement('div');
    cards.className = 'cards';

    byLevel[level].forEach((sch, idx) => {
      const st = schedinaStatus(sch);
      const card = document.createElement('div');
      card.className = 'card';
      let rows = sch.eventi.map(ev => {
        const es = eventStatus(ev);
        const resTxt = es==='pending' ? '⏳' : (es==='win' ? '✅' : '❌') + (ev.risultato_reale ? ' ' + ev.risultato_reale : '');
        return `<tr>
          <td>
            <div class="ev-match">${ev.partita}</div>
            <div class="ev-league">${ev.campionato} — ${fmtDate(ev.data)}</div>
          </td>
          <td class="ev-pick">${ev.pronostico}<br><span class="ev-league">${MARKET_LABELS[ev.mercato]||ev.mercato}</span></td>
          <td class="ev-p">${fmtPct(ev.probabilita_stimata)}${ev.quota_stimata ? '<br><span class="ev-league">@'+ev.quota_stimata.toFixed(2)+'</span>' : ''}${ev.confidenza_dati ? '<br><span class="ev-league">dati: '+ev.confidenza_dati+'</span>' : ''}</td>
          <td class="ev-res">${resTxt}</td>
        </tr>`;
      }).join('');

      const quotaTxt = sch.quota_combinata ? `<span class="prob" style="background:rgba(245,158,11,.15);color:var(--amber)">Quota ${sch.quota_combinata.toFixed(2)}</span>` : '';
      card.innerHTML = `
        <div class="card-head">
          <span class="name">Schedina ${level}E — #${idx+1}</span>
          ${quotaTxt}
          <span class="prob">Prob. combinata ${fmtPct(sch.probabilita_combinata)}</span>
          <span class="status-pill status-${st}">${STATUS_LABELS[st]}</span>
        </div>
        <table class="events">${rows}</table>`;
      cards.appendChild(card);
    });

    group.appendChild(cards);
    content.appendChild(group);
  });
}

async function renderStorico(weeks){
  const body = document.getElementById('storicoBody');
  const completed = weeks.filter(w => w.stato === 'completata' || w.stato === 'pubblicata');
  if(!completed.length){ body.innerHTML = '<div class="empty">Nessun dato storico ancora disponibile.</div>'; return; }

  const perLevel = {};
  let totWin=0, totLose=0, totPending=0;

  for(const w of completed){
    try{
      const data = await fetch('/data/' + w.file).then(r=>r.json());
      (data.schedine||[]).forEach(sch => {
        const st = schedinaStatus(sch);
        const lvl = sch.livello_rischio;
        perLevel[lvl] = perLevel[lvl] || {win:0,lose:0,pending:0};
        perLevel[lvl][st]++;
        if(st==='win') totWin++; else if(st==='lose') totLose++; else totPending++;
      });
    } catch(e){ /* file non ancora presente, ignora */ }
  }

  const decided = totWin + totLose;
  const rateGlobal = decided ? Math.round(totWin/decided*100) : null;

  let rows = Object.keys(perLevel).map(Number).sort((a,b)=>a-b).map(lvl=>{
    const d = perLevel[lvl];
    const dec = d.win + d.lose;
    const rate = dec ? Math.round(d.win/dec*100)+'%' : '—';
    return `<tr><td>${lvl} eventi</td><td>${d.win}</td><td>${d.lose}</td><td>${d.pending}</td><td>${rate}</td></tr>`;
  }).join('');

  body.innerHTML = `
    <p style="margin-top:0">
      Su ${completed.length} turni tracciati: <b style="color:var(--text)">${totWin} vinte</b>, ${totLose} perse, ${totPending} in attesa
      ${rateGlobal!==null ? ' — tasso di successo complessivo <b style="color:var(--text)">'+rateGlobal+'%</b>' : ''}.
    </p>
    <table class="stats-table">
      <thead><tr><th>Livello</th><th>Vinte</th><th>Perse</th><th>In attesa</th><th>% successo</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function init(){
  const idx = await fetch('/data/settimane.json').then(r=>r.json()).catch(()=>({settimane:[]}));
  const weeks = idx.settimane || [];
  const select = document.getElementById('weekSelect');

  if(!weeks.length){
    document.getElementById('content').innerHTML = '<div class="empty">Non ci sono ancora schedine pubblicate.</div>';
    document.getElementById('storicoBody').innerHTML = '<div class="empty">Nessun dato storico ancora disponibile.</div>';
    select.style.display = 'none';
    return;
  }

  weeks.forEach(w => {
    const opt = document.createElement('option');
    opt.value = w.file; opt.textContent = w.titolo;
    select.appendChild(opt);
  });

  async function loadWeek(file){
    const data = await fetch('/data/' + file).then(r=>r.json());
    renderWeek(data);
  }

  select.addEventListener('change', () => loadWeek(select.value));
  await loadWeek(weeks[0].file);
  renderStorico(weeks);
}

init();
</script>
</body>
</html>
PTEOF_index_html
cat > chi-siamo.html << 'PTEOF_chi_siamo_html'
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Il Nostro Metodo — PronosticiTop</title>
<meta name="description" content="Come costruiamo i pronostici calcio di PronosticiTop: analisi statistica reale, livelli di rischio, mercati usati e livello di confidenza dei dati.">
<meta name="robots" content="index, follow">
<style>
  :root{--bg:#0f1115;--panel:#171a21;--border:#2a2f3a;--text:#e8eaed;--muted:#9aa3b2}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.6}
  a{color:#7ab3ff}
  header{border-bottom:1px solid var(--border)}
  .wrap{max-width:760px;margin:0 auto;padding:16px}
  .brand{font-weight:800;font-size:19px}
  .brand a{color:var(--text);text-decoration:none}
  main{max-width:760px;margin:0 auto;padding:20px 16px 60px}
  h1{font-size:26px}
  h2{font-size:18px;margin-top:32px}
  p,li{color:#c7cbd4;font-size:15px}
  .box{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin:16px 0}
  table{width:100%;border-collapse:collapse;font-size:14px;margin:12px 0}
  th,td{border:1px solid var(--border);padding:8px;text-align:left}
  th{background:var(--panel);color:var(--muted);font-weight:500}
  footer{border-top:1px solid var(--border);margin-top:40px;padding:24px 16px;text-align:center;font-size:13px;color:var(--muted)}
</style>
</head>
<body>
<header><div class="wrap brand"><a href="/">⚽ PronosticiTop</a></div></header>
<main>
  <h1>Il nostro metodo</h1>
  <p>PronosticiTop pubblica ogni weekend 16 schedine di pronostici calcio, organizzate su 4 livelli di rischio crescente (4, 5, 6 e 7 eventi per schedina). Ogni pronostico nasce da un'analisi statistica delle squadre coinvolte, non da un semplice copia-incolla delle quote dei bookmaker.</p>

  <h2>Cosa analizziamo</h2>
  <ul>
    <li><strong>Forma recente e streak</strong>: risultati delle ultime partite, non solo la posizione in classifica</li>
    <li><strong>Statistiche sui gol</strong>: gol fatti e subiti, in generale e in casa/trasferta</li>
    <li><strong>Precedenti scontri diretti</strong> tra le due squadre</li>
    <li><strong>Assenze e infortuni</strong> dei giocatori chiave</li>
    <li><strong>Quote di mercato</strong>, usate come riscontro aggiuntivo e non come unica base del pronostico</li>
  </ul>

  <h2>Mercati utilizzati</h2>
  <p>Scegliamo il mercato più supportato dai dati per ciascuna partita, invece di usare sempre lo stesso: esito finale (1X2), doppia chance, Under/Over gol, Gol/No Gol (BTTS), e talvolta combinazioni tra questi mercati sulla stessa partita.</p>

  <h2>Livelli di rischio</h2>
  <table>
    <tr><th>Livello</th><th>N. eventi</th><th>Caratteristica</th></tr>
    <tr><td>Basso</td><td>4</td><td>Solo pick con probabilità stimata molto alta (70%+ per singolo evento)</td></tr>
    <tr><td>Medio-basso</td><td>5</td><td>Probabilità minima 65% per singolo evento</td></tr>
    <tr><td>Medio-alto</td><td>6</td><td>Più eventi, quota complessiva più alta</td></tr>
    <tr><td>Alto</td><td>7</td><td>Massimo numero di eventi e quota potenziale più alta</td></tr>
  </table>

  <h2>Confidenza dei dati</h2>
  <p>Ogni evento riporta un'etichetta di confidenza (ALTA / MEDIA-ALTA / MEDIA / MEDIA-BASSA / BASSA) che indica quanto sono solide le fonti usate per quel pronostico specifico. Un'etichetta BASSA significa che i dati disponibili erano limitati: va presa con più cautela.</p>

  <h2>Tracciamento dei risultati</h2>
  <p>Ogni settimana verifichiamo l'esito reale delle partite della settimana precedente e aggiorniamo lo storico, visibile in homepage, con il tasso di successo reale per livello di rischio — nel bene e nel male.</p>

  <div class="box">
    <strong>Ricorda:</strong> nessuna analisi statistica, per quanto accurata, può prevedere con certezza il risultato di un evento sportivo. Consulta i nostri <a href="/termini.html">Termini di utilizzo</a>.
  </div>
</main>
<footer>
  <a href="/">Home</a> · <a href="/termini.html">Termini</a> · <a href="/privacy.html">Privacy</a> · <a href="/cookie-policy.html">Cookie</a>
</footer>
</body>
</html>
PTEOF_chi_siamo_html
cat > termini.html << 'PTEOF_termini_html'
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Termini di Utilizzo — PronosticiTop</title>
<meta name="robots" content="index, follow">
<style>
  :root{--bg:#0f1115;--panel:#171a21;--border:#2a2f3a;--text:#e8eaed;--muted:#9aa3b2}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.6}
  a{color:#7ab3ff}
  header{border-bottom:1px solid var(--border)}
  .wrap{max-width:760px;margin:0 auto;padding:16px}
  .brand{font-weight:800;font-size:19px}
  .brand a{color:var(--text);text-decoration:none}
  main{max-width:760px;margin:0 auto;padding:20px 16px 60px}
  h1{font-size:26px}
  h2{font-size:18px;margin-top:32px}
  p,li{color:#c7cbd4;font-size:15px}
  .box{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin:20px 0}
  footer{border-top:1px solid var(--border);margin-top:40px;padding:24px 16px;text-align:center;font-size:13px;color:var(--muted)}
</style>
</head>
<body>
<header><div class="wrap brand"><a href="/">⚽ PronosticiTop</a></div></header>
<main>
  <h1>Termini di Utilizzo</h1>
  <p><em>Ultimo aggiornamento: settembre 2026</em></p>

  <div class="box">
    <strong>Il gioco è vietato ai minori di 18 anni. Il gioco può causare dipendenza patologica.</strong>
    Se ritieni di avere un problema con il gioco, contatta il servizio pubblico
    <a href="https://www.giocaresponsabile.gov.it" target="_blank" rel="noopener">giocaresponsabile.gov.it</a>.
  </div>

  <h2>1. Natura del servizio</h2>
  <p>PronosticiTop pubblica contenuti informativi e statistici relativi a eventi calcistici (classifiche, forma delle squadre, statistiche sui gol, ecc.) e stime di probabilità elaborate a partire da tali dati. I contenuti hanno finalità puramente informativa, di intrattenimento e statistica.</p>

  <h2>2. Nessun consiglio di scommessa</h2>
  <p>Nulla di quanto pubblicato su questo sito costituisce un consiglio, una raccomandazione o un invito a scommettere denaro. Le probabilità e le "quote stimate" indicate sono stime statistiche elaborate con metodi di analisi dei dati e ricerca, <strong>non hanno alcuna garanzia di accuratezza</strong> e non devono essere interpretate come previsioni certe di un risultato sportivo. Il risultato di un evento sportivo è per sua natura incerto.</p>

  <h2>3. Nessuna responsabilità per perdite</h2>
  <p>L'utilizzo dei contenuti di questo sito è a esclusivo rischio dell'utente. PronosticiTop e i suoi gestori non si assumono alcuna responsabilità per eventuali perdite economiche o di altro tipo derivanti dall'uso, diretto o indiretto, dei contenuti pubblicati, incluse eventuali scommesse effettuate presso operatori terzi.</p>

  <h2>4. Nessuna affiliazione con operatori di scommesse</h2>
  <p>PronosticiTop non è un operatore di scommesse, non gestisce conti di gioco, non accetta puntate e non è affiliato ad alcun operatore di scommesse regolamentato, salvo quanto diversamente ed esplicitamente indicato.</p>

  <h2>5. Accesso riservato ai maggiorenni</h2>
  <p>L'accesso e l'utilizzo del sito sono consentiti esclusivamente a persone maggiorenni (18+), in conformità con la normativa italiana sul gioco.</p>

  <h2>6. Pubblicità</h2>
  <p>Il sito è finanziato tramite spazi pubblicitari standard (es. Google AdSense). Gli annunci mostrati sono selezionati automaticamente dalla piattaforma pubblicitaria in base a policy proprie; PronosticiTop non seleziona direttamente gli inserzionisti.</p>

  <h2>7. Modifiche ai contenuti</h2>
  <p>I contenuti e i pronostici pubblicati possono essere aggiornati, corretti o rimossi senza preavviso, anche a seguito di nuove informazioni statistiche disponibili.</p>

  <h2>8. Legge applicabile</h2>
  <p>I presenti termini sono regolati dalla legge italiana. Per qualsiasi controversia sarà competente il foro del titolare del sito, salvo diversa disposizione inderogabile di legge a tutela del consumatore.</p>

  <h2>Contatti</h2>
  <p>Per domande su questi termini: <a href="mailto:info@pronosticitop.it">info@pronosticitop.it</a></p>
</main>
<footer>
  <a href="/">Home</a> · <a href="/chi-siamo.html">Il nostro metodo</a> · <a href="/privacy.html">Privacy</a> · <a href="/cookie-policy.html">Cookie</a>
</footer>
</body>
</html>
PTEOF_termini_html
cat > privacy.html << 'PTEOF_privacy_html'
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Privacy Policy — PronosticiTop</title>
<meta name="robots" content="index, follow">
<style>
  :root{--bg:#0f1115;--panel:#171a21;--border:#2a2f3a;--text:#e8eaed;--muted:#9aa3b2}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.6}
  a{color:#7ab3ff}
  header{border-bottom:1px solid var(--border)}
  .wrap{max-width:760px;margin:0 auto;padding:16px}
  .brand{font-weight:800;font-size:19px}
  .brand a{color:var(--text);text-decoration:none}
  main{max-width:760px;margin:0 auto;padding:20px 16px 60px}
  h1{font-size:26px}
  h2{font-size:18px;margin-top:32px}
  p,li{color:#c7cbd4;font-size:15px}
  table{width:100%;border-collapse:collapse;font-size:14px;margin:12px 0}
  th,td{border:1px solid var(--border);padding:8px;text-align:left;vertical-align:top}
  th{background:var(--panel);color:var(--muted);font-weight:500}
  footer{border-top:1px solid var(--border);margin-top:40px;padding:24px 16px;text-align:center;font-size:13px;color:var(--muted)}
</style>
</head>
<body>
<header><div class="wrap brand"><a href="/">⚽ PronosticiTop</a></div></header>
<main>
  <h1>Privacy Policy</h1>
  <p><em>Ultimo aggiornamento: settembre 2026</em></p>

  <h2>Titolare del trattamento</h2>
  <p>Il titolare del trattamento dei dati è il gestore di PronosticiTop, contattabile all'indirizzo <a href="mailto:info@pronosticitop.it">info@pronosticitop.it</a>.</p>

  <h2>Dati raccolti</h2>
  <p>PronosticiTop non richiede registrazione né raccoglie dati personali identificativi per la consultazione dei contenuti. Vengono raccolti solo i dati tecnici generati automaticamente dalla navigazione e dai servizi di terze parti indicati sotto, previo consenso dove richiesto dalla normativa (GDPR — Regolamento UE 2016/679).</p>

  <table>
    <tr><th>Servizio</th><th>Finalità</th><th>Dati trattati</th><th>Base giuridica</th></tr>
    <tr><td>Google Analytics</td><td>Statistiche di utilizzo del sito, in forma aggregata</td><td>Identificativo anonimo, pagine visitate, dispositivo/browser</td><td>Consenso dell'utente (cookie banner)</td></tr>
    <tr><td>Google AdSense</td><td>Visualizzazione di annunci pubblicitari, eventualmente personalizzati</td><td>Identificativi pubblicitari, interazioni con gli annunci</td><td>Consenso dell'utente per la personalizzazione (cookie banner); legittimo interesse per gli annunci non personalizzati</td></tr>
  </table>

  <p>Il trattamento di questi dati è gestito direttamente da Google LLC secondo le proprie informative, consultabili su
  <a href="https://policies.google.com/privacy" target="_blank" rel="noopener">policies.google.com/privacy</a>. Puoi gestire le tue preferenze pubblicitarie Google su
  <a href="https://myadcenter.google.com" target="_blank" rel="noopener">myadcenter.google.com</a>.</p>

  <h2>Cookie</h2>
  <p>Per il dettaglio dei cookie utilizzati consulta la <a href="/cookie-policy.html">Cookie Policy</a>.</p>

  <h2>Diritti dell'utente</h2>
  <p>In quanto interessato, hai diritto di accesso, rettifica, cancellazione, limitazione del trattamento e portabilità dei dati che ti riguardano, oltre al diritto di opposizione e di reclamo all'Autorità Garante per la protezione dei dati personali (<a href="https://www.garanteprivacy.it" target="_blank" rel="noopener">garanteprivacy.it</a>). Per esercitare questi diritti scrivi a <a href="mailto:info@pronosticitop.it">info@pronosticitop.it</a>.</p>

  <h2>Conservazione dei dati</h2>
  <p>I dati tecnici raccolti tramite Google Analytics vengono conservati secondo le impostazioni di conservazione configurate sulla proprietà Analytics del sito, comunque non oltre i termini previsti dalla normativa vigente.</p>

  <h2>Minori</h2>
  <p>Il sito è destinato esclusivamente a un pubblico maggiorenne (18+), coerentemente con la natura dei contenuti pubblicati.</p>
</main>
<footer>
  <a href="/">Home</a> · <a href="/chi-siamo.html">Il nostro metodo</a> · <a href="/termini.html">Termini</a> · <a href="/cookie-policy.html">Cookie</a>
</footer>
</body>
</html>
PTEOF_privacy_html
cat > cookie-policy.html << 'PTEOF_cookie_policy_html'
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cookie Policy — PronosticiTop</title>
<meta name="robots" content="index, follow">
<style>
  :root{--bg:#0f1115;--panel:#171a21;--border:#2a2f3a;--text:#e8eaed;--muted:#9aa3b2}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.6}
  a{color:#7ab3ff}
  header{border-bottom:1px solid var(--border)}
  .wrap{max-width:760px;margin:0 auto;padding:16px}
  .brand{font-weight:800;font-size:19px}
  .brand a{color:var(--text);text-decoration:none}
  main{max-width:760px;margin:0 auto;padding:20px 16px 60px}
  h1{font-size:26px}
  h2{font-size:18px;margin-top:32px}
  p,li{color:#c7cbd4;font-size:15px}
  table{width:100%;border-collapse:collapse;font-size:14px;margin:12px 0}
  th,td{border:1px solid var(--border);padding:8px;text-align:left;vertical-align:top}
  th{background:var(--panel);color:var(--muted);font-weight:500}
  .btnrow{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}
  button{background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:10px 16px;cursor:pointer;font-size:14px}
  footer{border-top:1px solid var(--border);margin-top:40px;padding:24px 16px;text-align:center;font-size:13px;color:var(--muted)}
</style>
</head>
<body>
<header><div class="wrap brand"><a href="/">⚽ PronosticiTop</a></div></header>
<main>
  <h1>Cookie Policy</h1>
  <p><em>Ultimo aggiornamento: settembre 2026</em></p>

  <p>Questo sito utilizza cookie tecnici, analitici e pubblicitari. Puoi modificare le tue preferenze in qualsiasi momento con il pulsante qui sotto.</p>

  <div class="btnrow">
    <button onclick="window.CookieConsent && window.CookieConsent.reset()">Gestisci preferenze cookie</button>
  </div>

  <h2>Cookie tecnici (sempre attivi)</h2>
  <p>Necessari al funzionamento del sito (es. memorizzazione delle preferenze di consenso). Non richiedono consenso.</p>

  <h2>Cookie analitici</h2>
  <table>
    <tr><th>Nome</th><th>Fornitore</th><th>Finalità</th><th>Durata</th></tr>
    <tr><td>_ga, _ga_*</td><td>Google Analytics</td><td>Statistiche di utilizzo aggregate e anonime</td><td>Fino a 13 mesi</td></tr>
  </table>

  <h2>Cookie pubblicitari</h2>
  <table>
    <tr><th>Nome</th><th>Fornitore</th><th>Finalità</th><th>Durata</th></tr>
    <tr><td>__gads, __gpi, IDE, test_cookie</td><td>Google AdSense</td><td>Visualizzazione e, se autorizzata, personalizzazione degli annunci pubblicitari</td><td>Fino a 13 mesi</td></tr>
  </table>

  <p>Questi cookie vengono attivati solo dopo il tuo consenso esplicito tramite il banner cookie. Puoi revocare il consenso in qualsiasi momento tramite il pulsante sopra o le impostazioni del tuo browser.</p>

  <h2>Come disabilitare i cookie dal browser</h2>
  <p>Oltre a gestire le preferenze da questa pagina, puoi bloccare o cancellare i cookie direttamente dalle impostazioni del tuo browser (Chrome, Firefox, Safari, Edge) — consulta la guida del tuo browser per le istruzioni specifiche.</p>
</main>
<footer>
  <a href="/">Home</a> · <a href="/chi-siamo.html">Il nostro metodo</a> · <a href="/termini.html">Termini</a> · <a href="/privacy.html">Privacy</a>
</footer>
<script src="/cookie-banner.js"></script>
</body>
</html>
PTEOF_cookie_policy_html
cat > cookie-banner.js << 'PTEOF_cookie_banner_js'
(function () {
  'use strict';

  var STORAGE_KEY = 'pt_cookie_consent';
  var GA_ID = 'G-XXXXXXXXXX'; // sostituire con l'ID Google Analytics reale quando disponibile

  function getConsent() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
    catch (e) { return {}; }
  }

  function saveConsent(obj) {
    obj.saved = true;
    obj.date = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
  }

  function removeCookiesByPrefix(prefixes) {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      var name = cookies[i].split('=')[0].trim();
      for (var p = 0; p < prefixes.length; p++) {
        if (new RegExp('^' + prefixes[p]).test(name)) {
          var domains = [location.hostname, '.' + location.hostname];
          for (var d = 0; d < domains.length; d++) {
            document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=' + domains[d];
          }
        }
      }
    }
  }

  function gtagDefaultConsent() {
    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    window.gtag = gtag;
    gtag('consent', 'default', {
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      analytics_storage: 'denied'
    });
  }
  gtagDefaultConsent();

  function loadGA() {
    if (document.querySelector('script[src*="googletagmanager.com/gtag"]')) return;
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    document.head.appendChild(s);
    window.gtag('js', new Date());
    window.gtag('config', GA_ID);
  }

  function applyConsent(consent) {
    window.gtag('consent', 'update', {
      ad_storage: consent.pubblicita ? 'granted' : 'denied',
      ad_user_data: consent.pubblicita ? 'granted' : 'denied',
      ad_personalization: consent.pubblicita ? 'granted' : 'denied',
      analytics_storage: consent.analytics ? 'granted' : 'denied'
    });
    if (consent.analytics) { loadGA(); }
    else { removeCookiesByPrefix(['_ga']); }
    if (!consent.pubblicita) { removeCookiesByPrefix(['__gads', '__gpi', 'IDE', 'test_cookie']); }
  }

  window.CookieConsent = {
    get: function () { return getConsent(); },
    hasAnalytics: function () { return !!getConsent().analytics; },
    hasAds: function () { return !!getConsent().pubblicita; },
    reset: function () {
      localStorage.removeItem(STORAGE_KEY);
      var existing = document.getElementById('pt-cookie-banner');
      if (existing) existing.remove();
      injectBanner();
    }
  };

  function injectBanner() {
    if (document.getElementById('pt-cookie-banner')) return;
    var el = document.createElement('div');
    el.id = 'pt-cookie-banner';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', 'Consenso cookie');
    el.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#171a21;color:#e8eaed;border-top:1px solid #2a2f3a;padding:16px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px;box-shadow:0 -4px 16px rgba(0,0,0,.3)';
    el.innerHTML =
      '<div style="max-width:960px;margin:0 auto">' +
      '<p style="margin:0 0 12px">Usiamo cookie tecnici (sempre attivi), di analisi e pubblicitari (Google AdSense) per mostrare annunci pertinenti. Puoi scegliere quali accettare. Leggi la <a href="/cookie-policy.html" style="color:#7ab3ff">Cookie Policy</a>.</p>' +
      '<div style="display:flex;gap:10px;flex-wrap:wrap">' +
      '<button id="pt-accept-all" style="background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:9px 16px;cursor:pointer;font-size:14px">Accetta tutti</button>' +
      '<button id="pt-reject-all" style="background:transparent;color:#e8eaed;border:1px solid #2a2f3a;border-radius:8px;padding:9px 16px;cursor:pointer;font-size:14px">Solo necessari</button>' +
      '<button id="pt-customize" style="background:transparent;color:#9aa3b2;border:none;text-decoration:underline;padding:9px 4px;cursor:pointer;font-size:14px">Personalizza</button>' +
      '</div></div>';
    document.body.appendChild(el);

    document.getElementById('pt-accept-all').addEventListener('click', function () {
      var c = { necessari: true, analytics: true, pubblicita: true };
      saveConsent(c); applyConsent(c); el.remove();
    });
    document.getElementById('pt-reject-all').addEventListener('click', function () {
      var c = { necessari: true, analytics: false, pubblicita: false };
      saveConsent(c); applyConsent(c); el.remove();
    });
    document.getElementById('pt-customize').addEventListener('click', function () {
      window.location.href = '/cookie-policy.html';
    });
  }

  var existing = getConsent();
  if (existing.saved) {
    applyConsent(existing);
  } else {
    document.addEventListener('DOMContentLoaded', injectBanner);
  }
})();
PTEOF_cookie_banner_js
cat > robots.txt << 'PTEOF_robots_txt'
User-agent: *
Allow: /

Sitemap: https://www.pronosticitop.it/sitemap.xml
PTEOF_robots_txt
cat > sitemap.xml << 'PTEOF_sitemap_xml'
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.pronosticitop.it/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>
  <url><loc>https://www.pronosticitop.it/chi-siamo.html</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
  <url><loc>https://www.pronosticitop.it/termini.html</loc><changefreq>yearly</changefreq><priority>0.3</priority></url>
  <url><loc>https://www.pronosticitop.it/privacy.html</loc><changefreq>yearly</changefreq><priority>0.3</priority></url>
  <url><loc>https://www.pronosticitop.it/cookie-policy.html</loc><changefreq>yearly</changefreq><priority>0.3</priority></url>
</urlset>
PTEOF_sitemap_xml
cat > README.md << 'PTEOF_README_md'
# PronosticiTop

Sito pubblico di pronostici calcio settimanali basati su analisi statistica reale
(forma, gol fatti/subiti, classifica, infortuni). Finanziato tramite pubblicità
standard (Google AdSense), nessuna registrazione richiesta per consultare i
contenuti.

## Struttura

- `index.html` — homepage: mostra le schedine del turno selezionato, raggruppate
  per livello di rischio, con storico dei risultati.
- `chi-siamo.html` — spiegazione del metodo (analisi statistica, mercati usati,
  livelli di rischio, confidenza dei dati).
- `termini.html` — termini di utilizzo e disclaimer (nessun consiglio di
  scommessa, vietato ai minori di 18 anni, gioco responsabile).
- `privacy.html`, `cookie-policy.html` — informativa privacy (GDPR) e cookie
  (Google Analytics + Google AdSense).
- `cookie-banner.js` — banner di consenso cookie con Google Consent Mode
  (categorie: necessari, analytics, pubblicità).
- `data/settimane.json` + `data/<id>.json` — dati delle schedine (stesso schema
  della sezione privata in analisiebusinessplan/pronostici — vedi quel repo per
  la documentazione completa dello schema dati e dei criteri di generazione).
- `robots.txt`, `sitemap.xml` — SEO di base.

## Deploy

Pensato per deploy statico automatico (Vercel/Netlify) collegato a questo
repository: ogni push sul branch principale pubblica la nuova versione.
Dominio: pronosticitop.it (+ pronosticitop.com).

## Da fare prima del lancio pubblico

- [ ] Collegare il dominio pronosticitop.it (DNS) all'hosting statico scelto
- [ ] Richiedere l'approvazione Google AdSense e inserire lo script reale
      (attualmente ci sono solo placeholder `<div class="ad-slot">`)
- [ ] Sostituire `G-XXXXXXXXXX` in `cookie-banner.js` con l'ID Google Analytics
      reale, quando creato
- [ ] Verificare testo legale (termini/privacy) con un consulente prima del
      lancio definitivo
- [ ] Impostare l'automazione settimanale (vedi repo analisiebusinessplan) per
      pubblicare anche qui i nuovi turni, oppure sincronizzare manualmente
      `data/` da quel repo ogni settimana
PTEOF_README_md
cat > vercel.json << 'PTEOF_vercel_json'
{
  "rewrites": [
    { "source": "/(.*\\.html)", "destination": "/$1" },
    { "source": "/", "destination": "/index.html" }
  ]
}
PTEOF_vercel_json
mkdir -p data
cat > data/settimane.json << 'PTEOF_settimane_json'
{
  "settimane": [
    {
      "id": "2026-09-15",
      "titolo": "Weekend 18–20 settembre 2026",
      "file": "2026-09-15.json"
    },
    {
      "id": "2026-09-15-ggng",
      "titolo": "Weekend 18–20 settembre 2026 — Solo Gol/No Gol (mondiale)",
      "file": "2026-09-15-ggng.json"
    },
    {
      "id": "2026-09-15-uo",
      "titolo": "Weekend 18–20 settembre 2026 — Solo Under/Over (mondiale)",
      "file": "2026-09-15-uo.json"
    }
  ]
}
PTEOF_settimane_json
curl -s -o data/2026-09-15.json "https://raw.githubusercontent.com/leonardomascia85-commits/analisiebusinessplan/claude/sleepy-einstein-temurs/pronostici/data/2026-09-15.json"
curl -s -o data/2026-09-15-ggng.json "https://raw.githubusercontent.com/leonardomascia85-commits/analisiebusinessplan/claude/sleepy-einstein-temurs/pronostici/data/2026-09-15-ggng.json"
curl -s -o data/2026-09-15-uo.json "https://raw.githubusercontent.com/leonardomascia85-commits/analisiebusinessplan/claude/sleepy-einstein-temurs/pronostici/data/2026-09-15-uo.json"

python3 -c "
import json
for f in ['data/settimane.json','data/2026-09-15.json','data/2026-09-15-ggng.json','data/2026-09-15-uo.json']:
    json.load(open(f))
    print(f, 'OK')
"
git add -A
git commit -m "Prima pubblicazione sito PronosticiTop"
git push -u origin main
