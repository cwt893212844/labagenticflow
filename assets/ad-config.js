/**
 * Adsterra placement config — fill keys after publisher approval.
 * Dashboard: Websites → Get code → copy key + invoke host per placement.
 * Keep Pop/Push disabled; only Banner + Native on this site.
 */
window.LAF_AD_CONFIG = {
  /** Live — keys from Adsterra Websites → GET CODE (2026-06-17) */
  enabled: true,

  /** Default invoke CDN host from your Adsterra code snippet */
  invokeHost: "www.highperformanceformat.com",

  slots: {
    /** Top leaderboard — desktop 728×90, mobile 320×50 */
    "banner-top": {
      type: "banner",
      key: "b8d212a174ec325734e583a2bdd92347",
      width: 728,
      height: 90,
      mobile: { key: "c4f7002bad9af6ab27fa3476178f04ef", width: 320, height: 50 },
    },

    /** Footer — 300×250 medium rectangle */
    "native-bottom": {
      type: "native",
      key: "2b760e4dda54dbe4750df8f4e430f74f",
      width: 300,
      height: 250,
    },
  },
};
