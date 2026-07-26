/**
 * Presencia HALU (en línea / ausente / desconectado) para la mensajería.
 *
 * - Define window.HALUPresence.update(data) para pintar los indicadores
 *   (elementos con data-presencia-user="<pk>").
 * - Para usuarios NO staff abre su propio WebSocket a /ws/notifications/
 *   (así quedan "en línea"); los staff ya lo abren con el script de toasts,
 *   que reenvía los eventos de presencia a HALUPresence.update.
 * - Interruptor manual En línea / Ausente y ausente automático por inactividad.
 *
 * Config vía #halu-presencia-config (data-*).
 */
(function () {
    var cfg = document.getElementById("halu-presencia-config");
    if (!cfg) return;

    var IS_STAFF = cfg.dataset.staff === "1";
    var URL_ESTADO = cfg.dataset.urlEstado;
    var URL_AUTO = cfg.dataset.urlAuto;
    var CSRF = cfg.dataset.csrf;
    var T = {
        EN_LINEA: cfg.dataset.txtOnline || "En línea",
        AUSENTE: cfg.dataset.txtAway || "Ausente",
        DESCONECTADO: cfg.dataset.txtOffline || "Desconectado"
    };
    var MSG_ONLINE = cfg.dataset.msgOnline || "{n} está en línea";
    var IDLE_MS = 6 * 60 * 1000; // ~6 min de inactividad → ausente automático
    var TOAST_DEBOUNCE_MS = 45000; // no repetir el aviso de un mismo usuario tan seguido (evita spam al navegar)

    var KNOWN = {};       // último estado conocido por usuario (evita avisar sin transición)
    var LAST_TOAST = {};  // último aviso "en línea" mostrado por usuario

    function esc(s) { return (s || "").replace(/[<>&"]/g, function (c) { return { "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]; }); }

    function ensureWrap() {
        var wrap = document.getElementById("presencia-toast-wrap");
        if (!wrap) {
            wrap = document.createElement("div");
            wrap.id = "presencia-toast-wrap";
            wrap.className = "toast-container position-fixed bottom-0 end-0 p-3";
            wrap.style.zIndex = "1250";
            document.body.appendChild(wrap);
        }
        return wrap;
    }

    // ---- Aviso emergente "X está en línea" (tipo MSN) ----------------------
    function toastOnline(nombre) {
        if (typeof bootstrap === "undefined" || !bootstrap.Toast) return;
        var el = document.createElement("div");
        el.className = "toast align-items-center text-bg-success border-0";
        el.setAttribute("role", "alert");
        el.innerHTML =
            '<div class="d-flex"><div class="toast-body"><i class="bi bi-person-check-fill me-1"></i>' +
            MSG_ONLINE.replace("{n}", esc(nombre)) +
            '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
        ensureWrap().appendChild(el);
        var t = new bootstrap.Toast(el, { delay: 4500 });
        t.show();
        el.addEventListener("hidden.bs.toast", function () { el.remove(); });
    }

    // ---- Toast de notificación (mensaje nuevo, etc.) en tiempo real --------
    function toastNotif(d) {
        if (typeof bootstrap === "undefined" || !bootstrap.Toast) return;
        var url = d.url || "";
        // No molestar si ya estás viendo esa misma página (p. ej. el chat abierto).
        if (url) {
            var path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
            if (window.location.pathname === path) return;
        }
        var sev = d.severity || "info";
        var head = sev === "danger" ? "bg-danger text-white" : sev === "warning" ? "bg-warning text-dark" : "bg-primary text-white";
        var icon = d.kind === "mensaje" ? "bi-chat-dots-fill" : "bi-bell-fill";
        var el = document.createElement("div");
        el.className = "toast border-0";
        el.setAttribute("role", "alert");
        el.innerHTML =
            '<div class="toast-header ' + head + '"><i class="bi ' + icon + ' me-2"></i>' +
            '<strong class="me-auto">' + esc(d.title || "Notificación") + '</strong>' +
            '<button type="button" class="btn-close ' + (sev === "warning" ? "" : "btn-close-white") + '" data-bs-dismiss="toast"></button></div>' +
            '<div class="toast-body">' + esc(d.message || "") + '</div>';
        if (url) {
            el.style.cursor = "pointer";
            el.addEventListener("click", function (ev) {
                if (ev.target.closest(".btn-close")) return;
                window.location.href = url;
            });
        }
        ensureWrap().appendChild(el);
        var t = new bootstrap.Toast(el, { delay: 6000 });
        t.show();
        el.addEventListener("hidden.bs.toast", function () { el.remove(); });
    }

    // ---- Pintar indicadores -------------------------------------------------
    function claseDot(estado) {
        return estado === "EN_LINEA" ? "p-online" : estado === "AUSENTE" ? "p-away" : "p-offline";
    }
    function paint(el, estado) {
        el.setAttribute("data-estado", estado);
        var dot = el.querySelector(".presencia-dot");
        if (dot) dot.className = "presencia-dot " + claseDot(estado);
        var txt = el.querySelector(".presencia-text");
        if (txt) txt.textContent = T[estado] || estado;
    }
    function pintarBanner(usuarioId, estado) {
        var b = document.getElementById("presencia-banner");
        if (!b || String(b.dataset.user) !== String(usuarioId)) return;
        var nombre = b.dataset.nombre || "";
        var dot = b.querySelector(".presencia-dot");
        if (dot) dot.className = "presencia-dot " + claseDot(estado);
        var txt = b.querySelector(".presencia-banner-text");
        if (txt) {
            if (estado === "EN_LINEA") txt.textContent = (b.dataset.tplOnline || "{n} está en línea").replace("{n}", nombre);
            else if (estado === "AUSENTE") txt.textContent = (b.dataset.tplAway || "{n} está ausente").replace("{n}", nombre);
            else txt.textContent = (b.dataset.tplOffline || "{n} está desconectado").replace("{n}", nombre);
        }
    }

    window.HALUPresence = window.HALUPresence || {};
    window.HALUPresence.update = function (data) {
        if (!data || data.usuario_id == null) return;
        var uid = String(data.usuario_id);
        // Aviso emergente al PASAR a en línea (transición real, con anti-spam).
        if (data.estado === "EN_LINEA" && KNOWN[uid] !== "EN_LINEA") {
            var now = Date.now();
            if (!LAST_TOAST[uid] || now - LAST_TOAST[uid] > TOAST_DEBOUNCE_MS) {
                LAST_TOAST[uid] = now;
                toastOnline(data.nombre || "");
            }
        }
        KNOWN[uid] = data.estado;
        var sel = '[data-presencia-user="' + data.usuario_id + '"]';
        document.querySelectorAll(sel).forEach(function (el) { paint(el, data.estado); });
        pintarBanner(data.usuario_id, data.estado);
    };

    // ---- WebSocket (solo no-staff; staff ya tiene el suyo) ------------------
    if (!IS_STAFF) {
        var scheme = location.protocol === "https:" ? "wss://" : "ws://";
        var sock = null, backoff = 1000, teardown = false;
        function connect() {
            try { sock = new WebSocket(scheme + location.host + "/ws/notifications/"); }
            catch (e) { setTimeout(connect, backoff); return; }
            sock.onopen = function () { backoff = 1000; };
            sock.onmessage = function (e) {
                try {
                    var d = JSON.parse(e.data);
                    if (!d) return;
                    if (d.kind === "presencia") { window.HALUPresence.update(d); return; }
                    // Cualquier otra notificación personal (mensaje nuevo, etc.) → toast en vivo.
                    toastNotif(d);
                } catch (_) {}
            };
            sock.onerror = function () { if (sock) try { sock.close(); } catch (_) {} };
            sock.onclose = function () { sock = null; if (teardown) return; setTimeout(connect, backoff); backoff = Math.min(60000, backoff * 2); };
        }
        window.addEventListener("beforeunload", function () { teardown = true; if (sock) try { sock.close(); } catch (_) {} });
        connect();
    }

    // ---- POST helper --------------------------------------------------------
    function post(url, body) {
        return fetch(url, {
            method: "POST",
            headers: { "X-CSRFToken": CSRF, "Content-Type": "application/x-www-form-urlencoded" },
            body: body
        }).catch(function () {});
    }

    // ---- Interruptor manual En línea / Ausente ------------------------------
    document.querySelectorAll("[data-presencia-set]").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            var estado = btn.getAttribute("data-presencia-set"); // DISPONIBLE / AUSENTE
            post(URL_ESTADO, "estado=" + encodeURIComponent(estado));
            document.querySelectorAll("[data-presencia-set]").forEach(function (b) {
                b.classList.toggle("active", b === btn);
            });
            var lbl = document.getElementById("mi-estado-label");
            if (lbl) lbl.textContent = estado === "AUSENTE" ? T.AUSENTE : T.EN_LINEA;
        });
    });

    // ---- Ausente automático por inactividad --------------------------------
    var idleTimer = null, estaAuto = false;
    function volverActivo() {
        if (estaAuto) { estaAuto = false; post(URL_AUTO, "away=0"); }
    }
    function reiniciarIdle() {
        volverActivo();
        clearTimeout(idleTimer);
        idleTimer = setTimeout(function () { estaAuto = true; post(URL_AUTO, "away=1"); }, IDLE_MS);
    }
    ["mousemove", "keydown", "touchstart", "scroll", "click"].forEach(function (ev) {
        document.addEventListener(ev, reiniciarIdle, { passive: true });
    });
    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") reiniciarIdle();
    });
    reiniciarIdle();

    // ---- Pintado inicial (estado que vino del servidor) --------------------
    // Sembramos KNOWN con el estado inicial para NO avisar de quien ya estaba
    // en línea al cargar la página (el aviso solo debe salir en la transición).
    document.querySelectorAll("[data-presencia-user][data-estado]").forEach(function (el) {
        var est = el.getAttribute("data-estado");
        paint(el, est);
        KNOWN[String(el.getAttribute("data-presencia-user"))] = est;
    });
    var b0 = document.getElementById("presencia-banner");
    if (b0 && b0.dataset.estado) {
        pintarBanner(b0.dataset.user, b0.dataset.estado);
        KNOWN[String(b0.dataset.user)] = b0.dataset.estado;
    }
})();
