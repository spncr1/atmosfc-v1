(function () {
  const DEFAULT_VISUAL = {
    primary: "#747782",
    secondary: "#2B2D33",
  };

  const TEAM_VISUALS_BY_ID = {
    10: { primary: "#CE1124", secondary: "#FFFFFF" },
    33: { primary: "#DA291C", secondary: "#FBE122" },
    34: { primary: "#241F20", secondary: "#FFFFFF" },
    35: { primary: "#DA291C", secondary: "#000000" },
    36: { primary: "#FFFFFF", secondary: "#000000" },
    39: { primary: "#FDB913", secondary: "#231F20" },
    40: { primary: "#C8102E", secondary: "#00B2A9" },
    41: { primary: "#D71920", secondary: "#FFFFFF" },
    42: { primary: "#EF0107", secondary: "#063672" },
    45: { primary: "#003399", secondary: "#FFFFFF" },
    46: { primary: "#003090", secondary: "#FDBE11" },
    47: { primary: "#132257", secondary: "#FFFFFF" },
    48: { primary: "#7A263A", secondary: "#1BB1E7" },
    49: { primary: "#034694", secondary: "#D1D3D4" },
    50: { primary: "#6CABDD", secondary: "#1C2C5B" },
    51: { primary: "#0057B8", secondary: "#FFCD00" },
    52: { primary: "#1B458F", secondary: "#C4122E" },
    55: { primary: "#E30613", secondary: "#FBB800" },
    63: { primary: "#FFCD00", secondary: "#1D428A" },
    65: { primary: "#DD0000", secondary: "#FFFFFF" },
    66: { primary: "#95BFE5", secondary: "#670E36" },
    79: { primary: "#E01E3C", secondary: "#1D3C89" },
    80: { primary: "#DA001A", secondary: "#003A70" },
    81: { primary: "#00A3E0", secondary: "#FFFFFF" },
    85: { primary: "#004170", secondary: "#DA291C" },
    91: { primary: "#E30613", secondary: "#FFFFFF" },
    157: { primary: "#DC052D", secondary: "#0066B2" },
    165: { primary: "#FDE100", secondary: "#000000" },
    168: { primary: "#E32221", secondary: "#000000" },
    173: { primary: "#DD0741", secondary: "#001F5B" },
    194: { primary: "#D2122E", secondary: "#FFFFFF" },
    197: { primary: "#FF0000", secondary: "#FFFFFF" },
    209: { primary: "#D71920", secondary: "#FFFFFF" },
    211: { primary: "#E83030", secondary: "#FFFFFF" },
    212: { primary: "#00428C", secondary: "#FFFFFF" },
    228: { primary: "#00843D", secondary: "#FFFFFF" },
    489: { primary: "#FB090B", secondary: "#000000" },
    492: { primary: "#12A0D7", secondary: "#FFFFFF" },
    496: { primary: "#FFFFFF", secondary: "#000000" },
    497: { primary: "#8E1F2F", secondary: "#F0BC42" },
    499: { primary: "#1D71B8", secondary: "#000000" },
    502: { primary: "#5B2A86", secondary: "#D71920" },
    505: { primary: "#0057A8", secondary: "#000000" },
    487: { primary: "#87D8F7", secondary: "#FFFFFF" },
    529: { primary: "#A50044", secondary: "#004D98" },
    530: { primary: "#CB3524", secondary: "#272E61" },
    532: { primary: "#F18A00", secondary: "#000000" },
    533: { primary: "#FFE667", secondary: "#005187" },
    536: { primary: "#D71920", secondary: "#FFFFFF" },
    541: { primary: "#FFFFFF", secondary: "#FEBE10" },
    549: { primary: "#000000", secondary: "#FFFFFF" },
    611: { primary: "#002D72", secondary: "#FFED00" },
    645: { primary: "#A90432", secondary: "#FDB912" },
  };

  const TEAM_VISUALS_BY_NAME = {
    ajax: TEAM_VISUALS_BY_ID[194],
    arsenal: TEAM_VISUALS_BY_ID[42],
    "aston villa": TEAM_VISUALS_BY_ID[66],
    atalanta: TEAM_VISUALS_BY_ID[499],
    barcelona: TEAM_VISUALS_BY_ID[529],
    benfica: TEAM_VISUALS_BY_ID[211],
    besiktas: TEAM_VISUALS_BY_ID[549],
    "bayern munich": TEAM_VISUALS_BY_ID[157],
    "bayern munchen": TEAM_VISUALS_BY_ID[157],
    "borussia dortmund": TEAM_VISUALS_BY_ID[165],
    bournemouth: TEAM_VISUALS_BY_ID[35],
    brentford: TEAM_VISUALS_BY_ID[55],
    brighton: TEAM_VISUALS_BY_ID[51],
    chelsea: TEAM_VISUALS_BY_ID[49],
    "crystal palace": TEAM_VISUALS_BY_ID[52],
    dortmund: TEAM_VISUALS_BY_ID[165],
    england: TEAM_VISUALS_BY_ID[10],
    everton: TEAM_VISUALS_BY_ID[45],
    fenerbahce: TEAM_VISUALS_BY_ID[611],
    feyenoord: TEAM_VISUALS_BY_ID[209],
    fiorentina: TEAM_VISUALS_BY_ID[502],
    fulham: TEAM_VISUALS_BY_ID[36],
    galatasaray: TEAM_VISUALS_BY_ID[645],
    inter: TEAM_VISUALS_BY_ID[505],
    "inter milan": TEAM_VISUALS_BY_ID[505],
    juventus: TEAM_VISUALS_BY_ID[496],
    lazio: TEAM_VISUALS_BY_ID[487],
    liverpool: TEAM_VISUALS_BY_ID[40],
    lille: TEAM_VISUALS_BY_ID[79],
    lyon: TEAM_VISUALS_BY_ID[80],
    "manchester city": TEAM_VISUALS_BY_ID[50],
    "man city": TEAM_VISUALS_BY_ID[50],
    "manchester united": TEAM_VISUALS_BY_ID[33],
    "man united": TEAM_VISUALS_BY_ID[33],
    marseille: TEAM_VISUALS_BY_ID[81],
    milan: TEAM_VISUALS_BY_ID[489],
    monaco: TEAM_VISUALS_BY_ID[91],
    napoli: TEAM_VISUALS_BY_ID[492],
    "newcastle united": TEAM_VISUALS_BY_ID[34],
    newcastle: TEAM_VISUALS_BY_ID[34],
    "paris saint germain": TEAM_VISUALS_BY_ID[85],
    porto: TEAM_VISUALS_BY_ID[212],
    psg: TEAM_VISUALS_BY_ID[85],
    psv: TEAM_VISUALS_BY_ID[197],
    "real madrid": TEAM_VISUALS_BY_ID[541],
    roma: TEAM_VISUALS_BY_ID[497],
    sevilla: TEAM_VISUALS_BY_ID[536],
    southampton: TEAM_VISUALS_BY_ID[41],
    sporting: TEAM_VISUALS_BY_ID[228],
    "sporting cp": TEAM_VISUALS_BY_ID[228],
    tottenham: TEAM_VISUALS_BY_ID[47],
    valencia: TEAM_VISUALS_BY_ID[532],
    villarreal: TEAM_VISUALS_BY_ID[533],
    "west ham": TEAM_VISUALS_BY_ID[48],
    "west ham united": TEAM_VISUALS_BY_ID[48],
    wolves: TEAM_VISUALS_BY_ID[39],
  };

  function get(teamId, teamName) {
    const byId = TEAM_VISUALS_BY_ID[Number(teamId)];
    const byName = TEAM_VISUALS_BY_NAME[normaliseName(teamName)];
    const visual = byId || byName || DEFAULT_VISUAL;
    return buildVisual(visual);
  }

  function fromServer(serverVisual, teamId, teamName) {
    if (serverVisual && serverVisual.primary) {
      return {
        primary: serverVisual.primary,
        secondary: serverVisual.secondary || DEFAULT_VISUAL.secondary,
        glow: serverVisual.glow || withAlpha(serverVisual.primary, 0.24),
        softGlow: serverVisual.soft_glow || serverVisual.softGlow || withAlpha(serverVisual.primary, 0.14),
        border: serverVisual.border || withAlpha(serverVisual.primary, 0.62),
        shadow: serverVisual.shadow || withAlpha(serverVisual.primary, 0.34),
      };
    }
    return get(teamId, teamName);
  }

  function buildVisual(visual) {
    const primary = visiblePrimary(visual.primary, visual.secondary);
    return {
      primary,
      secondary: visual.secondary,
      glow: withAlpha(primary, 0.24),
      softGlow: withAlpha(primary, 0.14),
      border: withAlpha(primary, 0.62),
      shadow: withAlpha(primary, 0.34),
    };
  }

  function normaliseName(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function withAlpha(hex, alpha) {
    const rgb = hexToRgb(hex);
    if (!rgb) return `rgba(116, 119, 130, ${alpha})`;
    return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
  }

  function visiblePrimary(primary, secondary) {
    if (!isNearBlack(primary)) return primary;
    return isNearBlack(secondary) ? "#FFFFFF" : secondary;
  }

  function isNearBlack(hex) {
    const rgb = hexToRgb(hex);
    if (!rgb) return false;
    return rgb.r <= 42 && rgb.g <= 42 && rgb.b <= 42;
  }

  function hexToRgb(hex) {
    const clean = String(hex || "").replace("#", "").trim();
    if (!/^[0-9a-f]{6}$/i.test(clean)) return null;
    return {
      r: parseInt(clean.slice(0, 2), 16),
      g: parseInt(clean.slice(2, 4), 16),
      b: parseInt(clean.slice(4, 6), 16),
    };
  }

  window.AtmosTeamVisuals = { get, fromServer, withAlpha };
})();
