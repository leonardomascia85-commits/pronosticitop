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
    el.style.cssText = 'position:fixed;left:16px;right:16px;bottom:16px;z-index:9999;max-width:640px;margin:0 auto;background:#151922;color:#eef1f6;border:1px solid #262c39;border-radius:16px;padding:20px;font-family:Inter,-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px;box-shadow:0 12px 40px rgba(0,0,0,.45)';
    el.innerHTML =
      '<p style="margin:0 0 14px;line-height:1.5">🍪 Usiamo cookie tecnici (sempre attivi), di analisi e pubblicitari (Google AdSense) per mostrare annunci pertinenti. Puoi scegliere quali accettare. Leggi la <a href="/cookie-policy.html" style="color:#8fadd9">Cookie Policy</a>.</p>' +
      '<div style="display:flex;gap:10px;flex-wrap:wrap">' +
      '<button id="pt-accept-all" style="background:linear-gradient(135deg,#5f8fd9,#7ba0d9);color:#fff;border:none;border-radius:10px;padding:10px 18px;cursor:pointer;font-size:14px;font-weight:600;box-shadow:0 4px 16px rgba(95,143,217,.3)">Accetta tutti</button>' +
      '<button id="pt-reject-all" style="background:transparent;color:#eef1f6;border:1px solid #262c39;border-radius:10px;padding:10px 18px;cursor:pointer;font-size:14px;font-weight:600">Solo necessari</button>' +
      '<button id="pt-customize" style="background:transparent;color:#8f98ab;border:none;text-decoration:underline;padding:10px 4px;cursor:pointer;font-size:14px">Personalizza</button>' +
      '</div>';
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
