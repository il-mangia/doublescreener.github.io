/* DoubleScreener — landing page: lingua, tema e piccole interazioni. */
(function () {
  "use strict";

  var I18N = {
    it: {
      "meta.title": "DoubleScreener — Regia desktop per presentazioni su due schermi",
      "meta.description": "DoubleScreener è una regia desktop open source per creare slide HTML, importare PDF e proiettarle su TV, tablet e altri PC tramite browser, sulla rete locale.",

      "a11y.skip": "Vai al contenuto",
      "a11y.nav": "Navigazione principale",
      "a11y.lang": "Lingua / Language",
      "a11y.theme": "Cambia tema",

      "nav.about": "Il progetto",
      "nav.features": "Funzionalità",
      "nav.how": "Come funziona",
      "nav.install": "Installa",
      "nav.status": "Stato",

      "hero.eyebrow": "Applicazione desktop · Open source",
      "hero.title": "La regia delle tue presentazioni, <span class=\"grad\">su ogni schermo.</span>",
      "hero.lead": "DoubleScreener unisce un editor visuale per slide HTML a un secondo schermo che vive nel browser. Gira sul tuo computer, senza cloud e senza account: TV, tablet e altri PC si collegano dalla rete locale.",
      "hero.cta.install": "Come installarlo",
      "hero.cta.github": "Vedi su GitHub",
      "hero.chip.os": "Windows · Linux · macOS",
      "hero.chip.python": "Python 3.11+",
      "hero.chip.account": "Nessun account",
      "hero.chip.license": "GPL-3.0",

      "mock.title": "DoubleScreener · regia",
      "mock.slides": "Slide",
      "mock.inspector": "Inspector",
      "mock.live": "Player connesso",
      "mock.screens": "schermi collegati",
      "mock.qr": "collega uno schermo",

      "notice.retired": "<strong>La demo web non c'è più.</strong> DoubleScreener v2 è un'applicazione locale: la regia gira sul tuo computer e il browser serve solo come secondo schermo.",

      "about.eyebrow": "Il progetto",
      "about.title": "Una regia, nessun cloud.",
      "about.lead": "DoubleScreener nasce per proiettare contenuti su un secondo schermo senza passare da servizi online. Tutto ciò che serve — progetti, immagini, pagine PDF — resta sul computer che apre la presentazione.",
      "about.c1.title": "Locale per scelta",
      "about.c1.text": "Niente database, login o sincronizzazione remota: i progetti sono file JSON sul disco e il server ascolta solo sulla rete locale.",
      "about.c2.title": "Un solo renderer",
      "about.c2.text": "Canvas, player ed export condividono lo stesso codice di rendering: quello che vedi in regia è esattamente ciò che arriva sullo schermo.",
      "about.c3.title": "Aperto e tradotto",
      "about.c3.text": "Codice GPL-3.0, documentazione tecnica inclusa e interfaccia in italiano e inglese. Nessun componente proprietario.",

      "features.eyebrow": "Funzionalità",
      "features.title": "Tutto quello che serve per proiettare.",
      "features.lead": "Editor, PDF, secondo schermo ed export in un'unica applicazione.",
      "f1.title": "Regia desktop nativa",
      "f1.text": "Costruita con PyQt6: pannelli progetti e slide, ispettore, palette e canvas HTML5. Niente schede del browser da tenere aperte.",
      "f2.title": "Slide HTML e PDF",
      "f2.text": "Crea slide da zero o importa pagine da un PDF a intervalli. Le pagine vengono renderizzate lato server in immagini leggere, pronte per il player.",
      "f3.title": "Editing visuale",
      "f3.text": "Trascina, ridimensiona e ruota gli elementi con snap e guide. Zoom 25–200%, testo modificabile inline, annulla/ripristina e salvataggio automatico.",
      "f4.title": "Inspector completo",
      "f4.text": "Geometria, rotazione, opacità e livello; tipografia, colori e allineamento; sfondo, bordo, raggio, ombra e animazioni d'ingresso.",
      "f5.title": "Template e temi",
      "f5.text": "Cinque layout pronti — titolo, titolo e sottotitolo, elenco, immagine a tutto schermo, due colonne — e quattro temi colore applicabili al progetto.",
      "f6.title": "Second screen, zero app",
      "f6.text": "TV, tablet o un altro PC aprono il player nel browser. Un QR code li collega; ogni schermo mostra la stessa slide, e con un tasto va in nero.",
      "f7.title": "Export autonomo",
      "f7.text": "Esporta il deck come cartella statica o come singolo file HTML con asset inclusi: si apre da file:// anche su un computer senza DoubleScreener.",
      "f8.title": "Il tuo spazio locale",
      "f8.text": "Progetti in JSON, asset in una cartella dedicata, nessun tracciamento. Interfaccia e player disponibili in italiano e inglese.",

      "how.eyebrow": "Come funziona",
      "how.title": "Tre pezzi, una sola presentazione.",
      "how.lead": "La regia è l'unica fonte di verità. Tutto il resto si limita a mostrare la slide corrente.",
      "flow.regia.title": "Regia",
      "flow.regia.text": "Editor PyQt6 con canvas, inspector e anteprima.",
      "flow.server.title": "Server locale",
      "flow.server.text": "FastAPI + Uvicorn sincronizza lo stato via WebSocket.",
      "flow.screen.title": "Second screen",
      "flow.screen.text": "Qualsiasi browser sulla rete locale, anche una Smart TV.",
      "step1.title": "Avvia la regia",
      "step1.text": "Apri DoubleScreener sul computer collegato al proiettore o alla TV.",
      "step2.title": "Collega lo schermo",
      "step2.text": "Inquadra il QR dal pannello Presentazione, oppure apri l'indirizzo LAN nel browser.",
      "step3.title": "Presenta",
      "step3.text": "Crea le slide, premi F5 e naviga con le frecce. Gli schermi restano allineati.",

      "install.eyebrow": "Installa",
      "install.title": "Da sorgente, in pochi minuti.",
      "install.lead": "DoubleScreener v2 è in sviluppo attivo: per ora si installa da sorgente. Servono Python 3.11+ e Git.",
      "install.req.title": "Requisiti",
      "install.req1": "<strong>Python 3.11+</strong> — testato su Python 3.13.",
      "install.req2": "<strong>Windows, Linux o macOS</strong> — su Linux servono le librerie Qt/WebEngine della distribuzione.",
      "install.req3": "<strong>Nessun Node.js</strong> — il frontend è già incluso nel pacchetto.",
      "install.note": "Il codice della v2 è su <code>main</code>. Il progetto è ancora in sviluppo: non ci sono release pacchettizzate.",
      "install.copy": "Copia",
      "install.copied": "Copiato",
      "install.after.title": "Poi…",
      "install.after.text": "Con la regia aperta, il pannello Presentazione mostra l'indirizzo per il secondo schermo (ad esempio <code>http://192.168.1.20:8765/p</code>) e il QR code. I dati vengono salvati nella cartella utente dell'app; usa <code>--data-dir</code> per sceglierne un'altra.",

      "status.eyebrow": "Stato",
      "status.title": "Dove siamo.",
      "status.lead": "La v2 è utilizzabile da sorgente. Manca il packaging: non ci sono ancora installer o release scaricabili.",
      "status.done.title": "Disponibile ora",
      "status.done1": "Editor visuale con inspector, palette, template e temi",
      "status.done2": "Slide HTML e import PDF con intervalli di pagine",
      "status.done3": "Second screen live con QR, sincronizzazione e schermo nero",
      "status.done4": "Export in cartella o file singolo e import progetto JSON",
      "status.done5": "Interfaccia IT/EN, tema scuro e chiaro, diagnostica",
      "status.done6": "Documentazione: architettura, API, protocollo WebSocket, setup",
      "status.next.title": "In programma",
      "status.next1": "Packaging Windows: installer e versione portable",
      "status.next2": "Modalità video, camera e pagine web",
      "status.next3": "Note relatore, multi-view e export PDF del deck",
      "status.next4": "QA su Windows, browser e Smart TV, poi tag v2.0.0",
      "status.note": "Il piano di lavoro, le decisioni tecniche e i limiti noti sono nel <a href=\"https://github.com/il-mangia/doublescreener.github.io/blob/main/work.md\" target=\"_blank\" rel=\"noopener\">work.md</a> del repository.",

      "footer.tagline": "Regia desktop e second screen per presentazioni HTML e PDF. Locale, open source, senza cloud.",
      "footer.project": "Progetto",
      "footer.github": "Repository GitHub",
      "footer.issues": "Segnala un problema",
      "footer.readme": "README",
      "footer.license": "Licenza GPL-3.0",
      "footer.docs": "Documentazione",
      "footer.docs.setup": "Setup e sviluppo",
      "footer.docs.architecture": "Architettura",
      "footer.docs.api": "API REST",
      "footer.docs.ws": "Protocollo WebSocket",
      "footer.tech": "Costruito con",
      "footer.legal": "Software libero distribuito con licenza <strong>GPL-3.0-only</strong>.",
      "footer.credits": "Copyright © 2026 il-mangia e contributori di DoubleScreener.",
      "footer.privacy": "Nessun cookie, nessun tracciamento: questa pagina è statica."
    },

    en: {
      "meta.title": "DoubleScreener — Desktop control room for two-screen presentations",
      "meta.description": "DoubleScreener is an open-source desktop control room to build HTML slides, import PDFs and project them to TVs, tablets and other PCs through a browser, on your local network.",

      "a11y.skip": "Skip to content",
      "a11y.nav": "Main navigation",
      "a11y.lang": "Language / Lingua",
      "a11y.theme": "Toggle theme",

      "nav.about": "The project",
      "nav.features": "Features",
      "nav.how": "How it works",
      "nav.install": "Install",
      "nav.status": "Status",

      "hero.eyebrow": "Desktop application · Open source",
      "hero.title": "Your presentation control room, <span class=\"grad\">on every screen.</span>",
      "hero.lead": "DoubleScreener pairs a visual HTML slide editor with a second screen that runs in the browser. It lives on your computer, with no cloud and no account: TVs, tablets and other PCs join over the local network.",
      "hero.cta.install": "How to install",
      "hero.cta.github": "View on GitHub",
      "hero.chip.os": "Windows · Linux · macOS",
      "hero.chip.python": "Python 3.11+",
      "hero.chip.account": "No account",
      "hero.chip.license": "GPL-3.0",

      "mock.title": "DoubleScreener · editor",
      "mock.slides": "Slides",
      "mock.inspector": "Inspector",
      "mock.live": "Player connected",
      "mock.screens": "screens connected",
      "mock.qr": "connect a screen",

      "notice.retired": "<strong>The web demo is gone.</strong> DoubleScreener v2 is a local application: the control room runs on your computer and the browser only acts as the second screen.",

      "about.eyebrow": "The project",
      "about.title": "One control room, no cloud.",
      "about.lead": "DoubleScreener was built to project content to a second screen without going through online services. Everything it needs — projects, images, PDF pages — stays on the computer running the presentation.",
      "about.c1.title": "Local by design",
      "about.c1.text": "No database, login or remote sync: projects are JSON files on disk and the server only listens on the local network.",
      "about.c2.title": "One renderer",
      "about.c2.text": "Canvas, player and export share the same rendering code: what you see in the control room is exactly what reaches the screen.",
      "about.c3.title": "Open and translated",
      "about.c3.text": "GPL-3.0 code, technical documentation included and an Italian/English interface. No proprietary components.",

      "features.eyebrow": "Features",
      "features.title": "Everything you need to project.",
      "features.lead": "Editor, PDF, second screen and export in a single application.",
      "f1.title": "Native desktop control room",
      "f1.text": "Built with PyQt6: project and slide panels, inspector, palette and HTML5 canvas. No browser tabs to keep open.",
      "f2.title": "HTML slides and PDF",
      "f2.text": "Build slides from scratch or import PDF pages by range. Pages are rendered server-side into lightweight images, ready for the player.",
      "f3.title": "Visual editing",
      "f3.text": "Drag, resize and rotate elements with snapping and guides. 25–200% zoom, inline text editing, undo/redo and autosave.",
      "f4.title": "Complete inspector",
      "f4.text": "Geometry, rotation, opacity and layer; typography, colors and alignment; background, border, radius, shadow and entrance animations.",
      "f5.title": "Templates and themes",
      "f5.text": "Five ready-made layouts — title, title and subtitle, bullet list, full-screen image, two columns — and four color themes for the project.",
      "f6.title": "Second screen, no app",
      "f6.text": "A TV, tablet or another PC opens the player in a browser. A QR code connects it; every screen shows the same slide, and one key turns it black.",
      "f7.title": "Standalone export",
      "f7.text": "Export the deck as a static folder or a single HTML file with assets inlined: it opens from file:// even on a computer without DoubleScreener.",
      "f8.title": "Your local workspace",
      "f8.text": "JSON projects, assets in a dedicated folder, no tracking. Interface and player available in Italian and English.",

      "how.eyebrow": "How it works",
      "how.title": "Three parts, one presentation.",
      "how.lead": "The control room is the single source of truth. Everything else just shows the current slide.",
      "flow.regia.title": "Control room",
      "flow.regia.text": "PyQt6 editor with canvas, inspector and preview.",
      "flow.server.title": "Local server",
      "flow.server.text": "FastAPI + Uvicorn keeps state in sync over WebSocket.",
      "flow.screen.title": "Second screen",
      "flow.screen.text": "Any browser on the local network, including a Smart TV.",
      "step1.title": "Start the control room",
      "step1.text": "Open DoubleScreener on the computer connected to the projector or TV.",
      "step2.title": "Connect the screen",
      "step2.text": "Scan the QR code in the Presentation panel, or open the LAN address in the browser.",
      "step3.title": "Present",
      "step3.text": "Build the slides, press F5 and navigate with the arrow keys. Every screen stays in sync.",

      "install.eyebrow": "Install",
      "install.title": "From source, in minutes.",
      "install.lead": "DoubleScreener v2 is under active development: for now it installs from source. You need Python 3.11+ and Git.",
      "install.req.title": "Requirements",
      "install.req1": "<strong>Python 3.11+</strong> — tested on Python 3.13.",
      "install.req2": "<strong>Windows, Linux or macOS</strong> — on Linux you need the distribution's Qt/WebEngine libraries.",
      "install.req3": "<strong>No Node.js</strong> — the frontend is already bundled.",
      "install.note": "The v2 code lives on <code>main</code>. The project is still under development: there are no packaged releases yet.",
      "install.copy": "Copy",
      "install.copied": "Copied",
      "install.after.title": "Then…",
      "install.after.text": "With the control room open, the Presentation panel shows the address for the second screen (for example <code>http://192.168.1.20:8765/p</code>) and the QR code. Data is stored in the app's user folder; use <code>--data-dir</code> to pick another one.",

      "status.eyebrow": "Status",
      "status.title": "Where we are.",
      "status.lead": "v2 is usable from source. Packaging is still missing: there are no installers or downloadable releases yet.",
      "status.done.title": "Available now",
      "status.done1": "Visual editor with inspector, palette, templates and themes",
      "status.done2": "HTML slides and PDF import by page range",
      "status.done3": "Live second screen with QR, sync and black screen",
      "status.done4": "Folder or single-file export and JSON project import",
      "status.done5": "IT/EN interface, dark and light themes, diagnostics",
      "status.done6": "Documentation: architecture, API, WebSocket protocol, setup",
      "status.next.title": "Planned",
      "status.next1": "Windows packaging: installer and portable build",
      "status.next2": "Video, camera and web page modes",
      "status.next3": "Speaker notes, multi-view and PDF deck export",
      "status.next4": "QA on Windows, browsers and Smart TVs, then tag v2.0.0",
      "status.note": "The work plan, technical decisions and known limits live in the repository's <a href=\"https://github.com/il-mangia/doublescreener.github.io/blob/main/work.md\" target=\"_blank\" rel=\"noopener\">work.md</a>.",

      "footer.tagline": "Desktop control room and second screen for HTML and PDF presentations. Local, open source, no cloud.",
      "footer.project": "Project",
      "footer.github": "GitHub repository",
      "footer.issues": "Report an issue",
      "footer.readme": "README",
      "footer.license": "GPL-3.0 license",
      "footer.docs": "Documentation",
      "footer.docs.setup": "Setup and development",
      "footer.docs.architecture": "Architecture",
      "footer.docs.api": "REST API",
      "footer.docs.ws": "WebSocket protocol",
      "footer.tech": "Built with",
      "footer.legal": "Free software released under the <strong>GPL-3.0-only</strong> license.",
      "footer.credits": "Copyright © 2026 il-mangia and DoubleScreener contributors.",
      "footer.privacy": "No cookies, no tracking: this page is static."
    }
  };

  var root = document.documentElement;
  var metaDescription = document.querySelector('meta[name="description"]');
  var metaTheme = document.querySelector('meta[name="theme-color"]');
  var themeToggle = document.getElementById("themeToggle");
  var copyButton = document.getElementById("copyInstall");
  var installCode = document.getElementById("installCode");
  var langButtons = Array.prototype.slice.call(document.querySelectorAll("[data-lang]"));
  var copiedTimer = null;

  function detectLanguage() {
    var requested = new URLSearchParams(window.location.search).get("lang");
    if (requested === "it" || requested === "en") return requested;
    try {
      var stored = localStorage.getItem("ds-lang");
      if (stored === "it" || stored === "en") return stored;
    } catch (error) {
      /* storage non disponibile */
    }
    var browser = (navigator.language || "en").toLowerCase();
    return browser.indexOf("it") === 0 ? "it" : "en";
  }

  function currentLanguage() {
    return root.lang === "en" ? "en" : "it";
  }

  function applyLanguage(lang) {
    var dict = I18N[lang] || I18N.it;
    root.lang = lang;
    document.title = dict["meta.title"];
    if (metaDescription) {
      metaDescription.setAttribute("content", dict["meta.description"]);
    }

    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      var value = dict[node.dataset.i18n];
      if (value) node.textContent = value;
    });

    document.querySelectorAll("[data-i18n-html]").forEach(function (node) {
      var value = dict[node.dataset.i18nHtml];
      if (value) node.innerHTML = value;
    });

    document.querySelectorAll("[data-i18n-label]").forEach(function (node) {
      var value = dict[node.dataset.i18nLabel];
      if (value) node.setAttribute("aria-label", value);
    });

    langButtons.forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.lang === lang));
    });

    if (copyButton) {
      copyButton.classList.remove("is-copied");
      var label = copyButton.querySelector("span");
      if (label) label.textContent = dict["install.copy"];
    }

    try {
      localStorage.setItem("ds-lang", lang);
    } catch (error) {
      /* storage non disponibile */
    }
  }

  function currentTheme() {
    return root.dataset.theme === "light" ? "light" : "dark";
  }

  function applyTheme(theme) {
    root.dataset.theme = theme;
    if (metaTheme) {
      metaTheme.setAttribute("content", theme === "light" ? "#f5f8fd" : "#0a0c11");
    }
    try {
      localStorage.setItem("ds-theme", theme);
    } catch (error) {
      /* storage non disponibile */
    }
  }

  function copyInstallCommand() {
    if (!copyButton || !installCode) return;
    var text = installCode.textContent;
    var done = function () {
      var label = copyButton.querySelector("span");
      copyButton.classList.add("is-copied");
      if (label) label.textContent = (I18N[currentLanguage()] || I18N.it)["install.copied"];
      clearTimeout(copiedTimer);
      copiedTimer = setTimeout(function () {
        copyButton.classList.remove("is-copied");
        if (label) label.textContent = (I18N[currentLanguage()] || I18N.it)["install.copy"];
      }, 2000);
    };

    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(fallbackCopy);
    } else {
      fallbackCopy();
    }

    function fallbackCopy() {
      try {
        var area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
        done();
      } catch (error) {
        /* copia non disponibile */
      }
    }
  }

  langButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      applyLanguage(button.dataset.lang === "en" ? "en" : "it");
    });
  });

  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  if (copyButton) {
    copyButton.addEventListener("click", copyInstallCommand);
  }

  var header = document.querySelector(".site-header");
  function onScroll() {
    if (!header) return;
    header.classList.toggle("is-scrolled", window.scrollY > 8);
  }
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  var reveals = document.querySelectorAll(".reveal");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if ("IntersectionObserver" in window && !reduceMotion) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
    );
    reveals.forEach(function (node) {
      observer.observe(node);
    });
  } else {
    reveals.forEach(function (node) {
      node.classList.add("is-visible");
    });
  }

  applyLanguage(detectLanguage());
  if (metaTheme) {
    metaTheme.setAttribute("content", currentTheme() === "light" ? "#f5f8fd" : "#0a0c11");
  }
})();
