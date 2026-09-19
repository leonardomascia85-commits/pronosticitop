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
    finale: 'FINALE'
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
    if (stato === 'finale') {
      if (actualEsito == null) return '';
      var win = pickEsito === actualEsito;
      return '<span class="pick-result ' + (win ? 'win' : 'lose') + '">' + (win ? '✅' : '❌') + (risultato.punteggio ? ' ' + risultato.punteggio : '') + '</span>';
    }
    var liveLbl = STATUS_LABELS[stato] || 'LIVE';
    return '<span class="ev-live"><span class="live-dot"></span>' + liveLbl + (risultato.punteggio ? ' ' + risultato.punteggio : '') + '</span>';
  }

  function statusBadgeHTML(risultato) {
    if (!risultato || risultato.stato === 'non_iniziata' || !STATUS_LABELS[risultato.stato]) return '';
    var cls = risultato.stato === 'finale' ? 'status-finale' : 'status-live';
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
          pickBoxHTML('Under/Over 2.5', m.pick_uo, actual ? actual.uo : null, m.risultato) +
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

  function bestPick(m) {
    var opts = [
      { market: 'Esito', pick: m.pick_1x2 },
      { market: 'Under/Over 2.5', pick: m.pick_uo },
      { market: 'Gol/No Gol', pick: m.pick_gg }
    ].filter(function (o) { return o.pick; });
    if (!opts.length) return null;
    opts.sort(function (a, b) { return b.pick.probabilita - a.pick.probabilita; });
    return opts[0];
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
      var actualForMarket = actual ? (best.market === 'Esito' ? actual.esito1x2 : (best.market === 'Under/Over 2.5' ? actual.uo : actual.gg)) : null;
      rows += (
        '<div class="schedina-item">' +
          '<div class="schedina-match">' + m.casa + ' — ' + m.trasferta + '</div>' +
          '<div class="schedina-pick">' + best.pick.etichetta + pickResultHTML(best.pick.esito, actualForMarket, m.risultato) + '<span class="schedina-market">' + best.market + '</span></div>' +
          '<div class="schedina-prob">' + pct(best.pick.probabilita) + '</div>' +
        '</div>'
      );
    });
    if (!n) return '';
    return (
      '<div class="schedina-card">' +
        '<div class="schedina-head">' +
          '<span class="schedina-title">Schedina consigliata — ' + titolo + '</span>' +
          '<span class="schedina-pill">Media ' + pct(somma / n) + '</span>' +
          '<span class="schedina-pill combo">Combinata ' + pct(combinata) + '</span>' +
        '</div>' +
        '<div class="schedina-list">' + rows + '</div>' +
        '<div class="schedina-disclaimer">Per ogni partita è indicato il mercato (Esito, Under/Over 2.5 o Gol/No Gol) con la probabilità stimata più alta tra i tre.</div>' +
      '</div>'
    );
  }

  function schedineHTML(data) {
    var grouped = groupByGirone(data.partite);
    return grouped.order.map(function (key) {
      var titolo = key === '_all' ? data.campionato : data.campionato + ' — Girone ' + key;
      return schedinaCardHTML(grouped.groups[key], titolo);
    }).join('');
  }

  window.PTCampionato = {
    render: function (dataUrl, rootId, bannerId) {
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
          schedineEl.innerHTML = schedineHTML(data);
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
