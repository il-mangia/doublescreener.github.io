/*
 * DoubleScreener — canvas di editing.
 * Il canvas non è mai fonte di verità: riceve lo stato dalla regia e invia
 * intenti. In assenza di Qt resta in sola visualizzazione.
 */
(function () {
  "use strict";

  const els = {
    viewport: document.getElementById("viewport"),
    holder: document.getElementById("holder"),
    stage: document.getElementById("stage"),
    grid: document.getElementById("grid"),
    overlay: document.getElementById("overlay"),
    guides: document.getElementById("guides"),
    banner: document.getElementById("banner"),
    hint: document.getElementById("hint"),
  };

  const state = {
    slide: null,
    canvas: { width: 1920, height: 1080, background: "#000000" },
    selection: [],
    zoom: 1,
    grid: false,
    lang: "it",
  };

  let bridge = null;
  let scale = 1;
  let panX = 0;
  let panY = 0;
  let interaction = null;
  let editing = null;
  let pendingFrame = 0;

  // -- infrastruttura -----------------------------------------------------

  function send(action, payload) {
    if (!bridge) return;
    bridge.intent(JSON.stringify({ action, payload: payload || {} }));
  }

  function canvasOf() {
    return state.canvas || (state.slide && state.slide.canvas) || { width: 1920, height: 1080 };
  }

  function byId(elementId) {
    if (!state.slide) return null;
    return (state.slide.elements || []).find((element) => element.id === elementId) || null;
  }

  function nodeOf(elementId) {
    const nodes = els.stage.querySelectorAll("[data-element-id]");
    for (const node of nodes) {
      if (node.dataset.elementId === elementId) return node;
    }
    return null;
  }

  function setBanner(text) {
    if (!text) {
      els.banner.classList.add("hidden");
      return;
    }
    els.banner.textContent = text;
    els.banner.classList.remove("hidden");
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function round(value) {
    return Math.round(value * 100) / 100;
  }

  // -- canale Qt ----------------------------------------------------------

  function initChannel() {
    if (!window.qt || !window.qt.webChannelTransport || typeof window.QWebChannel !== "function") {
      setBanner("Anteprima canvas: apri dalla regia per modificare");
      return;
    }
    new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
      bridge = channel.objects.bridge;
      bridge.stateChanged.connect(onStateJson);
      setBanner("");
      send("ready");
    });
  }

  function onStateJson(raw) {
    let message;
    try {
      message = JSON.parse(raw);
    } catch (error) {
      return;
    }
    switch (message.type) {
      case "render_slide":
        renderSlide(message);
        break;
      case "patch_element":
        patchElement(message);
        break;
      case "selection":
        state.selection = Array.isArray(message.ids) ? message.ids : [];
        renderOverlay();
        break;
      case "zoom":
        state.zoom = Number(message.zoom) || 1;
        fit();
        break;
      case "grid":
        setGrid(Boolean(message.on));
        break;
      case "lang":
        state.lang = message.lang || state.lang;
        document.documentElement.lang = state.lang;
        break;
      default:
        break;
    }
  }

  // -- rendering ----------------------------------------------------------

  function renderSlide(message) {
    const slide = message.slide;
    if (!slide) return;
    state.slide = slide;
    state.canvas = slide.canvas || state.canvas;
    state.selection = Array.isArray(message.selection) ? message.selection : [];
    state.zoom = Number(message.zoom) || state.zoom;
    if (message.lang) {
      state.lang = message.lang;
      document.documentElement.lang = state.lang;
    }

    const canvas = canvasOf();
    els.holder.style.width = `${canvas.width}px`;
    els.holder.style.height = `${canvas.height}px`;
    els.grid.style.backgroundSize = `${40 * (canvas.width / 1920)}px ${40 * (canvas.height / 1080)}px`;

    window.DS.render(els.stage, slide, {
      assetUrl: (assetId) => `/api/assets/${encodeURIComponent(assetId)}`,
      animate: false,
    });
    setGrid(Boolean(message.grid));

    renderOverlay();
    fit();
    setBanner("");
    window.requestAnimationFrame(drawOverlay);
  }

  function patchElement(message) {
    if (!state.slide) return;
    const element = byId(message.id);
    if (!element) return;
    Object.assign(element, message.element || {});
    renderSlide({ slide: state.slide, canvas: state.canvas, selection: state.selection, zoom: state.zoom });
    renderOverlay();
  }

  function setGrid(on) {
    state.grid = on;
    els.grid.hidden = !on;
  }

  function fit() {
    const canvas = canvasOf();
    const padding = 48;
    const availableWidth = Math.max(120, els.viewport.clientWidth - padding * 2);
    const availableHeight = Math.max(120, els.viewport.clientHeight - padding * 2);
    const base = Math.min(availableWidth / canvas.width, availableHeight / canvas.height);
    scale = Math.max(0.02, base * state.zoom);
    els.holder.style.width = `${canvas.width}px`;
    els.holder.style.height = `${canvas.height}px`;
    applyTransform();
    renderOverlay();
  }

  function applyTransform() {
    els.holder.style.transform =
      `translate(calc(-50% + ${panX}px), calc(-50% + ${panY}px)) scale(${scale})`;
  }

  // -- overlay ------------------------------------------------------------

  function renderOverlay() {
    if (pendingFrame) return;
    pendingFrame = window.requestAnimationFrame(() => {
      pendingFrame = 0;
      drawOverlay();
    });
  }

  function drawOverlay() {
    els.overlay.textContent = "";
    if (!state.slide) return;
    for (const id of state.selection) {
      const element = byId(id);
      if (!element || element.hidden) continue;
      const rect = element.rect;
      const box = document.createElement("div");
      box.className = "sel-box";
      box.dataset.elementId = id;
      box.style.left = `${rect.x}px`;
      box.style.top = `${rect.y}px`;
      box.style.width = `${rect.w}px`;
      box.style.height = `${rect.h}px`;
      if (element.rotation) {
        box.style.transform = `rotate(${element.rotation}deg)`;
      }
      if (state.selection.length === 1) {
        addHandles(box);
      }
      els.overlay.appendChild(box);
    }
  }

  function addHandles(box) {
    const points = [
      ["nw", 0, 0],
      ["n", 50, 0],
      ["ne", 100, 0],
      ["e", 100, 50],
      ["se", 100, 100],
      ["s", 50, 100],
      ["sw", 0, 100],
      ["w", 0, 50],
      ["rot", 50, -7],
    ];
    for (const [role, x, y] of points) {
      const handle = document.createElement("div");
      handle.className = "handle";
      handle.dataset.role = role;
      handle.style.left = `${x}%`;
      handle.style.top = `${y}%`;
      box.appendChild(handle);
    }
  }

  function drawGuides(guides) {
    els.guides.textContent = "";
    for (const guide of guides || []) {
      const line = document.createElement("div");
      line.className = `guide ${guide.axis}`;
      if (guide.axis === "v") line.style.left = `${guide.pos}px`;
      else line.style.top = `${guide.pos}px`;
      els.guides.appendChild(line);
    }
  }

  // -- coordinate ---------------------------------------------------------

  function toCanvas(event) {
    const rect = els.stage.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) / scale,
      y: (event.clientY - rect.top) / scale,
    };
  }

  function elementAt(target) {
    const node = target && target.closest ? target.closest("[data-element-id]") : null;
    return node ? node.dataset.elementId : null;
  }

  // -- snap ---------------------------------------------------------------

  function snapMove(rect) {
    const canvas = canvasOf();
    const threshold = 6 / scale;
    const xTargets = [0, canvas.width / 2, canvas.width];
    const yTargets = [0, canvas.height / 2, canvas.height];
    for (const element of state.slide.elements || []) {
      if (state.selection.includes(element.id) || element.hidden) continue;
      const r = element.rect;
      xTargets.push(r.x, r.x + r.w / 2, r.x + r.w);
      yTargets.push(r.y, r.y + r.h / 2, r.y + r.h);
    }
    const movingX = [rect.x, rect.x + rect.w / 2, rect.x + rect.w];
    const movingY = [rect.y, rect.y + rect.h / 2, rect.y + rect.h];

    let bestX = null;
    for (const target of xTargets) {
      for (const edge of movingX) {
        const delta = target - edge;
        if (Math.abs(delta) <= threshold && (!bestX || Math.abs(delta) < Math.abs(bestX.delta))) {
          bestX = { delta, pos: target };
        }
      }
    }
    let bestY = null;
    for (const target of yTargets) {
      for (const edge of movingY) {
        const delta = target - edge;
        if (Math.abs(delta) <= threshold && (!bestY || Math.abs(delta) < Math.abs(bestY.delta))) {
          bestY = { delta, pos: target };
        }
      }
    }

    if (state.grid) {
      const stepX = 40 * (canvas.width / 1920);
      const stepY = 40 * (canvas.height / 1080);
      if (!bestX) {
        const target = Math.round(rect.x / stepX) * stepX;
        if (Math.abs(target - rect.x) <= threshold) {
          bestX = { delta: target - rect.x, pos: target };
        }
      }
      if (!bestY) {
        const target = Math.round(rect.y / stepY) * stepY;
        if (Math.abs(target - rect.y) <= threshold) {
          bestY = { delta: target - rect.y, pos: target };
        }
      }
    }
    const guides = [];
    if (bestX) guides.push({ axis: "v", pos: bestX.pos });
    if (bestY) guides.push({ axis: "h", pos: bestY.pos });
    return { dx: bestX ? bestX.delta : 0, dy: bestY ? bestY.delta : 0, guides };
  }

  // -- selezione ----------------------------------------------------------

  function setSelection(ids) {
    state.selection = Array.from(new Set(ids));
    renderOverlay();
    send("selection.change", { ids: state.selection });
  }

  function selectOnly(id, additive) {
    if (!id) {
      setSelection(additive ? state.selection : []);
      return;
    }
    if (additive) {
      const next = state.selection.includes(id)
        ? state.selection.filter((item) => item !== id)
        : [...state.selection, id];
      setSelection(next);
    } else {
      setSelection([id]);
    }
  }

  // -- interazioni --------------------------------------------------------

  function beginMove(event, id) {
    if (editing) return;
    const additive = event.shiftKey;
    if (!state.selection.includes(id)) {
      selectOnly(id, additive);
    } else if (additive) {
      selectOnly(id, true);
      return;
    }
    if (!state.selection.includes(id)) return;
    event.preventDefault();

    const origin = toCanvas(event);
    const originals = {};
    for (const selected of state.selection) {
      const element = byId(selected);
      if (element) originals[selected] = { ...element.rect };
    }
    interaction = { type: "move", origin, originals, moved: false };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp, { once: true });
  }

  function beginResize(event, id, role) {
    const element = byId(id);
    if (!element) return;
    event.preventDefault();
    event.stopPropagation();
    const origin = toCanvas(event);
    interaction = {
      type: role === "rot" ? "rotate" : "resize",
      role,
      id,
      origin,
      original: { ...element.rect },
      rotation: element.rotation || 0,
      moved: false,
    };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp, { once: true });
  }

  function beginMarquee(event) {
    if (event.button !== 0) return;
    if (editing) return;
    const start = toCanvas(event);
    const additive = event.shiftKey;
    const base = additive ? [...state.selection] : [];
    if (!additive) setSelection([]);

    const marquee = document.createElement("div");
    marquee.className = "marquee";
    els.overlay.appendChild(marquee);
    interaction = { type: "marquee", start, marquee, base };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp, { once: true });
  }

  function onPointerMove(event) {
    if (!interaction) return;
    const point = toCanvas(event);
    if (interaction.type === "move") {
      let dx = point.x - interaction.origin.x;
      let dy = point.y - interaction.origin.y;
      const primary = byId(state.selection[0]);
      let guides = [];
      if (primary) {
        const tentative = { ...interaction.originals[primary.id], x: interaction.originals[primary.id].x + dx, y: interaction.originals[primary.id].y + dy };
        const snap = snapMove(tentative);
        dx += snap.dx;
        dy += snap.dy;
        guides = snap.guides;
      }
      if (dx !== 0 || dy !== 0) interaction.moved = true;
      for (const [id, rect] of Object.entries(interaction.originals)) {
        const element = byId(id);
        if (!element) continue;
        element.rect = { ...rect, x: round(rect.x + dx), y: round(rect.y + dy) };
        const node = nodeOf(id);
        if (node) {
          node.style.left = `${element.rect.x}px`;
          node.style.top = `${element.rect.y}px`;
        }
      }
      drawGuides(guides);
      renderOverlay();
      return;
    }

    if (interaction.type === "resize") {
      resizeTo(point);
      return;
    }

    if (interaction.type === "rotate") {
      const element = byId(interaction.id);
      if (!element) return;
      const rect = interaction.original;
      const centerX = rect.x + rect.w / 2;
      const centerY = rect.y + rect.h / 2;
      const angle = (Math.atan2(point.y - centerY, point.x - centerX) * 180) / Math.PI + 90;
      const rotation = round(((angle + 180) % 360) - 180);
      element.rotation = rotation;
      const node = nodeOf(interaction.id);
      if (node) node.style.transform = `rotate(${rotation}deg)`;
      interaction.moved = true;
      renderOverlay();
      return;
    }

    if (interaction.type === "pan") {
      panX = interaction.panX + (event.clientX - interaction.start.x);
      panY = interaction.panY + (event.clientY - interaction.start.y);
      applyTransform();
      return;
    }

    if (interaction.type === "marquee") {
      const start = interaction.start;
      const rect = {
        x: Math.min(start.x, point.x),
        y: Math.min(start.y, point.y),
        w: Math.abs(point.x - start.x),
        h: Math.abs(point.y - start.y),
      };
      interaction.rect = rect;
      interaction.marquee.style.left = `${rect.x}px`;
      interaction.marquee.style.top = `${rect.y}px`;
      interaction.marquee.style.width = `${rect.w}px`;
      interaction.marquee.style.height = `${rect.h}px`;
      const hits = (state.slide.elements || [])
        .filter((element) => !element.hidden && intersects(rect, element.rect))
        .map((element) => element.id);
      state.selection = Array.from(new Set([...interaction.base, ...hits]));
      renderOverlay();
    }
  }

  function intersects(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function resizeTo(point) {
    const element = byId(interaction.id);
    if (!element) return;
    const original = interaction.original;
    const role = interaction.role;
    const minSize = 8;
    let left = original.x;
    let top = original.y;
    let right = original.x + original.w;
    let bottom = original.y + original.h;

    if (role.includes("w")) left = Math.min(point.x, right - minSize);
    if (role.includes("e")) right = Math.max(point.x, left + minSize);
    if (role.includes("n")) top = Math.min(point.y, bottom - minSize);
    if (role.includes("s")) bottom = Math.max(point.y, top + minSize);

    const rect = { x: round(left), y: round(top), w: round(right - left), h: round(bottom - top) };
    element.rect = rect;
    const node = nodeOf(interaction.id);
    if (node) {
      node.style.left = `${rect.x}px`;
      node.style.top = `${rect.y}px`;
      node.style.width = `${rect.w}px`;
      node.style.height = `${rect.h}px`;
    }
    interaction.moved = true;
    renderOverlay();
  }

  function onPointerUp() {
    window.removeEventListener("pointermove", onPointerMove);
    const current = interaction;
    interaction = null;
    drawGuides([]);
    if (!current) return;

    if (current.type === "move" && current.moved) {
      for (const id of Object.keys(current.originals)) {
        const element = byId(id);
        if (element) send("element.update", { id, changes: { rect: element.rect } });
      }
      send("selection.change", { ids: state.selection });
    } else if (current.type === "resize" && current.moved) {
      const element = byId(current.id);
      if (element) send("element.update", { id: current.id, changes: { rect: element.rect } });
    } else if (current.type === "rotate" && current.moved) {
      const element = byId(current.id);
      if (element) send("element.update", { id: current.id, changes: { rotation: element.rotation || 0 } });
    } else if (current.type === "marquee") {
      send("selection.change", { ids: state.selection });
    }
  }

  // -- testo inline -------------------------------------------------------

  function beginTextEdit(event, id) {
    const element = byId(id);
    if (!element || (element.type !== "text" && element.type !== "button")) return;
    event.preventDefault();
    event.stopPropagation();
    const node = nodeOf(id);
    if (!node) return;

    editing = {
      id,
      original: element.content.text || "",
      node,
      content: { ...element.content },
    };
    node.contentEditable = "true";
    node.focus();
    const range = document.createRange();
    range.selectNodeContents(node);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);

    node.addEventListener("keydown", onEditKeyDown);
    node.addEventListener("blur", commitTextEdit, { once: true });
  }

  function onEditKeyDown(event) {
    if (!editing) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      editing.node.textContent = editing.original;
      cancelTextEdit();
    } else if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      editing.node.blur();
    }
  }

  function cancelTextEdit() {
    if (!editing) return;
    const node = editing.node;
    node.contentEditable = "false";
    node.removeEventListener("keydown", onEditKeyDown);
    editing = null;
    node.blur();
  }

  function commitTextEdit() {
    if (!editing) return;
    const current = editing;
    editing = null;
    current.node.contentEditable = "false";
    current.node.removeEventListener("keydown", onEditKeyDown);

    const text = current.node.textContent || "";
    if (text === current.original) return;
    const element = byId(current.id);
    if (!element) return;
    const content = { ...element.content, ...current.content, text };
    element.content = content;
    send("text.edit", { id: current.id, content });
  }

  // -- tastiera e zoom ----------------------------------------------------

  function moveSelection(dx, dy) {
    if (!state.selection.length) return;
    for (const id of state.selection) {
      const element = byId(id);
      if (!element) continue;
      element.rect = { ...element.rect, x: round(element.rect.x + dx), y: round(element.rect.y + dy) };
      const node = nodeOf(id);
      if (node) {
        node.style.left = `${element.rect.x}px`;
        node.style.top = `${element.rect.y}px`;
      }
      send("element.update", { id, changes: { rect: element.rect } });
    }
    renderOverlay();
  }

  function onKeyDown(event) {
    if (editing) return;
    const tag = (document.activeElement && document.activeElement.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA") return;

    const arrows = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    if (arrows[event.key] && state.selection.length) {
      event.preventDefault();
      const factor = event.shiftKey ? 10 : 1;
      moveSelection(arrows[event.key][0] * factor, arrows[event.key][1] * factor);
      return;
    }
    if ((event.key === "Delete" || event.key === "Backspace") && state.selection.length) {
      event.preventDefault();
      send("element.delete", { ids: state.selection });
      setSelection([]);
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") {
      if (!state.selection.length) return;
      event.preventDefault();
      send("element.duplicate", { ids: state.selection });
      return;
    }
    if ((event.ctrlKey || event.metaKey) && (event.key === "]" || event.key === "[")) {
      if (!state.selection.length) return;
      event.preventDefault();
      send("element.reorder", { ids: state.selection, direction: event.key === "]" ? 1 : -1 });
      return;
    }
    if (event.key === "Escape") {
      setSelection([]);
    }
  }

  function onWheel(event) {
    if (!event.ctrlKey) return;
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    state.zoom = clamp(state.zoom * factor, 0.25, 2);
    fit();
    send("zoom.change", { zoom: round(state.zoom) });
  }

  // -- eventi DOM ---------------------------------------------------------

  els.stage.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    if (event.target.isContentEditable) return;
    const id = elementAt(event.target);
    if (id) {
      beginMove(event, id);
    } else {
      beginMarquee(event);
    }
  });

  els.stage.addEventListener("dblclick", (event) => {
    const id = elementAt(event.target);
    if (id) beginTextEdit(event, id);
  });

  els.overlay.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest ? event.target.closest(".handle") : null;
    if (!handle) return;
    const box = handle.closest(".sel-box");
    if (!box) return;
    beginResize(event, box.dataset.elementId, handle.dataset.role);
  });

  window.addEventListener("keydown", onKeyDown);
  els.viewport.addEventListener("wheel", onWheel, { passive: false });
  els.viewport.addEventListener("pointerdown", (event) => {
    if (event.button !== 1) return;
    event.preventDefault();
    interaction = {
      type: "pan",
      start: { x: event.clientX, y: event.clientY },
      panX,
      panY,
    };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp, { once: true });
  });
  window.addEventListener("resize", fit);

  initChannel();
  fit();
})();
