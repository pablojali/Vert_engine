// Resizes .report-frame iframes (same-origin uploaded HTML reports) to
// exactly match their content height, so they flow as part of the page
// instead of showing as a boxed, scrollable window. No-op on pages
// without one.

(function () {
  function resize(iframe) {
    try {
      const doc = iframe.contentDocument || iframe.contentWindow.document;
      iframe.style.height = doc.documentElement.scrollHeight + "px";
    } catch (e) {
      // Cross-origin or not ready yet - leave the fallback height.
    }
  }

  document.querySelectorAll(".report-frame").forEach((iframe) => {
    iframe.addEventListener("load", () => {
      resize(iframe);

      try {
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        if (window.ResizeObserver) {
          new ResizeObserver(() => resize(iframe)).observe(doc.documentElement);
        }
      } catch (e) {
        // Cross-origin - the timed re-checks below are the fallback.
      }

      // Charts inside the report (Plotly, loaded from a CDN) can finish
      // rendering shortly after the iframe's own load event - a few
      // follow-up checks catch that growth even without ResizeObserver.
      [300, 800, 1500, 3000].forEach((delay) => setTimeout(() => resize(iframe), delay));
    });
  });

  window.addEventListener("resize", () => {
    document.querySelectorAll(".report-frame").forEach(resize);
  });
})();
