// Share button on athlete (and, later, race) pages: native OS share
// sheet when the browser supports it, otherwise the button reads "Copy
// link" and copies the canonical URL to the clipboard with a temporary
// "Link copied" confirmation. No dependencies, no popups. Dispatches a
// "vtl:share" CustomEvent on document (method: "native" | "copy_link") -
// not wired to any analytics provider today, just a hook a future one
// could listen to without touching this file.

(function () {
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback for browsers/contexts without the Clipboard API.
    return new Promise(function (resolve, reject) {
      var el = document.createElement("textarea");
      el.value = text;
      el.style.position = "fixed";
      el.style.opacity = "0";
      document.body.appendChild(el);
      el.focus();
      el.select();
      try {
        document.execCommand("copy") ? resolve() : reject(new Error("copy failed"));
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(el);
      }
    });
  }

  function notify(method, url) {
    document.dispatchEvent(new CustomEvent("vtl:share", { detail: { method: method, url: url } }));
  }

  var canNativeShare = !!navigator.share;

  document.querySelectorAll("[data-share]").forEach(function (button) {
    var label = button.querySelector("[data-share-label]");
    // Resting label: "Share" when the OS share sheet is available, else
    // "Copy link" - set once up front, so the button never claims a
    // capability the browser doesn't have.
    var restingLabel = canNativeShare
      ? (label ? label.textContent : "")
      : (button.getAttribute("data-share-copy-label") || (label ? label.textContent : ""));
    var copiedLabel = button.getAttribute("data-share-copied-label") || restingLabel;
    var resetTimer = null;

    if (!canNativeShare && label) label.textContent = restingLabel;

    button.addEventListener("click", function () {
      var url = button.getAttribute("data-share-url");
      var title = button.getAttribute("data-share-title") || "";
      var text = button.getAttribute("data-share-text") || "";
      if (!url) return;

      if (canNativeShare) {
        navigator.share({ title: title, text: text, url: url })
          .then(function () { notify("native", url); })
          .catch(function () { /* user cancelled or share failed - no-op */ });
        return;
      }

      copyText(url)
        .then(function () {
          notify("copy_link", url);
          if (label) {
            clearTimeout(resetTimer);
            label.textContent = copiedLabel;
            resetTimer = setTimeout(function () {
              label.textContent = restingLabel;
            }, 2000);
          }
        })
        .catch(function () { /* clipboard unavailable and fallback failed - leave label as-is */ });
    });
  });
})();
