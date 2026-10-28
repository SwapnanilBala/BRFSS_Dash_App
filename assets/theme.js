// Follow the operating system's light/dark setting while the page is open.
// The theme is resolved once in <head> (THEME_BOOT in app.py) and on every
// toggle by the clientside callback; this only has to tell Dash when the OS
// flips, so that a "System" choice keeps tracking it without a reload.
(function () {
  if (!window.matchMedia) return;
  var query = window.matchMedia("(prefers-color-scheme: dark)");

  function notify(event) {
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props("os-theme", {
        data: event.matches ? "dark" : "light",
      });
    }
  }

  if (query.addEventListener) query.addEventListener("change", notify);
  else if (query.addListener) query.addListener(notify);
})();
