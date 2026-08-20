// Live search + gender/race/year filters + pagination for /athletes/.
// Reuses the server-rendered rows (no separate JSON fetch, no duplicate
// data) - without JS every athlete is already listed in full, so this
// only adds the interactive layer on top. No-op on pages without
// .athletes-index.

(function () {
  const container = document.querySelector(".athletes-index");
  if (!container) return;

  const searchInput = document.getElementById("athlete-search");
  const genderPills = Array.from(container.querySelectorAll("[data-gender-filter]"));
  const raceSelect = document.getElementById("athlete-race-filter");
  const yearSelect = document.getElementById("athlete-year-filter");
  const loadMoreBtn = document.getElementById("athlete-load-more");
  const noResults = document.getElementById("athlete-no-results");
  const groups = Array.from(container.querySelectorAll(".athlete-group"));
  const rows = Array.from(container.querySelectorAll(".athlete-row"));

  const PAGE_SIZE = parseInt(container.dataset.pageSize, 10) || 100;
  let visibleCount = PAGE_SIZE;
  let activeGender = "";

  function isFiltering() {
    return !!(searchInput.value.trim() || activeGender || raceSelect.value || yearSelect.value);
  }

  function matches(row) {
    const q = searchInput.value.trim().toLowerCase();
    if (q && !row.dataset.name.includes(q)) return false;
    if (activeGender && row.dataset.gender !== activeGender) return false;
    if (raceSelect.value && !(row.dataset.races || "").split(",").includes(raceSelect.value)) return false;
    if (yearSelect.value && !(row.dataset.years || "").split(",").includes(yearSelect.value)) return false;
    return true;
  }

  // Once a search/filter is active, just show every match - filtered
  // sets here are always well under a page's worth (largest race/year
  // slice is under 100 runners), so there's no real pagination need.
  // Pagination only applies to the default, unfiltered A-Z browse.
  function render() {
    const filtering = isFiltering();
    let shown = 0;

    rows.forEach((row, i) => {
      const isMatch = matches(row);
      const visible = filtering ? isMatch : (isMatch && i < visibleCount);
      row.hidden = !visible;
      if (visible) shown++;
    });

    groups.forEach((group) => {
      group.hidden = !group.querySelector(".athlete-row:not([hidden])");
    });

    loadMoreBtn.hidden = filtering || visibleCount >= rows.length;
    noResults.hidden = shown > 0;
  }

  searchInput.addEventListener("input", render);
  raceSelect.addEventListener("change", render);
  yearSelect.addEventListener("change", render);

  genderPills.forEach((btn) => {
    btn.addEventListener("click", () => {
      activeGender = btn.dataset.genderFilter;
      genderPills.forEach((b) => b.classList.toggle("active", b === btn));
      render();
    });
  });

  loadMoreBtn.addEventListener("click", () => {
    visibleCount += PAGE_SIZE;
    render();
  });

  // The alpha-jump anchors only work if every row up to that letter is
  // already revealed - otherwise the browser jumps to a hidden target.
  // Reveal everything on click (only matters in the unfiltered/default
  // view - a filtered view already shows every match).
  container.querySelectorAll(".alpha-jump a").forEach((link) => {
    link.addEventListener("click", () => {
      if (!isFiltering()) {
        visibleCount = rows.length;
        render();
      }
    });
  });

  render();
})();
