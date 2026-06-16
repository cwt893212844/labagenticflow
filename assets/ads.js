(function () {
  "use strict";

  const MOBILE_MQ = window.matchMedia("(max-width: 640px)");

  function getConfig() {
    return window.LAF_AD_CONFIG || { enabled: false, slots: {} };
  }

  function resolveSlot(slotId, slotCfg, host) {
    if (slotCfg.mobile && MOBILE_MQ.matches) {
      const m = slotCfg.mobile;
      if (m.key) {
        return {
          key: m.key,
          width: m.width,
          height: m.height,
          invokeHost: m.invokeHost || host,
        };
      }
    }
    return {
      key: slotCfg.key,
      width: slotCfg.width,
      height: slotCfg.height,
      invokeHost: slotCfg.invokeHost || host,
    };
  }

  function buildIframeSrcdoc(opts) {
    const atOptions = {
      key: opts.key,
      format: "iframe",
      height: opts.height,
      width: opts.width,
      params: opts.params || {},
    };
    const host = opts.invokeHost.replace(/^\/\//, "");
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;padding:0;overflow:hidden;background:transparent}body{display:flex;justify-content:center;align-items:center;min-height:${opts.height}px}</style></head><body><script>atOptions=${JSON.stringify(atOptions)};<\/script><script src="https://${host}/${opts.key}/invoke.js"><\/script></body></html>`;
  }

  function mountBannerSlot(el, slotCfg, host) {
    const resolved = resolveSlot(el.dataset.adSlot, slotCfg, host);
    if (!resolved.key) return false;

    const iframe = document.createElement("iframe");
    iframe.title = "Advertisement";
    iframe.setAttribute("loading", "lazy");
    iframe.setAttribute("referrerpolicy", "no-referrer-when-downgrade");
    iframe.setAttribute(
      "sandbox",
      "allow-scripts allow-popups allow-popups-to-escape-sandbox allow-same-origin"
    );
    iframe.width = String(resolved.width);
    iframe.height = String(resolved.height);
    iframe.style.border = "0";
    iframe.style.display = "block";
    iframe.style.margin = "0 auto";
    iframe.style.maxWidth = "100%";
    iframe.srcdoc = buildIframeSrcdoc(resolved);

    el.innerHTML = "";
    el.classList.add("ad-slot--live");
    el.style.minHeight = resolved.height + "px";
    el.appendChild(iframe);
    return true;
  }

  function initSlot(el, cfg) {
    const slotId = el.dataset.adSlot;
    const slotCfg = cfg.slots[slotId];
    if (!slotCfg) return;

    const mounted = mountBannerSlot(el, slotCfg, cfg.invokeHost);
    if (!mounted && cfg.enabled) {
      el.classList.add("ad-slot--pending");
    }
  }

  function init() {
    const cfg = getConfig();
    const slots = document.querySelectorAll("[data-ad-slot]");
    if (!cfg.enabled) return;

    slots.forEach((el) => initSlot(el, cfg));

    MOBILE_MQ.addEventListener("change", () => {
      slots.forEach((el) => {
        const slotCfg = cfg.slots[el.dataset.adSlot];
        if (slotCfg?.mobile) {
          el.classList.remove("ad-slot--live", "ad-slot--pending");
          el.innerHTML =
            '<span class="ad-slot__placeholder">' +
            (el.dataset.adSlot === "banner-top" ? "Ad · banner" : "Ad · native") +
            "</span>";
          initSlot(el, cfg);
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
