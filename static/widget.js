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
    // Joey, the floating mascot button: gently bobs, with a soft gold halo
    '#sjuFab{position:fixed;bottom:24px;right:24px;width:100px;height:100px;background:none;border:none;border-radius:50%;cursor:pointer;padding:0;z-index:2147483000;filter:drop-shadow(0 10px 22px rgba(10,35,64,.38));animation:sjuBob 3.2s ease-in-out infinite;transition:transform .3s cubic-bezier(.2,.9,.25,1)}',
    '#sjuFab:hover{transform:scale(1.08)}',
    '#sjuFab img{width:100%;height:100%;display:block;border-radius:50%}',
    '#sjuFab::before{content:"";position:absolute;inset:-7px;border-radius:50%;border:2.5px solid rgba(240,201,61,.7);animation:sjuHalo 2.6s ease-out infinite}',
    '#sjuFabDot{position:absolute;bottom:6px;right:6px;width:20px;height:20px;background:#22c55e;border:3px solid #fff;border-radius:50%}',
    '@keyframes sjuBob{0%,100%{translate:0 0}50%{translate:0 -6px}}',
    '@keyframes sjuHalo{0%{transform:scale(.92);opacity:.9}100%{transform:scale(1.25);opacity:0}}',
    // "Hey, I'm Joey" greeting bubble beside the button
    '#sjuHello{position:fixed;right:142px;bottom:52px;max-width:320px;padding:18px 24px;background:rgba(255,255,255,.88);-webkit-backdrop-filter:blur(14px) saturate(160%);backdrop-filter:blur(14px) saturate(160%);border:1px solid rgba(255,255,255,.9);border-radius:24px 24px 6px 24px;box-shadow:0 14px 40px rgba(10,35,64,.22);font:500 17px/1.45 "Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",sans-serif;color:#33415c;cursor:pointer;z-index:2147482999;opacity:0;transform:translateY(10px) scale(.92);transform-origin:bottom right;pointer-events:none;transition:opacity .4s ease,transform .5s cubic-bezier(.2,1.4,.4,1)}',
    '#sjuHello.show{opacity:1;transform:none;pointer-events:all}',
    '#sjuHello b{display:block;font-size:22px;font-weight:800;color:#0a2340;letter-spacing:-.01em;margin-bottom:4px}',
    '@media(prefers-reduced-motion:reduce){#sjuFab,#sjuFab::before{animation:none}}',
    // frosted glass: the iframe is transparent and blurs whatever page sits behind it.
    // color-scheme must match embed.html or Chrome paints the frame opaque.
    '#sjuFrame{position:fixed;bottom:140px;right:24px;width:min(620px,calc(100vw - 48px));height:840px;max-height:calc(100vh - 164px);border:1px solid rgba(255,255,255,.55);border-radius:26px;color-scheme:normal;background:rgba(255,255,255,.08);-webkit-backdrop-filter:blur(28px) saturate(170%);backdrop-filter:blur(28px) saturate(170%);box-shadow:0 24px 70px rgba(10,35,64,.28),0 2px 8px rgba(10,35,64,.08);z-index:2147482999;opacity:0;transform:scale(.96) translateY(14px);transform-origin:bottom right;pointer-events:none;transition:transform .38s cubic-bezier(.2,.9,.25,1),opacity .28s ease}',
    '#sjuFrame.open{opacity:1;transform:none;pointer-events:all}',
    // phones have no room for a floating panel - take the whole screen instead
    '@media(max-width:560px){#sjuFrame{inset:0;width:100%;height:100%;max-height:none;border:0;border-radius:0}#sjuFab.open{display:none}#sjuFab{width:80px;height:80px;bottom:18px;right:18px}#sjuHello{right:110px;bottom:34px;max-width:210px;padding:14px 18px;font-size:15px}#sjuHello b{font-size:19px}}'
  ].join('\n');
  document.head.appendChild(css);

  var hello = document.createElement('div');
  hello.id = 'sjuHello';
  hello.setAttribute('role', 'button');
  hello.innerHTML = '<b>Hey, I’m Joey</b>Ask me anything about SJU!';

  var fab = document.createElement('button');
  fab.id = 'sjuFab';
  fab.setAttribute('aria-label', 'Chat with Joey, the SJU Assistant');
  fab.innerHTML = '<img src="' + base + '/joey.svg" alt=""><span id="sjuFabDot"></span>';

  var frame = document.createElement('iframe');
  frame.id = 'sjuFrame';
  frame.title = 'Joey - SJU Assistant';
  frame.setAttribute('allow', 'clipboard-write');
  frame.setAttribute('allowtransparency', 'true');

  var open = false, loaded = false;
  function toggle() {
    open = !open;
    // only fetch the chat app the first time someone actually opens it
    if (open && !loaded) { frame.src = base + '/embed.html'; loaded = true; }
    frame.classList.toggle('open', open);
    fab.classList.toggle('open', open);
    hello.classList.toggle('show', !open);   // greeting stays up whenever the chat is closed
    if (open) frame.focus();
  }
  fab.addEventListener('click', toggle);
  hello.addEventListener('click', toggle);

  setTimeout(function () { if (!open) hello.classList.add('show'); }, 1200);

  window.addEventListener('message', function (e) {
    if (e.origin === origin && e.data === 'sju-chat-close' && open) toggle();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && open) toggle();
  });

  function mount() { document.body.append(hello, fab, frame); }
  if (document.body) mount();
  else document.addEventListener('DOMContentLoaded', mount);
})();
