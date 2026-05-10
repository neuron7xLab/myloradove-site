/* =====================================================================
   Милорадове · script.js
   Zero dependencies. Each module isolated in safely(); one failure
   never cascades. Operational events optionally reported via window._mv.
   ===================================================================== */
(() => {
  'use strict';

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const rmotion = () =>
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── Telemetry hook ───────────────────────────────────────────────
  // Page owners can wire this to a beacon endpoint; otherwise errors
  // are visible in console.error (not suppressed). No silent death.
  const report = (name, err) => {
    if (window.console && console.error) {
      console.error(`[myloradove:${name}]`, err);
    }
    if (typeof window._mv === 'function') {
      try { window._mv(name, err); } catch (_) { /* never throw from hook */ }
    }
  };
  const safely = (name, fn) => {
    try { fn(); } catch (err) { report(name, err); }
  };

  // ── Shared scroll-lock primitive (never set twice, never forgotten) ─
  const ScrollLock = (() => {
    const owners = new Set();
    return {
      acquire(owner) {
        owners.add(owner);
        if (owners.size === 1) {
          document.documentElement.style.overflow = 'hidden';
          document.body.style.overflow = 'hidden';
        }
      },
      release(owner) {
        owners.delete(owner);
        if (owners.size === 0) {
          document.documentElement.style.overflow = '';
          document.body.style.overflow = '';
        }
      },
    };
  })();

  /* --- NAV: scrolled state + mobile drawer -------------------------- */
  safely('nav', () => {
    const nav = $('#nav');
    if (!nav) return;

    // 1. scrolled flag — add class after 40 px
    let scrolled = false;
    const onScroll = () => {
      const next = window.scrollY > 40;
      if (next !== scrolled) {
        scrolled = next;
        nav.classList.toggle('is-scrolled', next);
        // Mirror the state on <html> so elements outside nav (lang-switch)
        // can restyle without being siblings.
        document.documentElement.dataset.scrolled = next ? 'true' : 'false';
      }
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    // 2. mobile drawer
    const toggle = $('.nav__toggle', nav);
    const menu = $('#nav-menu');
    if (!toggle || !menu) return;

    const DESKTOP = window.matchMedia('(width > 860px)');

    const setOpen = (open) => {
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? 'Закрити меню' : 'Відкрити меню');
      menu.classList.toggle('is-open', open);
      if (open) ScrollLock.acquire('nav');
      else      ScrollLock.release('nav');
    };

    toggle.addEventListener('click', () =>
      setOpen(toggle.getAttribute('aria-expanded') !== 'true'));

    $$('a', menu).forEach(a =>
      a.addEventListener('click', () => setOpen(false)));

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && menu.classList.contains('is-open')) setOpen(false);
    });

    // 3. ⚠ if viewport crosses mobile→desktop while drawer is open,
    //    CSS hides the drawer but scroll-lock stays active. Reset.
    const onBreakpointChange = (e) => {
      if (e.matches && toggle.getAttribute('aria-expanded') === 'true') {
        setOpen(false);
      }
    };
    if (typeof DESKTOP.addEventListener === 'function') {
      DESKTOP.addEventListener('change', onBreakpointChange);
    } else if (typeof DESKTOP.addListener === 'function') {
      // legacy Safari < 14
      DESKTOP.addListener(onBreakpointChange);
    }
  });

  /* --- READING PROGRESS: rAF-throttled, writes one CSS var ---------- */
  safely('progress', () => {
    const bar = $('.progress');
    if (!bar) return;
    let rafPending = false;
    const update = () => {
      rafPending = false;
      const doc = document.documentElement;
      const max = doc.scrollHeight - doc.clientHeight;
      const p = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
      bar.style.setProperty('--scroll', p.toFixed(4));
    };
    update();
    const tick = () => {
      if (!rafPending) {
        rafPending = true;
        requestAnimationFrame(update);
      }
    };
    window.addEventListener('scroll', tick, { passive: true });
    window.addEventListener('resize', tick, { passive: true });
  });

  /* --- ACTIVE SECTION: aria-current on the live link ---------------- */
  safely('active-section', () => {
    const links = $$('.nav__menu a[href^="#"]');
    if (!links.length) return;

    const byId = new Map();
    const sections = [];
    links.forEach((a) => {
      const id = a.getAttribute('href').slice(1);
      const sec = document.getElementById(id);
      if (sec) { byId.set(sec, a); sections.push(sec); }
    });
    if (!sections.length || !('IntersectionObserver' in window)) return;

    let current = null;
    const setCurrent = (link) => {
      if (link === current) return;
      if (current) current.removeAttribute('aria-current');
      current = link;
      if (link) link.setAttribute('aria-current', 'true');
    };

    const io = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (visible.length) setCurrent(byId.get(visible[0].target));
    }, {
      rootMargin: '-25% 0px -60% 0px',
      threshold: [0, 0.25, 0.5, 0.75, 1],
    });
    sections.forEach((sec) => io.observe(sec));

    // Near the bottom of the page the rootMargin above misses short
    // final sections (#contact). Fall back to "closest section above
    // the mid-line" on scroll bottom.
    const closestOnBottom = () => {
      const near = window.innerHeight + window.scrollY >=
                   document.documentElement.scrollHeight - 2;
      if (!near) return;
      const mid = window.scrollY + window.innerHeight * 0.4;
      let best = null, bestTop = -Infinity;
      for (const sec of sections) {
        const top = sec.getBoundingClientRect().top + window.scrollY;
        if (top <= mid && top > bestTop) { best = sec; bestTop = top; }
      }
      if (best) setCurrent(byId.get(best));
    };
    window.addEventListener('scroll', closestOnBottom, { passive: true });
  });

  /* --- SMOOTH ANCHOR SCROLL with header offset ---------------------- */
  safely('anchor-offset', () => {
    const nav = $('#nav');
    const headerH = () => (nav ? nav.getBoundingClientRect().height : 0);
    const behavior = rmotion() ? 'auto' : 'smooth';

    $$('a[href^="#"]').forEach((a) => {
      a.addEventListener('click', (e) => {
        const href = a.getAttribute('href');
        if (!href || href === '#') return;
        const target = document.getElementById(href.slice(1));
        if (!target) return;
        e.preventDefault();
        const y = target.getBoundingClientRect().top + window.scrollY - headerH() - 8;
        window.scrollTo({ top: y, behavior });
        history.replaceState(null, '', href);
      });
    });
  });

  /* --- REVEAL: fade-up on enter ------------------------------------- */
  safely('reveal', () => {
    const targets = $$([
      '.chapter__head',
      '.essay',
      '.plate',
      '.timeline > li',
      '.culture__text',
      '.infra__item',
      '.tile',
      '.contact article'
    ].join(','));
    if (!targets.length) return;
    targets.forEach(el => el.classList.add('reveal'));

    if (rmotion() || !('IntersectionObserver' in window)) {
      targets.forEach(el => el.classList.add('is-in'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('is-in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });
    targets.forEach(el => io.observe(el));
  });

  /* --- LIGHTBOX: AVIF-first, focus restore, inert main -------------- */
  safely('lightbox', () => {
    const lb = $('#lightbox');
    if (!lb) return;
    const img    = $('img', lb);
    const cap    = $('.lightbox__caption', lb);
    const closeBtn = $('.lightbox__close', lb);
    const main   = $('main');
    if (!img || !cap || !closeBtn) return;

    const hasDialog = typeof lb.showModal === 'function';

    // Pick the best quality source the browser can decode.
    // Each tile knows its base name (e.g. "img_4886") and max width (1920).
    const pickSource = (baseHref) => {
      // baseHref looks like "images/img_4886-1920.webp"
      const match = /^(.*)-(\d+)\.(webp|avif|jpe?g|png)$/i.exec(baseHref);
      if (!match) return baseHref;
      const base = match[1];
      // Prefer AVIF if the browser supports it; fall back to WebP.
      if (document.createElement('picture').toString() !== '[object HTMLUnknownElement]') {
        // All modern browsers implementing <picture> also decode WebP.
        // AVIF support is harder to detect synchronously — keep baseHref
        // as the webp/jpg fallback, but try AVIF via an Image probe below.
      }
      return {
        avif: `${base}-1920.avif`,
        webp: baseHref,
      };
    };

    // One-time AVIF decode probe.
    let canAvif = null;
    const probeAvif = () => new Promise((resolve) => {
      if (canAvif !== null) return resolve(canAvif);
      const test = new Image();
      test.onload  = () => { canAvif = true;  resolve(true); };
      test.onerror = () => { canAvif = false; resolve(false); };
      // 1×1 AVIF
      test.src = 'data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAAB0AAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAIAAAACAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQ0MAAAAABNjb2xybmNseAACAAIAAYAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAACVtZGF0EgAKCBgANogQEAwgMg8f8D///8WfhwB8+ErK42A=';
    });

    let returnFocus = null;

    const open = async (href, alt, caption, trigger) => {
      returnFocus = trigger || document.activeElement;

      // Source negotiation
      const sources = pickSource(href);
      let src = typeof sources === 'string' ? sources : sources.webp;
      if (typeof sources === 'object') {
        const avifOk = await probeAvif();
        if (avifOk) src = sources.avif;
      }

      img.src = src;
      img.alt = alt || '';
      cap.textContent = caption || '';

      if (hasDialog) lb.showModal();
      else lb.setAttribute('open', '');
      if (main) main.inert = true;
      ScrollLock.acquire('lightbox');

      closeBtn.focus({ preventScroll: true });
    };

    const close = () => {
      if (hasDialog) lb.close();
      else lb.removeAttribute('open');
      if (main) main.inert = false;
      ScrollLock.release('lightbox');
      img.src = '';
      if (returnFocus && typeof returnFocus.focus === 'function') {
        returnFocus.focus({ preventScroll: true });
      }
      returnFocus = null;
    };

    $$('.tile a').forEach((a) => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        const pict = a.querySelector('img');
        open(a.getAttribute('href'),
             pict ? pict.alt : '',
             a.dataset.caption || '',
             a);
      });
    });
    closeBtn.addEventListener('click', close);
    lb.addEventListener('click', (e) => { if (e.target === lb) close(); });
    lb.addEventListener('cancel', (e) => { e.preventDefault(); close(); });
  });

  /* --- HERO FILTER GATE: pause SVG displacement when off-screen ------
     The feTurbulence + feDisplacementMap chain runs at 60 fps while the
     <animate> ticks. When the hero scrolls out of view the filter still
     re-rasterises behind the scenes unless we explicitly pause SMIL and
     hide the filtered layer. Saves a substantial GPU budget on every
     section below the fold. */
  safely('hero-filter-gate', () => {
    const hero = document.getElementById('top');
    const water = $('.hero__water');
    const filters = $('.hero__filters');
    if (!hero || !water || !('IntersectionObserver' in window)) return;

    let active = true;
    const setActive = (next) => {
      if (next === active) return;
      active = next;
      // Hide the filtered surface entirely — no paint, no composite.
      water.style.visibility = next ? '' : 'hidden';
      // Pause SMIL animations on the filter SVG root.
      try {
        if (!next && typeof filters.pauseAnimations === 'function') {
          filters.pauseAnimations();
        } else if (next && typeof filters.unpauseAnimations === 'function') {
          filters.unpauseAnimations();
        }
      } catch (_) { /* ignore — SMIL not supported on this browser */ }
    };

    const io = new IntersectionObserver((entries) => {
      setActive(entries[0].isIntersecting);
    }, { threshold: 0, rootMargin: '120px 0px 120px 0px' });
    io.observe(hero);
  });

  /* --- COPY EMAIL: clipboard for contact cards ---------------------- */
  safely('copy-email', () => {
    const buttons = $$('.email-card__copy[data-copy]');
    if (!buttons.length) return;
    const status = $('[data-copy-status]');

    const announce = (msg) => {
      if (status) status.textContent = msg;
    };

    const fallbackCopy = (text) => {
      // Clipboard API unavailable (old iOS, insecure context) — fall through
      // to a temporary textarea + execCommand. Works on every browser 2015+.
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
        return true;
      } finally {
        document.body.removeChild(ta);
      }
    };

    const markCopied = (btn) => {
      btn.classList.add('is-copied');
      const label = btn.querySelector('.email-card__copy-label');
      const originalLabel = label ? label.textContent : '';
      if (label) label.textContent = 'Скопійовано';
      announce(`Скопійовано: ${btn.dataset.copy}`);
      setTimeout(() => {
        btn.classList.remove('is-copied');
        if (label) label.textContent = originalLabel;
      }, 1800);
    };

    buttons.forEach((btn) => {
      btn.addEventListener('click', async () => {
        const text = btn.dataset.copy;
        let ok = false;
        if (navigator.clipboard && window.isSecureContext) {
          try {
            await navigator.clipboard.writeText(text);
            ok = true;
          } catch (_) { /* fall through */ }
        }
        if (!ok) ok = fallbackCopy(text);
        if (ok) markCopied(btn);
        else announce('Не вдалося скопіювати. Виділіть і Ctrl+C.');
      });
    });
  });

  /* --- Year stamp --------------------------------------------------- */
  safely('year', () => {
    const el = $('#year');
    if (el) el.textContent = String(new Date().getFullYear());
  });
})();
