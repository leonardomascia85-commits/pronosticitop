(function () {
  'use strict';

  function fmtDate(iso) {
    try {
      var d = new Date(iso);
      var opts = { timeZone: 'Europe/Rome' };
      return d.toLocaleDateString('it-IT', Object.assign({}, opts, { weekday: 'short', day: '2-digit', month: '2-digit' })) +
        ' ' + d.toLocaleTimeString('it-IT', Object.assign({}, opts, { hour: '2-digit', minute: '2-digit' }));
    } catch (e) { return iso; }
  }

  function pct(x) { return Math.round(x * 100) + '%'; }

  var STATUS_LABELS = {
    non_iniziata: '',
    in_corso: 'LIVE · 1° tempo',
    intervallo: 'INTERVALLO',
    secondo_tempo: 'LIVE · 2° tempo',
    finale: 'FINALE',
    sospesa: 'SOSPESA'
  };

  function parseScore(punteggio) {
    if (!punteggio) return null;
    var parts = punteggio.split('-').map(function (x) { return parseInt(x, 10); });
    if (parts.length !== 2 || isNaN(parts[0]) || isNaN(parts[1])) return null;
    return { home: parts[0], away: parts[1] };
  }

  function actualEsiti(score) {
    if (!score) return null;
    return {
      esito1x2: score.home > score.away ? '1' : (score.home < score.away ? '2' : 'X'),
      uo: (score.home + score.away) > 2.5 ? 'over' : 'under',
      uo35: (score.home + score.away) > 3.5 ? 'over' : 'under',
      gg: (score.home > 0 && score.away > 0) ? 'gol' : 'nogol'
    };
  }

  function resultIconHTML(pickEsito, actualEsito) {
    if (actualEsito == null) return '';
    return '<span class="pick-result ' + (pickEsito === actualEsito ? 'win' : 'lose') + '">' + (pickEsito === actualEsito ? '✅' : '❌') + '</span>';
  }

  // Come resultIconHTML, ma consapevole dello stato della partita: a partita in corso
  // mostra "LIVE" col punteggio invece di anticipare un esito che puo' ancora cambiare;
  // a partita finita mostra l'icona col punteggio finale.
  function pickResultHTML(pickEsito, actualEsito, risultato) {
    var stato = risultato ? risultato.stato : 'non_iniziata';
    if (stato === 'non_iniziata' || !stato) return '';
    if (stato === 'sospesa') return '<span class="pick-result">⏸️ sospesa</span>';
    if (stato === 'finale') {
      if (actualEsito == null) return '';
      var win = pickEsito === actualEsito;
      return '<span class="pick-result ' + (win ? 'win' : 'lose') + '">' + (win ? '✅' : '❌') + (risultato.punteggio ? ' ' + risultato.punteggio : '') + '</span>';
    }
    var liveLbl = STATUS_LABELS[stato] || 'LIVE';
    return '<span class="ev-live"><span class="live-dot"></span>' + liveLbl + (risultato.punteggio ? ' ' + risultato.punteggio : '') + '</span>';
  }

  // Come pickResultHTML, ma per la doppia chance: il pick (es. "1X") vince se
  // l'esito 1X2 reale (un singolo carattere "1"/"X"/"2") e' uno dei due che copre,
  // quindi il confronto e' "pickEsito contiene actualEsito1x2", non un'uguaglianza esatta.
  function dcResultHTML(pickEsito, actualEsito1x2, risultato) {
    var stato = risultato ? risultato.stato : 'non_iniziata';
    if (stato === 'non_iniziata' || !stato) return '';
    if (stato === 'sospesa') return '<span class="pick-result">⏸️ sospesa</span>';
    if (stato === 'finale') {
      if (actualEsito1x2 == null) return '';
      var win = pickEsito.indexOf(actualEsito1x2) !== -1;
      return '<span class="pick-result ' + (win ? 'win' : 'lose') + '">' + (win ? '✅' : '❌') + (risultato.punteggio ? ' ' + risultato.punteggio : '') + '</span>';
    }
    var liveLbl = STATUS_LABELS[stato] || 'LIVE';
    return '<span class="ev-live"><span class="live-dot"></span>' + liveLbl + (risultato.punteggio ? ' ' + risultato.punteggio : '') + '</span>';
  }

  function statusBadgeHTML(risultato) {
    if (!risultato || risultato.stato === 'non_iniziata' || !STATUS_LABELS[risultato.stato]) return '';
    var cls = (risultato.stato === 'finale' || risultato.stato === 'sospesa') ? 'status-finale' : 'status-live';
    return '<span class="match-status ' + cls + '">' + STATUS_LABELS[risultato.stato] + (risultato.punteggio ? ' · ' + risultato.punteggio : '') + '</span>';
  }

  function matchCardHTML(m) {
    var score = m.risultato ? parseScore(m.risultato.punteggio) : null;
    var actual = actualEsiti(score);
    return (
      '<div class="match-card">' +
        '<div class="match-date">' + fmtDate(m.data) + statusBadgeHTML(m.risultato) + '</div>' +
        '<div class="match-teams">' + m.casa + ' — ' + m.trasferta + '</div>' +
        (m.forma_casa ? '<div class="match-form">Forma ' + m.casa + ': ' + m.forma_casa + ' · Forma ' + m.trasferta + ': ' + m.forma_trasferta + '</div>' : '') +
        '<div class="picks-row">' +
          pickBoxHTML('Esito', m.pick_1x2, actual ? actual.esito1x2 : null, m.risultato) +
          dcBoxHTML(m.pick_dc, actual ? actual.esito1x2 : null, m.risultato) +
          pickBoxHTML('Under/Over 2.5', m.pick_uo, actual ? actual.uo : null, m.risultato) +
          pickBoxHTML('Under/Over 3.5', m.pick_uo35, actual ? actual.uo35 : null, m.risultato) +
          pickBoxHTML('Gol/No Gol', m.pick_gg, actual ? actual.gg : null, m.risultato) +
        '</div>' +
        (m.nota ? '<div class="match-note">' + m.nota + '</div>' : '') +
      '</div>'
    );
  }

  function pickBoxHTML(label, pick, actualEsito, risultato) {
    if (!pick) return '';
    return (
      '<div class="pick-box">' +
        '<div class="pick-label">' + label + '</div>' +
        '<div class="pick-value">' + pick.etichetta + pickResultHTML(pick.esito, actualEsito, risultato) + '</div>' +
        '<div class="pick-prob">' + pct(pick.probabilita) + '</div>' +
      '</div>'
    );
  }

  function dcBoxHTML(pick, actualEsito1x2, risultato) {
    if (!pick) return '';
    return (
      '<div class="pick-box">' +
        '<div class="pick-label">Doppia chance</div>' +
        '<div class="pick-value">' + pick.esito + dcResultHTML(pick.esito, actualEsito1x2, risultato) + '</div>' +
        '<div class="pick-prob">' + pct(pick.probabilita) + '</div>' +
      '</div>'
    );
  }

  // Probabilita' massima oltre la quale un pick non viene piu' considerato "di valore":
  // Doppia chance e Under 3.5 coprono piu' esiti e quindi hanno quasi sempre la
  // probabilita' stimata piu' alta, ma con una quota troppo bassa per essere un
  // pronostico interessante. Tra i mercati con probabilita' entro questo tetto si
  // sceglie comunque il piu' alto (resta il pick con dati migliori), cosi' da avere
  // un mix piu' vario tra Esito secco, Under/Over e Gol/No Gol invece di appiattirsi
  // sempre sul mercato piu' "coperto". Se nessun mercato rientra nel tetto (partita
  // a senso unico) si torna al piu' probabile in assoluto, per non forzare un pick
  // debole solo per varieta'.
  var MAX_PROB_PICK = 0.65;

  function bestPick(m) {
    var opts = [
      { market: 'Esito', pick: m.pick_1x2 },
      { market: 'Doppia chance', pick: m.pick_dc },
      { market: 'Under/Over 2.5', pick: m.pick_uo },
      { market: 'Under/Over 3.5', pick: m.pick_uo35 },
      { market: 'Gol/No Gol', pick: m.pick_gg }
    ].filter(function (o) { return o.pick; });
    if (!opts.length) return null;
    opts.sort(function (a, b) { return b.pick.probabilita - a.pick.probabilita; });
    var valueOpts = opts.filter(function (o) { return o.pick.probabilita <= MAX_PROB_PICK; });
    return valueOpts.length ? valueOpts[0] : opts[0];
  }

  function groupByGirone(partite) {
    var groups = {}, order = [];
    partite.forEach(function (m) {
      var key = m.girone || '_all';
      if (!groups[key]) { groups[key] = []; order.push(key); }
      groups[key].push(m);
    });
    return { groups: groups, order: order };
  }

  // Solo partite non ancora iniziate: una schedina consigliata guarda avanti,
  // non ha senso includere partite gia' finite o in corso.
  function nonFinaleMatches(partite) {
    return partite.filter(function (m) {
      return !m.risultato || !m.risultato.stato || m.risultato.stato === 'non_iniziata';
    });
  }

  // Le partite di uno stesso turno cadono entro pochi giorni l'una dall'altra:
  // una partita rinviata a settimane di distanza (es. per la sosta nazionali
  // o per maltempo) non va mescolata nella stessa schedina con le partite del
  // turno in corso, anche se ha ancora stato "non_iniziata". Tiene solo le
  // partite entro SAME_ROUND_WINDOW_DAYS dalla piu' vicina nel tempo.
  var SAME_ROUND_WINDOW_DAYS = 7;
  function sameRoundMatches(partite) {
    if (partite.length <= 1) return partite;
    var earliest = Math.min.apply(null, partite.map(function (m) { return new Date(m.data).getTime(); }));
    var windowMs = SAME_ROUND_WINDOW_DAYS * 24 * 60 * 60 * 1000;
    return partite.filter(function (m) { return new Date(m.data).getTime() - earliest <= windowMs; });
  }

  // Ordina per affidabilita' decrescente usando la probabilita' del miglior
  // pick di ciascuna partita (stesso criterio di bestPick).
  function sortByBestProb(partite) {
    return partite
      .map(function (m) { return { match: m, best: bestPick(m) }; })
      .filter(function (x) { return x.best; })
      .sort(function (a, b) { return b.best.pick.probabilita - a.best.pick.probabilita; })
      .map(function (x) { return x.match; });
  }

  // Costruisce N schedine "top" dalle partite non ancora iniziate piu'
  // affidabili dell'intero campionato (stessa logica per tutti i
  // campionati, Serie C compresa: nessun vincolo per girone). Preferisce
  // partite non ancora usate in una schedina precedente, cosi' le N
  // schedine restano il piu' possibile distinte tra loro; quando il pool e'
  // piccolo (un turno puo' avere anche solo 8-10 partite, non sempre
  // sufficienti per N schedine da 4/5/6 senza sovrapposizioni) riusa le
  // partite gia' mostrate pur di avere sempre N schedine, invece di farne
  // sparire qualcuna.
  function topSchedineHTML(data, opts) {
    var pool = sortByBestProb(sameRoundMatches(nonFinaleMatches(data.partite)));
    if (!pool.length) return '';
    var html = '', used = {};
    opts.sizes.forEach(function (n, i) {
      var fresh = pool.filter(function (m) { return !used[m.casa + ' - ' + m.trasferta]; });
      var list = fresh.slice(0, n);
      if (list.length < n) {
        var extra = pool.filter(function (m) { return list.indexOf(m) === -1; }).slice(0, n - list.length);
        list = list.concat(extra);
      }
      if (!list.length) return;
      list.forEach(function (m) { used[m.casa + ' - ' + m.trasferta] = true; });
      var titolo = opts.sizes.length > 1
        ? 'Schedina ' + data.campionato + ' #' + (i + 1) + ' — i più affidabili'
        : 'Schedina consigliata — ' + data.campionato;
      html += schedinaCardHTML(list, titolo);
    });
    return html;
  }

  function schedinaCardHTML(partite, titolo) {
    var rows = '', combinata = 1, somma = 0, n = 0;
    partite.forEach(function (m) {
      var best = bestPick(m);
      if (!best) return;
      combinata *= best.pick.probabilita;
      somma += best.pick.probabilita;
      n++;
      var score = m.risultato ? parseScore(m.risultato.punteggio) : null;
      var actual = actualEsiti(score);
      var marketKey = { 'Esito': 'esito1x2', 'Under/Over 2.5': 'uo', 'Under/Over 3.5': 'uo35', 'Gol/No Gol': 'gg' }[best.market];
      var resultHTML;
      if (best.market === 'Doppia chance') {
        resultHTML = dcResultHTML(best.pick.esito, actual ? actual.esito1x2 : null, m.risultato);
      } else {
        resultHTML = pickResultHTML(best.pick.esito, actual ? actual[marketKey] : null, m.risultato);
      }
      var pickText = best.market === 'Doppia chance' ? best.pick.esito : best.pick.etichetta;
      rows += (
        '<div class="schedina-item">' +
          '<div class="schedina-match">' + m.casa + ' — ' + m.trasferta + '</div>' +
          '<div class="schedina-pick">' + pickText + resultHTML + '<span class="schedina-market">' + best.market + '</span></div>' +
          '<div class="schedina-prob">' + pct(best.pick.probabilita) + '</div>' +
        '</div>'
      );
    });
    if (!n) return '';
    return (
      '<div class="schedina-card">' +
        '<div class="schedina-head">' +
          '<span class="schedina-title">' + titolo + '</span>' +
          '<span class="schedina-pill">Media ' + pct(somma / n) + '</span>' +
          '<span class="schedina-pill combo">Combinata ' + pct(combinata) + '</span>' +
        '</div>' +
        '<div class="schedina-list">' + rows + '</div>' +
        '<div class="schedina-disclaimer">Per ogni partita è indicato il mercato (Esito, Doppia Chance, Under/Over 2.5, Under/Over 3.5 o Gol/No Gol) con il miglior equilibrio tra probabilità stimata e quota: evitiamo di scegliere sempre i mercati con probabilità altissima ma quota troppo bassa (es. doppia chance), a parità di affidabilità dei dati preferiamo un pronostico con una quota più interessante.</div>' +
      '</div>'
    );
  }

  function schedineHTML(data) {
    var grouped = groupByGirone(data.partite);
    return grouped.order.map(function (key) {
      var partite = sortByBestProb(sameRoundMatches(nonFinaleMatches(grouped.groups[key])));
      if (!partite.length) return '';
      var titolo = 'Schedina consigliata — ' + (key === '_all' ? data.campionato : data.campionato + ' — Girone ' + key);
      return schedinaCardHTML(partite, titolo);
    }).join('');
  }

  window.PTCampionato = {
    render: function (dataUrl, rootId, bannerId, opts) {
      var root = document.getElementById(rootId || 'matchesRoot');
      var banner = document.getElementById(bannerId || 'giornataLabel');
      fetch(dataUrl)
        .then(function (r) { if (!r.ok) throw new Error('not found'); return r.json(); })
        .then(function (data) {
          if (banner) {
            banner.innerHTML = '<b>' + data.giornata + '</b> — ' + data.periodo + ' · aggiornato il ' +
              new Date(data.aggiornato).toLocaleDateString('it-IT', { day: '2-digit', month: 'long', year: 'numeric' });
          }
          var existingSchedine = document.getElementById('schedineConsigliate');
          if (existingSchedine) existingSchedine.parentNode.removeChild(existingSchedine);
          if (!data.partite || !data.partite.length) {
            root.innerHTML = '<div class="empty">Nessuna partita disponibile per questo turno.</div>';
            return;
          }
          var schedineEl = document.createElement('div');
          schedineEl.id = 'schedineConsigliate';
          schedineEl.innerHTML = (opts && opts.schedina) ? topSchedineHTML(data, opts.schedina) : schedineHTML(data);
          root.parentNode.insertBefore(schedineEl, root);
          root.innerHTML = data.partite.map(matchCardHTML).join('');
        })
        .catch(function () {
          if (banner) banner.style.display = 'none';
          root.innerHTML = '<div class="empty">Dati non ancora pubblicati per questo campionato.</div>';
        });
    }
  };
})();
