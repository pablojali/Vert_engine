// Click-to-sort for the full race-roster tables on race/event pages
// (Pos, VPI, DMI, ER). Scoped to table.roster-table specifically - NOT
// the curated Top 10 tables inside posts, which reuse the same base
// .athlete-table styling but are a fixed, hand-picked list and stay as
// they are. No gender filter here: race.json has no reliable gender
// field yet (gender_rank is only populated for a handful of runners per
// race), so there's nothing solid to filter by. Plain <table> markup, so
// the roster is fully readable/usable with JS disabled - this only adds
// the interactive sort on top.

(function () {
  document.querySelectorAll("table.roster-table").forEach((table) => {
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    if (!thead || !tbody) return;

    const headers = Array.from(thead.querySelectorAll("th[data-sort-key]"));
    if (!headers.length) return;

    let activeHeader = null;
    let direction = 1; // 1 = ascending, -1 = descending

    headers.forEach((th) => {
      th.classList.add("sortable");
      th.addEventListener("click", () => {
        direction = th === activeHeader ? -direction : 1;
        activeHeader = th;

        headers.forEach((h) => h.classList.remove("sort-asc", "sort-desc"));
        th.classList.add(direction === 1 ? "sort-asc" : "sort-desc");

        const colIndex = Array.from(th.parentNode.children).indexOf(th);
        const rows = Array.from(tbody.querySelectorAll("tr"));

        rows.sort((rowA, rowB) => {
          const valA = parseFloat((rowA.children[colIndex].textContent || "").replace(",", "."));
          const valB = parseFloat((rowB.children[colIndex].textContent || "").replace(",", "."));
          const missingA = isNaN(valA);
          const missingB = isNaN(valB);
          if (missingA && missingB) return 0;
          if (missingA) return 1; // rows without a value ("—") always sort last
          if (missingB) return -1;
          return (valA - valB) * direction;
        });

        rows.forEach((row) => tbody.appendChild(row));
      });
    });
  });
})();
