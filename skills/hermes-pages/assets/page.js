'use strict';
(() => {
  const root = document.documentElement;
  const tell = text => { document.getElementById('feedback').textContent = text; };
  try { const value = localStorage.getItem('hermes-pages-theme'); if (['light','dark'].includes(value)) root.dataset.theme = value; } catch (_) {}
  document.getElementById('theme').addEventListener('click', () => {
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('hermes-pages-theme', root.dataset.theme); } catch (_) {}
  });
  document.getElementById('print').addEventListener('click', () => window.print());
  document.getElementById('copy').addEventListener('click', async () => {
    try { if (!navigator.clipboard) throw new Error('unsupported'); await navigator.clipboard.writeText(location.href); tell('Link copied'); }
    catch (_) { tell('Copy is unavailable here. Copy the address from your browser.'); }
  });
  const button = document.getElementById('listen');
  const label = button.querySelector('span') || button;
  if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
    label.textContent = 'Listen unavailable'; button.disabled = true; button.title = 'This browser does not support speech synthesis.';
    return;
  }
  button.addEventListener('click', () => {
    if (speechSynthesis.speaking || speechSynthesis.pending) { speechSynthesis.cancel(); label.textContent = 'Listen'; return; }
    // Short utterances reduce browser truncation; voices depend on the browser/OS.
    const text = document.querySelector('main').innerText;
    const chunks = text.match(/[\s\S]{1,180}(?:\s|$)|[\s\S]{1,180}/g) || [];
    const voices = speechSynthesis.getVoices();
    if (!voices.length) { tell('No speech voice is available yet. Try again or check browser voice support.'); return; }
    label.textContent = 'Stop';
    chunks.forEach((chunk, i) => {
      const speech = new SpeechSynthesisUtterance(chunk);
      // Prefer a local voice, but do not claim speech is always offline.
      const local = voices.find(v => v.localService); if (local) speech.voice = local;
      speech.onerror = () => { speechSynthesis.cancel(); label.textContent = 'Listen'; tell('Speech unavailable or interrupted in this browser.'); };
      if (i === chunks.length - 1) speech.onend = () => { label.textContent = 'Listen'; };
      speechSynthesis.speak(speech);
    });
  });
  window.addEventListener('pagehide', () => speechSynthesis.cancel());
})();
