// Paste into the console on your own, logged-in Clashfinder page.
(() => {
  const desired = __DESIRED__;
  const festival = __FESTIVAL__;
  const setNumber = __SET__;
  const setName = __NAME__;
  if (!window.cg || cg.getName !== festival || !cg.isLoggedIn || cg.showOtherUser ||
      typeof modCgHl !== "function" || typeof pokeData !== "function") {
    throw new Error(`Open your own ${festival} Clashfinder while logged in, then try again.`);
  }
  const existing = [];
  for (const [name, value] of Object.entries(cg.hl[setNumber] || {})) {
    const appearances = value === "all"
      ? Array.from({length: cg.appearances[name] || 1}, (_, i) => i + 1)
      : value;
    if (!Array.isArray(appearances)) throw new Error(`Unrecognised set-${setNumber} highlight: ${name}`);
    for (const n of appearances) existing.push(`${name}(${n})`);
  }
  const desiredSet = new Set(desired);
  const existingSet = new Set(existing);
  const toRemove = existing.filter(short => !desiredSet.has(short));
  const toAdd = desired.filter(short => !existingSet.has(short));
  const previousGroup = cg.hlGroup;
  cg.hl[setNumber] = {};
  cg.hlGroup = String(setNumber);
  try { desired.forEach(short => modCgHl(short, "add")); }
  finally { cg.hlGroup = previousGroup; }
  const rename = cg.hlName[setNumber] !== setName;
  cg.hlName[setNumber] = setName;
  if (toRemove.length || toAdd.length || rename) {
    const update = {};
    update[`hl-name${setNumber}`] = setName;
    if (toRemove.length) update[`hl${setNumber}-sub`] = toRemove.join(",");
    if (toAdd.length) update[`hl${setNumber}-add`] = toAdd.join(",");
    pokeData(update);
  }
  console.info(`Set ${setNumber} now targets ${desired.length} scheduled screenings. Wait for “Highlights saved” on the page, then refresh.`);
})();
