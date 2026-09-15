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

  function matchCardHTML(m) {
    return (
      '<div class="match-card">' +
        '<div class="match-date">' + fmtDate(m.data) + '</div>' +
        '<div class="match-teams">' + m.casa + ' — ' + m.trasferta + '</div>' +
        (m.forma_casa ? '<div class="match-form">Forma ' + m.casa + ': ' + m.forma_casa + ' · Forma ' + m.trasferta + ': ' + m.forma_trasferta + '</div>' : '') +
        '<div class="picks-row">' +
          pickBoxHTML('Esito', m.pick_1x2) +
          pickBoxHTML('Under/Over 2.5', m.pick_uo) +
          pickBoxHTML('Gol/No Gol', m.pick_gg) +
        '</div>' +
        (m.nota ? '<div class="match-note">' + m.nota + '</div>' : '') +
      '</div>'
    );
  }

  function pickBoxHTML(label, pick) {
    if (!pick) return '';
    return (
      '<div class="pick-box">' +
        '<div class="pick-label">' + label + '</div>' +
        '<div class="pick-value">' + pick.etichetta + '</div>' +
        '<div class="pick-prob">' + pct(pick.probabilita) + '</div>' +
      '</div>'
    );
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
          if (!data.partite || !data.partite.length) {
            root.innerHTML = '<div class="empty">Nessuna partita disponibile per questo turno.</div>';
            return;
          }
          root.innerHTML = data.partite.map(matchCardHTML).join('');
        })
        .catch(function () {
          if (banner) banner.style.display = 'none';
          root.innerHTML = '<div class="empty">Dati non ancora pubblicati per questo campionato.</div>';
        });
    }
  };
})();
