document.addEventListener("DOMContentLoaded", function () {
  var modal = document.getElementById("video-modal");
  var player = document.getElementById("video-modal-player");
  if (!modal || !player) return;

  function openModal(src) {
    player.src = src;
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    player.play();
  }

  function closeModal() {
    modal.hidden = true;
    document.body.style.overflow = "";
    player.pause();
    player.removeAttribute("src");
    player.load();
  }

  document.querySelectorAll("[data-video-src]").forEach(function (trigger) {
    trigger.addEventListener("click", function (e) {
      // Video triggers can sit inside another clickable element (e.g. a
      // <summary> accordion header) - stop the click from also toggling
      // or navigating that ancestor.
      e.preventDefault();
      e.stopPropagation();
      openModal(trigger.getAttribute("data-video-src"));
    });
  });

  modal.querySelectorAll("[data-video-close]").forEach(function (el) {
    el.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modal.hidden) closeModal();
  });
});
