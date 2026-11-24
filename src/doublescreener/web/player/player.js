/*
 * DoubleScreener — player del second screen.
 * La regia comanda: il client riceve slide e stato e non naviga mai da solo.
 */
(function () {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const params = new URLSearchParams(window.location.search);
  const explicitLang = params.get("lang");
  const SUPPORTED = ["it", "en"];

  const ui = {
    wrap: byId("stage-wrap"),
    stage: byId("stage"),
    overlay: byId("overlay"),
    overlayTitle: byId("overlay-title"),
    overlayText: byId("overlay-text"),
    retry: byId("retry"),
    controls: byId("controls"),
    status: byId("status"),
    fullscreen: byId("fullscreen"),
    reload: byId("reload"),
  };

  let lang = explicitLang && SUPPORTED.includes(explicitLang) ? explicitLang : null;
  let strings = {};
  let overlayMode = "connecting";
  let overlayDetail = "";
  let session = null;
  let socket = null;
  let attempts = 0;
  let reconnectTimer = null;
  let hideControlsTimer = null;
  let renderToken = 0;
  const pdfCache = new Set();

  const clientId = (() => {
    try {
      let value = window.localStorage.getItem("ds.client_id");
      if (!value) {
        value =
          window.crypto && typeof window.crypto.randomUUID === "function"
            ? window.crypto.randomUUID()
            : `client-${Math.random().toString(36).slice(2)}`;
        window.localStorage.setItem("ds.client_id", value);
      }
      return value;
    } catch (error) {
      return `client-${Math.random().toString(36).slice(2)}`;
    }
  })();

  function t(key, fallback) {
    return strings[key] || fallback || key;
  }

  async function setLang(code, force) {
    if (!SUPPORTED.includes(code)) return;
    if (!force && code === lang && Object.keys(strings).length > 0) return;
    lang = code;
    try {
      const response = await fetch(`/static/player/locales/${code}.json`, {
        cache: "no-cache",
      });
      if (response.ok) strings = await response.json();
    } catch (error) {
      console.warn("locale non caricata", error);
    }
    document.documentElement.lang = code;
    renderOverlay();
  }

  function renderOverlay() {
    if (overlayMode === "hidden") {
      ui.overlay.classList.add("hidden");
      return;
    }
    ui.overlay.classList.remove("hidden");
    const titles = {
      waiting: "waiting.title",
      connecting: "connecting.title",
      error: "error.title",
    };
    const texts = {
      waiting: "waiting.text",
      connecting: "connecting.text",
      error: "error.text",
    };
    ui.overlayTitle.textContent = t(titles[overlayMode] || "connecting.title", "DoubleScreener");
    ui.overlayText.textContent =
      overlayDetail || t(texts[overlayMode] || "connecting.text", "");
    ui.retry.hidden = overlayMode !== "error";
    ui.retry.textContent = t("retry", "Riprova ora");
    ui.fullscreen.title = t("fullscreen", "Schermo intero");
    ui.reload.title = t("reload", "Ricarica");
    ui.fullscreen.setAttribute("aria-label", ui.fullscreen.title);
    ui.reload.setAttribute("aria-label", ui.reload.title);
  }

  function setOverlay(mode, detail) {
    overlayMode = mode;
    overlayDetail = detail || "";
    renderOverlay();
  }

  function hideOverlay() {
    setOverlay("hidden");
  }

  function setStatus(text) {
    ui.status.textContent = text || "";
  }

  function canvasOf() {
    if (session && session.canvas) return session.canvas;
    if (session && session.slide && session.slide.canvas) return session.slide.canvas;
    return null;
  }

  function fit() {
    const canvas = canvasOf();
    if (!canvas) return;
    const scale = Math.min(
      window.innerWidth / canvas.width,
      window.innerHeight / canvas.height
    );
    ui.stage.style.width = `${canvas.width}px`;
    ui.stage.style.height = `${canvas.height}px`;
    ui.stage.style.transform = `translate(-50%, -50%) scale(${scale})`;
  }

  function applyTransition(transition) {
    const type = transition && transition.type ? transition.type : "none";
    const duration = transition ? Number(transition.duration_ms) || 0 : 0;
    ui.wrap.classList.remove(
      "ds-transition-fade",
      "ds-transition-slide",
      "ds-transition-zoom"
    );
    ui.wrap.style.animation = "none";
    void ui.wrap.offsetWidth;
    ui.wrap.style.animation = "";
    if (type === "none" || duration <= 0) return;
    ui.wrap.style.animationDuration = `${duration}ms`;
    ui.wrap.classList.add(`ds-transition-${type}`);
  }

  function preloadImage(url, timeoutMs) {
    return new Promise((resolve) => {
      if (!url) {
        resolve(false);
        return;
      }
      const image = new Image();
      let settled = false;
      const finish = (ok) => {
        if (settled) return;
        settled = true;
        image.onload = null;
        image.onerror = null;
        resolve(ok);
      };
      image.onload = () => finish(true);
      image.onerror = () => finish(false);
      image.src = url;
      window.setTimeout(() => finish(false), timeoutMs || 8000);
    });
  }

  async function showSlide(message) {
    if (!message || !message.slide) return;
    const slide = message.slide;
    const index = typeof message.index === "number" ? message.index : slide.index || 0;
    const token = ++renderToken;
    const pdfUrl =
      slide.kind === "pdf_page" && slide.pdf ? slide.pdf.image_url : null;

    if (pdfUrl && !pdfCache.has(pdfUrl)) {
      if (session && session.slide) setStatus(t("status.rendering", "Rendering…"));
      const loaded = await preloadImage(pdfUrl);
      if (token !== renderToken) return;
      if (loaded) pdfCache.add(pdfUrl);
    }
    if (token !== renderToken) return;

    session = session
      ? { ...session, canvas: slide.canvas, slide, index }
      : { canvas: slide.canvas, slide, index, state: {} };

    window.DS.render(ui.stage, slide, {
      assetUrl: (assetId) => `/api/assets/${encodeURIComponent(assetId)}`,
      animate: true,
    });
    fit();
    applyTransition(message.transition || slide.transition);
    hideOverlay();
    setStatus("");

    (message.prefetch || []).forEach((url) => {
      const image = new Image();
      image.src = url;
    });

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ack", index }));
    }
  }

  function applyState(state) {
    if (!state) return;
    if (session) session.state = { ...(session.state || {}), ...state };
    const black = Boolean(state.black);
    document.body.classList.toggle("is-black", black);
    if (black) {
      setStatus(t("status.black", "Schermo nero"));
      return;
    }
    if (!session || !session.slide) setOverlay("waiting");
    else setStatus("");
  }

  function handleSession(message) {
    session = message;
    if (!explicitLang && message.lang) setLang(message.lang);
    if (message.slide) {
      showSlide({
        slide: message.slide,
        index: message.index,
        transition: message.slide.transition,
        prefetch: [],
      });
    } else {
      ui.stage.textContent = "";
      setOverlay("waiting");
    }
    applyState(message.state);
  }

  function handleMessage(message) {
    switch (message.type) {
      case "session":
        handleSession(message);
        break;
      case "slide":
        showSlide(message);
        break;
      case "state":
        applyState(message);
        break;
      case "reload":
        window.location.reload();
        break;
      case "ping":
        if (socket && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "pong", t: message.t }));
        }
        break;
      case "error":
        setOverlay("error", message.message || "");
        break;
      default:
        break;
    }
  }

  function wsUrl() {
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}//${window.location.host}/ws/player`;
  }

  function connect() {
    window.clearTimeout(reconnectTimer);
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      try {
        socket.close();
      } catch (error) {
        /* ignore */
      }
    }

    const ws = new WebSocket(wsUrl());
    socket = ws;
    if (!session || !session.slide) setOverlay("connecting");
    setStatus(t("status.connecting", "Connessione…"));

    ws.onopen = () => {
      if (socket !== ws) return;
      attempts = 0;
      setStatus("");
      ws.send(
        JSON.stringify({ type: "hello", protocol: 1, client_id: clientId, role: "player" })
      );
    };

    ws.onmessage = (event) => {
      if (socket !== ws) return;
      let message;
      try {
        message = JSON.parse(event.data);
      } catch (error) {
        return;
      }
      handleMessage(message);
    };

    ws.onclose = () => {
      if (socket !== ws) return;
      if (session && session.slide) setStatus(t("status.reconnecting", "Riconnessione…"));
      else setOverlay("connecting");
      scheduleReconnect();
    };

    ws.onerror = () => {
      try {
        ws.close();
      } catch (error) {
        /* ignore */
      }
    };
  }

  function scheduleReconnect() {
    const delay =
      Math.min(5000, 500 * Math.pow(2, Math.min(attempts, 4))) + Math.random() * 250;
    attempts += 1;
    window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(connect, delay);
  }

  function revealControls() {
    ui.controls.classList.add("visible");
    window.clearTimeout(hideControlsTimer);
    hideControlsTimer = window.setTimeout(() => {
      ui.controls.classList.remove("visible");
    }, 2500);
  }

  async function toggleFullscreen() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (error) {
      console.warn("fullscreen non disponibile", error);
    }
  }

  ui.retry.addEventListener("click", () => {
    attempts = 0;
    connect();
  });
  ui.reload.addEventListener("click", () => window.location.reload());
  ui.fullscreen.addEventListener("click", toggleFullscreen);

  document.addEventListener("mousemove", revealControls);
  document.addEventListener("touchstart", revealControls, { passive: true });
  document.addEventListener("dblclick", toggleFullscreen);
  document.addEventListener("keydown", (event) => {
    if (event.key === "f" || event.key === "F") toggleFullscreen();
    if (event.key === "r" || event.key === "R") window.location.reload();
    if (event.key === "Escape" && document.fullscreenElement) document.exitFullscreen();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    if (!socket || socket.readyState > WebSocket.OPEN) connect();
  });
  window.addEventListener("resize", fit);

  async function init() {
    await setLang(lang || "it", true);
    setOverlay("connecting");
    connect();
  }

  init();
})();
