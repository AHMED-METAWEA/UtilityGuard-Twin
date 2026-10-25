// Every user-visible string of the shell lives here, in English (AGENTS.md, Language).
// Components import STRINGS and never write text themselves; a test enforces it. The Arabic
// translation is added later as a second table with full RTL support (Master Spec section 13).

export const STRINGS = {
  appName: "UtilityGuard Twin",
  honesty: {
    regionLabel: "Honesty notice",
    // True at every fidelity level the product can show before ACUD data exists.
    statement:
      "Virtual twin. Not ACUD data and not a survey of any real network. Advisory only: a human approves every action. Not certified for operation of critical infrastructure.",
    chip: "Virtual twin · advisory only",
    collapse: "Collapse notice",
    expand: "Show full notice",
  },
  fidelity: {
    label: "Fidelity",
    none: "No network loaded",
    unknown: "Fidelity could not be determined",
    f0: "Fidelity F0: Generic synthetic",
    f1: "Fidelity F1: Public capital layout, inferred pipes, synthetic hydraulics",
    downgraded:
      "The loaded network declares a higher fidelity than its provenance supports, so the lowest level is shown.",
  },
  stream: {
    label: "Stream source",
    noStream: "no stream connected",
    unknown: "unknown",
  },
  nav: {
    label: "Main navigation",
    commandCenter: "Command Center",
    scenarioLab: "Scenario Lab",
    systemHealth: "System Health",
  },
  pages: {
    commandCenter: {
      title: "Command Center",
      empty: "No network is loaded, so there is nothing to show yet.",
    },
    scenarioLab: {
      title: "Scenario Lab",
      empty: "Scenarios can be configured once a network is loaded.",
    },
    systemHealth: {
      title: "System Health",
      empty: "No health data yet. The API is not connected in this build.",
    },
    notFound: {
      title: "Page not found",
      body: "This address does not match a screen. Choose one from the navigation.",
    },
  },
  status: {
    loading: "Loading…",
    errorTitle: "Something went wrong",
    errorHint: "The notice, the fidelity badge and the stream source stay visible.",
  },
} as const;
