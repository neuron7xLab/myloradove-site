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
      try { window._mv(name, err); } catch (_) {  }
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
  
    safely('portal-data', () => {
    const root = document.querySelector('[data-portal-grid]');
    if (!root) return;
    fetch('data/portal.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error('portal.json missing')))
      .then(data => {
        const cats = Array.isArray(data.categories) ? data.categories : [];
        const dir = Array.isArray(data.directory) ? data.directory : [];
        root.innerHTML = cats.map(c => `
          <article class="portal-card">
            <h3><span aria-hidden="true">${c.icon || '▣'}</span> ${c.name || 'Секція'}</h3>
            ${(c.items || []).map(i => `<p><strong>${i.title || ''}</strong><br>${i.price || ''}<br><em>${i.promo || ''}</em></p>`).join('')}
          </article>`).join('') + `
          <article class="portal-card portal-card--directory">
            <h3>Корисна інформація</h3>
            ${dir.map(d => `<p><strong>${d.title}</strong><br>${d.hours}<br><a href="tel:${d.phone}">${d.phone}</a></p>`).join('')}
          </article>`;
      })
      .catch((e) => report('portal-data', e));
  });

    safely('geo-stack', () => {
    const mapEl = document.getElementById('village-map');
    const panoEl = document.getElementById('panorama-view');
    if (!mapEl || !panoEl || !window.L) return;

    const points = [
      { name: 'Милорадове центр', lat: 49.5374, lng: 34.7102 },
      { name: 'Лабурівка', lat: 49.5215, lng: 34.7351 },
      { name: 'Околиці ставу', lat: 49.5459, lng: 34.6954 }
    ];

    const map = L.map(mapEl, { scrollWheelZoom: false }).setView([49.5374, 34.7102], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
    L.polyline(points.map(p => [p.lat, p.lng]), { color: '#d4af37', weight: 4, opacity: 0.8 }).addTo(map);

    points.forEach((p) => {
      const url = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${p.lat},${p.lng}`;
      L.marker([p.lat, p.lng]).addTo(map).bindPopup(`<strong>${p.name}</strong><br><a href="${url}" target="_blank" rel="noopener">Street View</a>`);
    });

    if (window.pannellum) {
      window.pannellum.viewer('panorama-view', { type: 'equirectangular', panorama: 'images/img_9210-1920.webp', autoLoad: true, showControls: true, hfov: 100 });
    }
  });

})();

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
      } catch (_) {  }
    };

    const io = new IntersectionObserver((entries) => {
      setActive(entries[0].isIntersecting);
    }, { threshold: 0, rootMargin: '120px 0px 120px 0px' });
    io.observe(hero);
  });

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
          } catch (_) {  }
        }
        if (!ok) ok = fallbackCopy(text);
        if (ok) markCopied(btn);
        else announce('Не вдалося скопіювати. Виділіть і Ctrl+C.');
      });
    });
  });

    safely('year', () => {
    const el = $('#year');
    if (el) el.textContent = String(new Date().getFullYear());
  });

    safely('cursor-light', () => {
    const hero = $('.hero');
    if (!hero) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (matchMedia('(pointer: coarse)').matches) return;
    let raf = 0;
    hero.addEventListener('pointermove', (e) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        const r = hero.getBoundingClientRect();
        const x = ((e.clientX - r.left) / r.width)  * 100;
        const y = ((e.clientY - r.top)  / r.height) * 100;
        hero.style.setProperty('--mouse-x', x.toFixed(1) + '%');
        hero.style.setProperty('--mouse-y', y.toFixed(1) + '%');
        raf = 0;
      });
    }, { passive: true });
    hero.addEventListener('pointerleave', () => {
      hero.style.setProperty('--mouse-x', '50%');
      hero.style.setProperty('--mouse-y', '50%');
    });
  });

    safely('chapter-indicator', () => {
    const ind = document.querySelector('[data-chapter-indicator]');
    if (!ind || !('IntersectionObserver' in window)) return;
    const numEl   = ind.querySelector('.chapter-indicator__num');
    const titleEl = ind.querySelector('.chapter-indicator__title');
    const sections = document.querySelectorAll('section.chapter');
    if (!sections.length) return;
    const data = new Map();
    sections.forEach((s) => {
      const numNode = s.querySelector('.chapter__num');
      const titleNode = s.querySelector('.chapter__title');
      if (!numNode || !titleNode) return;
      // "I · Село" → ["I", "Село"]
      const raw = (numNode.textContent || '').trim();
      const parts = raw.split(/\s+·\s+/);
      data.set(s, {
        num: parts[0] || raw,
        title: (titleNode.textContent || '').trim().replace(/\s+/g, ' '),
      });
    });
    let active = null;
    const io = new IntersectionObserver((entries) => {
      // Pick the entry whose top is closest to the upper third of the viewport.
      const candidates = entries.filter((e) => e.isIntersecting);
      if (!candidates.length) return;
      const best = candidates.sort(
        (a, b) => Math.abs(a.boundingClientRect.top) - Math.abs(b.boundingClientRect.top)
      )[0];
      const meta = data.get(best.target);
      if (!meta || meta === active) return;
      active = meta;
      numEl.textContent = meta.num;
      titleEl.textContent = meta.title;
      ind.classList.add('is-visible');
    }, { rootMargin: '-30% 0px -55% 0px', threshold: 0 });
    sections.forEach((s) => io.observe(s));
    // Hide indicator when the hero is back in view.
    const hero = $('.hero');
    if (hero) {
      const heroIO = new IntersectionObserver(([e]) => {
        ind.classList.toggle('is-visible', !e.isIntersecting && active !== null);
      }, { threshold: 0.4 });
      heroIO.observe(hero);
    }
  });

  safely('view-transitions', () => {
    if (!document.startViewTransition) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a[href^="#"]');
      if (!link) return;
      const href = link.getAttribute('href');
      if (!href || href === '#') return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      document.startViewTransition(() => {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', href);
      });
    });
  });

    safely('portal-data', () => {
    const root = document.querySelector('[data-portal-grid]');
    if (!root) return;
    fetch('data/portal.json', { cache: 'no-store' })
      .then(r => r.ok ? r.json() : Promise.reject(new Error('portal.json missing')))
      .then(data => {
        const cats = Array.isArray(data.categories) ? data.categories : [];
        const dir = Array.isArray(data.directory) ? data.directory : [];
        root.innerHTML = cats.map(c => `
          <article class="portal-card">
            <h3><span aria-hidden="true">${c.icon || '▣'}</span> ${c.name || 'Секція'}</h3>
            ${(c.items || []).map(i => `<p><strong>${i.title || ''}</strong><br>${i.price || ''}<br><em>${i.promo || ''}</em></p>`).join('')}
          </article>`).join('') + `
          <article class="portal-card portal-card--directory">
            <h3>Корисна інформація</h3>
            ${dir.map(d => `<p><strong>${d.title}</strong><br>${d.hours}<br><a href="tel:${d.phone}">${d.phone}</a></p>`).join('')}
          </article>`;
      })
      .catch((e) => report('portal-data', e));
  });

    safely('geo-stack', () => {
    const mapEl = document.getElementById('village-map');
    const panoEl = document.getElementById('panorama-view');
    if (!mapEl || !panoEl || !window.L) return;

    const points = [
      { name: 'Милорадове центр', lat: 49.5374, lng: 34.7102 },
      { name: 'Лабурівка', lat: 49.5215, lng: 34.7351 },
      { name: 'Околиці ставу', lat: 49.5459, lng: 34.6954 }
    ];

    const map = L.map(mapEl, { scrollWheelZoom: false }).setView([49.5374, 34.7102], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
    L.polyline(points.map(p => [p.lat, p.lng]), { color: '#d4af37', weight: 4, opacity: 0.8 }).addTo(map);

    points.forEach((p) => {
      const url = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${p.lat},${p.lng}`;
      L.marker([p.lat, p.lng]).addTo(map).bindPopup(`<strong>${p.name}</strong><br><a href="${url}" target="_blank" rel="noopener">Street View</a>`);
    });

    if (window.pannellum) {
      window.pannellum.viewer('panorama-view', { type: 'equirectangular', panorama: 'images/img_9210-1920.webp', autoLoad: true, showControls: true, hfov: 100 });
    }
  });

})();

  