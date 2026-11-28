/*
 * DoubleScreener — renderer condiviso.
 * Trasforma una slide JSON in DOM. Usato da player, canvas ed export.
 * Nessun innerHTML: i contenuti testuali passano da textContent.
 */
(function (global) {
  "use strict";

  const ANIMATIONS = {
    fadeIn: "ds-fadeIn",
    slideUp: "ds-slideUp",
    slideDown: "ds-slideDown",
    slideLeft: "ds-slideLeft",
    slideRight: "ds-slideRight",
    zoomIn: "ds-zoomIn",
    bounce: "ds-bounce",
  };

  const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:", "tel:", "file:"]);

  function px(value) {
    const number = Number(value);
    return `${Number.isFinite(number) ? number : 0}px`;
  }

  function safeUrl(value, allowData) {
    if (!value) return null;
    try {
      const parsed = new URL(value, document.baseURI);
      if (SAFE_PROTOCOLS.has(parsed.protocol)) return value;
      if (allowData && parsed.protocol === "data:" && /^data:image\//i.test(value)) {
        return value;
      }
    } catch (error) {
      return null;
    }
    return null;
  }

  function assetUrl(assetId, options) {
    if (typeof options.assetUrl === "function") return options.assetUrl(assetId);
    return `/api/assets/${encodeURIComponent(assetId)}`;
  }

  function applyBox(node, element) {
    const rect = element.rect || {};
    node.style.position = "absolute";
    node.style.left = px(rect.x);
    node.style.top = px(rect.y);
    node.style.width = px(rect.w);
    node.style.height = px(rect.h);
    node.style.opacity = String(element.opacity == null ? 1 : element.opacity);
    node.style.setProperty(
      "--ds-opacity",
      String(element.opacity == null ? 1 : element.opacity)
    );
    node.style.zIndex = String(element.z || 0);
    if (element.rotation) {
      node.style.transform = `rotate(${Number(element.rotation)}deg)`;
    }
    node.dataset.elementId = element.id;
    node.dataset.elementType = element.type;
    node.classList.add("ds-element", `ds-element-${element.type}`);
  }

  function applyVisual(node, style) {
    const s = style || {};
    node.style.boxSizing = "border-box";
    if (s.font_family) {
      node.style.fontFamily = `"${s.font_family}", system-ui, -apple-system, "Segoe UI", sans-serif`;
    }
    node.style.fontSize = px(s.font_size);
    node.style.fontWeight = String(s.font_weight == null ? 400 : s.font_weight);
    node.style.lineHeight = String(s.line_height == null ? 1.2 : s.line_height);
    node.style.letterSpacing = px(s.letter_spacing);
    node.style.color = s.color || "#ffffff";
    node.style.background = s.background || "transparent";
    node.style.padding = px(s.padding);
    node.style.borderRadius = px(s.border_radius);
    node.style.textAlign = s.text_align || "left";
    if (Number(s.border_width) > 0) {
      node.style.border = `${px(s.border_width)} solid ${s.border_color || "#000000"}`;
    }
    if (s.shadow) {
      node.style.boxShadow = s.shadow;
    }
    node.style.overflow = "hidden";
  }

  function buildElement(element, options) {
    const content = element.content || {};
    let node;

    switch (element.type) {
      case "image": {
        node = document.createElement("img");
        const source = content.asset_id
          ? assetUrl(content.asset_id, options)
          : safeUrl(content.src, true);
        if (source) node.src = source;
        node.alt = content.alt || "";
        node.draggable = false;
        node.decoding = "async";
        node.style.objectFit = (element.style && element.style.object_fit) || "cover";
        break;
      }
      case "button": {
        const href = safeUrl(content.href, false);
        node = document.createElement(href ? "a" : "button");
        if (href) {
          node.href = href;
          node.rel = "noopener noreferrer";
          node.target = "_blank";
        } else {
          node.type = "button";
        }
        node.textContent = content.text || "";
        node.style.display = "flex";
        node.style.alignItems = "center";
        node.style.justifyContent = "center";
        node.style.textDecoration = "none";
        node.style.cursor = href ? "pointer" : "default";
        break;
      }
      case "line": {
        node = document.createElement("div");
        node.style.background = (element.style && element.style.color) || "#ffffff";
        break;
      }
      case "box": {
        node = document.createElement("div");
        break;
      }
      case "text":
      default: {
        node = document.createElement("div");
        node.textContent = content.text || "";
        node.style.whiteSpace = "pre-wrap";
        node.style.wordBreak = "break-word";
        break;
      }
    }

    applyVisual(node, element.style);
    return node;
  }

  function applyAnimation(node, animation, enabled) {
    if (!enabled || !animation || animation.enter === "none") return;
    const name = ANIMATIONS[animation.enter];
    if (!name) return;
    node.style.animationName = name;
    node.style.animationDuration = `${Number(animation.duration_ms) || 0}ms`;
    node.style.animationDelay = `${Number(animation.delay_ms) || 0}ms`;
    node.style.animationTimingFunction = animation.easing || "ease-out";
    node.style.animationFillMode = "both";
  }

  function render(container, slide, options) {
    const opts = options || {};
    const canvas = slide.canvas || { width: 1920, height: 1080, background: "#000000" };
    const canvasWidth = Number(canvas.width) || 1920;
    const canvasHeight = Number(canvas.height) || 1080;

    container.textContent = "";
    container.classList.add("ds-slide");
    container.dataset.slideId = slide.id || "";
    container.dataset.slideKind = slide.kind || "html";
    container.style.width = px(canvasWidth);
    container.style.height = px(canvasHeight);
    container.style.background = slide.background || canvas.background || "#000000";
    container.style.overflow = "hidden";

    if (slide.kind === "pdf_page" && slide.pdf && slide.pdf.image_url) {
      const image = document.createElement("img");
      image.className = "ds-pdf-page";
      image.src = slide.pdf.image_url;
      image.alt = slide.name || "";
      image.draggable = false;
      container.appendChild(image);
    }

    const ordered = (slide.elements || [])
      .map((element, index) => ({ element, index }))
      .sort((a, b) => {
        const delta = (a.element.z || 0) - (b.element.z || 0);
        return delta !== 0 ? delta : a.index - b.index;
      });

    for (const { element } of ordered) {
      if (element.hidden) continue;
      const node = buildElement(element, opts);
      applyBox(node, element);
      applyAnimation(node, element.animation, opts.animate !== false);
      container.appendChild(node);
    }

    return container;
  }

  function preload(slide, options) {
    const opts = options || {};
    const urls = [];
    if (slide.pdf && slide.pdf.image_url) urls.push(slide.pdf.image_url);
    for (const element of slide.elements || []) {
      if (element.type !== "image") continue;
      const content = element.content || {};
      if (content.asset_id) urls.push(assetUrl(content.asset_id, opts));
      else {
        const source = safeUrl(content.src, true);
        if (source) urls.push(source);
      }
    }
    return urls;
  }

  global.DS = Object.freeze({
    version: "1.0.0",
    render,
    preload,
    assetUrl,
  });
})(window);
