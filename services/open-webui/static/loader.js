(function () {
  try {
    var STALE = {
      "qwen3.5-9b-uncensored-aggressive": true,
      "qwen3.5-35b-a3b-uncensored-aggressive": true,
      "qwen3.5-122b-a10b-uncensored-aggressive": true,
    };

    function readSettings() {
      try {
        return JSON.parse(localStorage.getItem("settings") || "{}") || {};
      } catch (e) {
        return {};
      }
    }

    function writeSettings(s) {
      localStorage.setItem("settings", JSON.stringify(s));
    }

    // CRITICAL for Hub SSO + stock Open WebUI:
    // if ui.models is set before the models store is warm, onMount aborts and the
    // picker stays on "No models available" forever.
    (function clearSelectedModelsLocally() {
      var s = readSettings();
      var changed = false;
      if (s.directConnections) {
        delete s.directConnections;
        changed = true;
      }
      if (!s.ui || typeof s.ui !== "object") {
        s.ui = {};
        changed = true;
      }
      if (s.ui.directConnections) {
        delete s.ui.directConnections;
        changed = true;
      }
      if (Array.isArray(s.ui.models)) {
        delete s.ui.models;
        changed = true;
      }
      s.ui.showChangelog = false;
      writeSettings(s);
      try {
        localStorage.setItem("dismissedUpdateToast", String(Date.now()));
      } catch (e) {}
    })();

    // Hub SSO: stock OWUI trusted-header sign-in can finish (token set) but
    // leave the SPA stuck on /auth?redirect=… ("Signing in…") when goto()
    // races with a nested /auth redirect. Hard-navigate out once we have a token.
    function safeRedirectTarget() {
      var params = new URLSearchParams(location.search);
      var r = params.get("redirect") || "/";
      var guard = 0;
      while (guard++ < 5 && typeof r === "string" && r.indexOf("/auth") === 0) {
        try {
          r = new URL(r, location.origin).searchParams.get("redirect") || "/";
        } catch (e) {
          return "/";
        }
      }
      // Bare /c is not a route in OWUI 0.10 (only /c/{chatId}) → SPA 404.
      if (r === "/c" || r === "/c/") return "/";
      if (
        typeof r !== "string" ||
        r.charAt(0) !== "/" ||
        r.indexOf("//") === 0 ||
        r.indexOf("/auth") === 0
      ) {
        return "/";
      }
      return r;
    }

    function escapeStuckAuth() {
      if (location.pathname !== "/auth") return;
      if (!localStorage.token) return;
      if (sessionStorage.getItem("__iron_auth_escape") === "1") return;
      sessionStorage.setItem("__iron_auth_escape", "1");
      location.replace(safeRedirectTarget());
    }

    // Old Hub land path /c (no id) → home
    if (location.pathname === "/c" || location.pathname === "/c/") {
      location.replace("/" + location.search + location.hash);
      return;
    }

    if (location.pathname === "/auth") {
      var authTries = 0;
      var authIv = setInterval(function () {
        authTries += 1;
        if (localStorage.token) {
          clearInterval(authIv);
          escapeStuckAuth();
        }
        if (authTries > 50) clearInterval(authIv);
      }, 100);
    } else {
      try {
        sessionStorage.removeItem("__iron_auth_escape");
      } catch (e) {}
    }

    var started = false;

    async function api(path, token, method, body) {
      var res = await fetch(path, {
        method: method || "GET",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        credentials: "include",
        cache: "no-store",
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) throw new Error(path + " " + res.status);
      if (res.status === 204) return null;
      return res.json();
    }

    async function clearServerSelection(token) {
      try {
        var cur = await api("/api/v1/users/user/settings", token);
        var ui = Object.assign({}, (cur && cur.ui) || {});
        if (!Array.isArray(ui.models) && ui.showChangelog === false) return;
        delete ui.models;
        ui.showChangelog = false;
        ui.version = ui.version || "0.10.2";
        await api("/api/v1/users/user/settings/update", token, "POST", { ui: ui });
      } catch (e) {}
    }

    function emptyPicker() {
      var text = (document.body && document.body.innerText) || "";
      if (text.indexOf("No models available") !== -1) return true;
      if (text.indexOf("Connect to an AI provider") !== -1) return true;
      var btn = document.getElementById("model-selector-0-button");
      if (!btn) return false;
      var label = ((btn.getAttribute("aria-label") || "") + " " + (btn.innerText || "")).toLowerCase();
      return label.indexOf("select a model") !== -1 || label.indexOf("selecione um modelo") !== -1;
    }

    async function boot() {
      if (started) return;
      var token = localStorage.token;
      if (!token) return;
      started = true;

      await clearServerSelection(token);

      var ids = [];
      try {
        var body = await api("/api/models?refresh=true&_=" + Date.now(), token);
        ids = (body.data || [])
          .map(function (m) {
            return m.id;
          })
          .filter(function (id) {
            return id && id !== "arena-model" && !STALE[id];
          });
      } catch (e) {}

      var tries = 0;
      var timer = setInterval(function () {
        tries += 1;
        if (!document.getElementById("model-selector-0-button") && tries < 8) return;
        var empty = emptyPicker();
        var available = ids.length > 0;
        if (!empty) {
          clearInterval(timer);
          sessionStorage.removeItem("__iron_models_reload");
          return;
        }
        if (available && tries >= 5) {
          clearInterval(timer);
          if (sessionStorage.getItem("__iron_models_reload") === "1") return;
          sessionStorage.setItem("__iron_models_reload", "1");
          var s = readSettings();
          if (s.ui) delete s.ui.models;
          writeSettings(s);
          location.reload();
        }
      }, 700);

      setTimeout(function () {
        clearInterval(timer);
      }, 12000);
    }

    var iv = setInterval(function () {
      if (localStorage.token) {
        boot();
        clearInterval(iv);
      }
    }, 150);
    setTimeout(function () {
      clearInterval(iv);
    }, 20000);
  } catch (e) {}
})();
