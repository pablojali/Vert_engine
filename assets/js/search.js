// Client-side search over /search.json.
// At VertLabs' scale (hundreds of athletes, dozens of races/year) this
// is enough - no need for an external index like Pagefind.

(async function () {
  const input = document.getElementById("search-input");
  const results = document.getElementById("search-results");
  if (!input || !results) return; // only runs on /search/

  const res = await fetch("/search.json");
  const index = await res.json();

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    results.innerHTML = "";
    if (!q) return;

    index
      .filter((item) => item.title.toLowerCase().includes(q))
      .slice(0, 20)
      .forEach((item) => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.href = item.url;
        a.textContent = item.title;
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = item.type;
        li.appendChild(a);
        li.appendChild(tag);
        results.appendChild(li);
      });
  });
})();
