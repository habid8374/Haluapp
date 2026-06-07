/**
 * WebSocket de notificaciones HALU (Fase A–D).
 * JSON: kind, title, message, url (opcional), severity, institucion_id (opcional).
 * Reconexión con backoff exponencial; compatible con { "message": "..." } solo.
 */
(function () {
    var MAX_BACKOFF_MS = 60000;
    var INITIAL_BACKOFF_MS = 1000;

    function resolveUrl(url) {
        if (!url) return "";
        if (url.startsWith("http://") || url.startsWith("https://")) return url;
        var path = url.startsWith("/") ? url : "/" + url;
        return window.location.origin + path;
    }

    function applySeverity(headerEl, closeBtn, severity) {
        headerEl.className = "toast-header ";
        if (severity === "warning") {
            headerEl.classList.add("bg-warning", "text-dark");
            closeBtn.className = "btn-close";
        } else if (severity === "danger") {
            headerEl.classList.add("bg-danger", "text-white");
            closeBtn.className = "btn-close btn-close-white";
        } else {
            headerEl.classList.add("bg-primary", "text-white");
            closeBtn.className = "btn-close btn-close-white";
        }
    }

    function setIcon(iconEl, kind) {
        iconEl.className = "bi me-2 ";
        if (kind === "cita_nueva") {
            iconEl.classList.add("bi-calendar-check");
        } else {
            iconEl.classList.add("bi-bell-fill");
        }
    }

    function bindDraggable(toastElement) {
        var isDragging = false;
        var currentX = 0;
        var currentY = 0;
        var initialX;
        var initialY;

        toastElement.addEventListener("mousedown", function (e) {
            if (e.target.closest(".toast-header")) {
                initialX = e.clientX - currentX;
                initialY = e.clientY - currentY;
                isDragging = true;
                toastElement.style.transition = "none";
                toastElement.style.transform = "none";
                toastElement.style.minWidth = "300px";
            }
        });

        document.addEventListener("mousemove", function (e) {
            if (isDragging) {
                e.preventDefault();
                currentX = e.clientX - initialX;
                currentY = e.clientY - initialY;
                toastElement.style.position = "absolute";
                toastElement.style.left = currentX + "px";
                toastElement.style.top = currentY + "px";
            }
        });

        document.addEventListener("mouseup", function () {
            isDragging = false;
            toastElement.style.transition = "opacity 0.3s ease";
            toastElement.style.minWidth = "300px";
        });
    }

    function initStaffNotifications() {
        var root = document.getElementById("staff-ws-notifications-root");
        if (!root) return;

        var toastElement = document.getElementById("staff-notif-toast");
        var headerEl = document.getElementById("staff-notif-header");
        var titleEl = document.getElementById("staff-notif-title");
        var closeBtn = document.getElementById("staff-notif-close");
        var iconEl = document.getElementById("staff-notif-icon");
        var bodyEl = document.getElementById("staff-notif-body");
        var linkEl = document.getElementById("staff-notif-link");

        if (!toastElement || !headerEl || !titleEl || !bodyEl || !linkEl || !iconEl || !closeBtn) {
            return;
        }

        bindDraggable(toastElement);

        var expectedInstId = root.getAttribute("data-institucion-id");
        if (expectedInstId === "") expectedInstId = null;

        var reconnectTimer = null;
        var backoffMs = INITIAL_BACKOFF_MS;
        var socket = null;
        var teardown = false;

        function clearReconnectTimer() {
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
        }

        function scheduleReconnect() {
            if (teardown) return;
            clearReconnectTimer();
            reconnectTimer = setTimeout(connectSocket, backoffMs);
            backoffMs = Math.min(MAX_BACKOFF_MS, backoffMs * 2);
        }

        function onMessage(e) {
            var data;
            try {
                data = JSON.parse(e.data);
            } catch (err) {
                return;
            }

            if (
                expectedInstId &&
                data &&
                data.institucion_id != null &&
                String(data.institucion_id) !== String(expectedInstId)
            ) {
                return;
            }

            if (data && typeof data.message === "undefined" && typeof data.body === "string") {
                data.message = data.body;
            }
            var message = (data && data.message) || "";
            var title = (data && data.title) || "Notificación";
            var url = (data && data.url) || "";
            var severity = (data && data.severity) || "info";
            var kind = (data && data.kind) || "generic";

            applySeverity(headerEl, closeBtn, severity);
            setIcon(iconEl, kind);
            titleEl.textContent = title;
            bodyEl.textContent = message;

            if (url) {
                linkEl.href = resolveUrl(url);
                linkEl.classList.remove("d-none");
            } else {
                linkEl.removeAttribute("href");
                linkEl.classList.add("d-none");
            }

            var toast = new bootstrap.Toast(toastElement);
            toast.show();
        }

        function connectSocket() {
            clearReconnectTimer();
            if (teardown) return;

            var scheme = window.location.protocol === "https:" ? "wss://" : "ws://";
            var wsUrl = scheme + window.location.host + "/ws/notifications/";

            try {
                socket = new WebSocket(wsUrl);
            } catch (err) {
                if (window.console && console.warn) {
                    console.warn("HALU: no se pudo abrir WebSocket de notificaciones.", err);
                }
                scheduleReconnect();
                return;
            }

            socket.onopen = function () {
                backoffMs = INITIAL_BACKOFF_MS;
            };

            socket.onmessage = onMessage;

            socket.onerror = function () {
                if (socket && socket.readyState !== WebSocket.CLOSED) {
                    try {
                        socket.close();
                    } catch (e2) {}
                }
            };

            socket.onclose = function () {
                socket = null;
                if (teardown) return;
                if (window.console && console.warn) {
                    console.warn("HALU: socket de notificaciones cerrado; reintentando en " + backoffMs + " ms.");
                }
                scheduleReconnect();
            };
        }

        window.addEventListener("beforeunload", function () {
            teardown = true;
            clearReconnectTimer();
            if (socket && socket.readyState === WebSocket.OPEN) {
                try {
                    socket.close();
                } catch (e3) {}
            }
        });

        connectSocket();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initStaffNotifications);
    } else {
        initStaffNotifications();
    }
})();
