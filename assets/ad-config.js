/**
 * Adsterra placement config — fill keys after publisher approval.
 * Dashboard: Websites → Get code → copy key + invoke host per placement.
 * Keep Pop/Push disabled; only Banner + Native on this site.
 */
window.LAF_AD_CONFIG = {
  /** Set true once keys are filled and site is approved */
  enabled: false,

  /** Default invoke CDN host from your Adsterra code snippet */
  invokeHost: "www.highperformanceformat.com",

  slots: {
    /** Top leaderboard — desktop 728×90, mobile 320×50 */
    "banner-top": {
      type: "banner",
      key: "",
      width: 728,
      height: 90,
      mobile: { key: "", width: 320, height: 50 },
    },

    /** Footer native / medium rectangle */
    "native-bottom": {
      type: "native",
      key: "",
      width: 300,
      height: 250,
    },
  },
};
