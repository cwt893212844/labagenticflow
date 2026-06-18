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

  /** Sequential mount — global atOptions must not be overwritten by a second slot. */
  function mountSlot(el, slotCfg, host) {
    const resolved = resolveSlot(el.dataset.adSlot, slotCfg, host);
    if (!resolved.key) return Promise.resolve(false);

    const atOptions = {
      key: resolved.key,
      format: "iframe",
      height: resolved.height,
      width: resolved.width,
      params: {},
    };
    const invokeHost = resolved.invokeHost.replace(/^\/\//, "");

    el.innerHTML = "";
    el.classList.add("ad-slot--live");
    el.style.minHeight = resolved.height + "px";
    el.style.maxWidth = resolved.width + "px";
    el.style.marginLeft = "auto";
    el.style.marginRight = "auto";

    return new Promise((resolve) => {
      const optsScript = document.createElement("script");
      optsScript.text = "atOptions = " + JSON.stringify(atOptions) + ";";

      const invokeScript = document.createElement("script");
      invokeScript.src = "//" + invokeHost + "/" + resolved.key + "/invoke.js";
      invokeScript.onload = () => resolve(true);
      invokeScript.onerror = () => {
        el.classList.add("ad-slot--pending");
        resolve(false);
      };

      el.appendChild(optsScript);
      el.appendChild(invokeScript);
    });
  }

  function placeholderLabel(slotId) {
    return slotId === "banner-top" ? "Ad · banner" : "Ad · native";
  }

  function resetSlot(el) {
    el.classList.remove("ad-slot--live", "ad-slot--pending");
    el.style.minHeight = "";
    el.style.maxWidth = "";
    el.style.marginLeft = "";
    el.style.marginRight = "";
    el.innerHTML =
      '<span class="ad-slot__placeholder">' + placeholderLabel(el.dataset.adSlot) + "</span>";
  }

  async function mountAll(slots, cfg) {
    for (const el of slots) {
      const slotCfg = cfg.slots[el.dataset.adSlot];
      if (slotCfg) await mountSlot(el, slotCfg, cfg.invokeHost);
    }
  }

  function init() {
    const cfg = getConfig();
    const slots = document.querySelectorAll("[data-ad-slot]");
    if (!cfg.enabled) return;

    mountAll(slots, cfg);

    MOBILE_MQ.addEventListener("change", () => {
      slots.forEach((el) => {
        const slotCfg = cfg.slots[el.dataset.adSlot];
        if (slotCfg?.mobile) resetSlot(el);
      });
      mountAll(slots, cfg);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
