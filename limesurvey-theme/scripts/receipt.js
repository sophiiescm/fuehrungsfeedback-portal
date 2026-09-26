/* Quittung: Nach dem Absenden holt dieses Skript die eigene Antwortseite ("Antworten drucken") aus der
 * laufenden Sitzung, verpackt sie und leitet zum Portal weiter. Die Antworten stehen dabei nur im
 * URL-FRAGMENT (#...): Fragmente werden vom Browser nie an einen Server gesendet. Das Portal legt sie
 * ausschliesslich im Speicher DIESES Geraets ab (localStorage). Es gibt keine serverseitige Verknuepfung
 * zwischen Person und Antworten (Anonymitaet bleibt gewahrt). */
(function () {
  'use strict';
  function ready(fn) { if (document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }

  ready(function () {
    if (!document.querySelector('.completed-wrapper')) return;
    var portal = document.querySelector('a[href*="/feedbacks/quittung"]');
    var print = document.querySelector('a[href*="printanswers/view"]');
    if (!portal || !print) return;

    var sidMatch = /surveyid=(\d+)|surveyid\/(\d+)/.exec(print.getAttribute('href'));
    var sid = sidMatch ? (sidMatch[1] || sidMatch[2]) : '';

    function text(el) { return (el ? el.textContent : '').replace(/\s+/g, ' ').trim(); }
    function stripId(s) { return s.replace(/\s*\(\d+\)\s*$/, ''); }

    function parse(html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var out = [];
      doc.querySelectorAll('groupsection, .groupSection').forEach(function (g) {
        var groupName = stripId(text(g.querySelector('h1')));
        g.querySelectorAll('.question-container-printanswers').forEach(function (q) {
          var qb = q.querySelector('.col-md-4 b');
          var answers = [];
          q.querySelectorAll('.col-lg-8 .row').forEach(function (row) {
            var label = text(row.querySelector('.text-end'));
            var val = text(row.querySelector('.text-start'));
            if (!label && !val) return;
            answers.push(label && val && label !== val ? label + ' (' + val + ')' : (label || val));
          });
          if (!answers.length) { var a = text(q.querySelector('.col-lg-8')); if (a) answers.push(a); }
          out.push({ g: groupName, q: stripId(text(qb)), a: answers });
        });
      });
      return out;
    }

    function b64url(str) {
      var bytes = new TextEncoder().encode(str), bin = '';
      bytes.forEach(function (b) { bin += String.fromCharCode(b); });
      return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }

    var note = document.createElement('p');
    note.textContent = 'Deine Antworten werden für dich vorbereitet – du wirst gleich zum Portal weitergeleitet …';
    note.style.cssText = 'margin-top:1rem;font-weight:600';
    var host = document.querySelector('.completed-wrapper');
    host.appendChild(note);

    function go(fragment) {
      var url = portal.getAttribute('href').split('#')[0];
      window.location.href = url + (fragment ? '#' + fragment : '');
    }

    fetch(print.getAttribute('href'), { credentials: 'same-origin' })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var data = parse(html);
        var payload = b64url(JSON.stringify({ sid: sid, at: new Date().toISOString().slice(0, 10), items: data }));
        go(payload.length < 60000 && data.length ? 'r=' + payload + '&sid=' + sid : 'sid=' + sid);
      })
      .catch(function () { go('sid=' + sid); });
  });
})();
