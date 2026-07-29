/* ══════════════════════════════════════════════════════════════════════
   SJU Assistant - embeddable widget loader

   Drop this one line into any page, just before </body>:

     <script src="https://YOUR-APP.vercel.app/static/widget.js" defer></script>

   It adds a floating button that opens the assistant in an iframe served
   from this same app. The chat UI lives in embed.html, so the host page's
   CSS and JavaScript can never collide with it, and no API key ever
   touches the university's web server.
══════════════════════════════════════════════════════════════════════ */
(function () {
  var self = document.currentScript ||
             document.querySelector('script[src*="widget.js"]');
  var base = self ? self.src.replace(/\/[^\/]*$/, '') : '';
  var origin = base ? new URL(base, location.href).origin : location.origin;

  var css = document.createElement('style');
  css.textContent = [
    '#sjuFab{position:fixed;bottom:24px;right:24px;width:70px;height:70px;background:#0a2340;border:none;border-radius:50%;cursor:pointer;box-shadow:0 4px 20px rgba(0,32,96,.45);display:flex;align-items:center;justify-content:center;z-index:2147483000;transition:transform .2s,box-shadow .2s;padding:0}',
    '#sjuFab:hover{transform:scale(1.1);box-shadow:0 8px 28px rgba(0,32,96,.55)}',
    '#sjuFab svg{width:32px;height:32px;fill:#fff}',
    '#sjuFabDot{position:absolute;top:-3px;right:-3px;width:24px;height:24px;background:#e63946;border-radius:50%;border:3px solid #fff;font:800 12px/1 system-ui,sans-serif;color:#fff;display:flex;align-items:center;justify-content:center;animation:sjuPulse 2s ease-in-out infinite}',
    '@keyframes sjuPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.15)}}',
    '#sjuFabLabel{position:fixed;right:104px;bottom:44px;background:#fff;color:#e63946;font:800 15px/1 system-ui,sans-serif;padding:9px 18px;border-radius:22px;box-shadow:0 4px 14px rgba(0,0,0,.18);z-index:2147482999;white-space:nowrap}',
    '#sjuFrame{position:fixed;bottom:106px;right:24px;width:540px;height:840px;max-height:calc(100vh - 130px);border:0;border-radius:22px;box-shadow:0 12px 48px rgba(0,0,0,.22);z-index:2147482999;background:#fff;opacity:0;transform:scale(.95) translateY(12px);pointer-events:none;transition:transform .22s ease,opacity .22s ease}',
    '#sjuFrame.open{opacity:1;transform:none;pointer-events:all}',
    // phones have no room for a floating panel - take the whole screen instead
    '@media(max-width:560px){#sjuFrame{inset:0;width:100%;height:100%;max-height:none;border-radius:0}#sjuFabLabel{display:none}}'
  ].join('\n');
  document.head.appendChild(css);

  var label = document.createElement('div');
  label.id = 'sjuFabLabel';
  label.textContent = 'Chat';

  var fab = document.createElement('button');
  fab.id = 'sjuFab';
  fab.setAttribute('aria-label', 'Open SJU AI Assistant');
  fab.innerHTML =
    '<svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 0 1 2 2c0 .55-.22 1.05-.59 1.41A2 2 0 0 1 14 7v1h2a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-6a3 3 0 0 1 3-3h2V7a2 2 0 0 1 1-1.73A2 2 0 0 1 10 4a2 2 0 0 1 2-2zM8 10a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1H8zm1.5 2.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm5 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zM4 12h1v4H4a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1zm16 0a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-1v-4h1z"/></svg>' +
    '<span id="sjuFabDot">AI</span>';

  var frame = document.createElement('iframe');
  frame.id = 'sjuFrame';
  frame.title = 'SJU Assistant';
  frame.setAttribute('allow', 'clipboard-write');

  var open = false, loaded = false;
  function toggle() {
    open = !open;
    // only fetch the chat app the first time someone actually opens it
    if (open && !loaded) { frame.src = base + '/embed.html'; loaded = true; }
    frame.classList.toggle('open', open);
    label.style.display = open ? 'none' : '';
    if (open) frame.focus();
  }
  fab.addEventListener('click', toggle);
  label.addEventListener('click', toggle);

  window.addEventListener('message', function (e) {
    if (e.origin === origin && e.data === 'sju-chat-close' && open) toggle();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && open) toggle();
  });

  function mount() { document.body.append(label, fab, frame); }
  if (document.body) mount();
  else document.addEventListener('DOMContentLoaded', mount);
})();
