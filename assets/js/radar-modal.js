document.addEventListener("DOMContentLoaded", function () {
  var modal = document.getElementById("radar-modal");
  var content = document.getElementById("radar-modal-content");
  if (!modal || !content) return;

  function openModal(svg) {
    content.innerHTML = "";
    content.appendChild(svg.cloneNode(true));
    modal.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    modal.hidden = true;
    document.body.style.overflow = "";
    content.innerHTML = "";
  }

  document.querySelectorAll("[data-radar-trigger]").forEach(function (trigger) {
    var svg = trigger.querySelector("svg");
    if (!svg) return;
    trigger.addEventListener("click", function () {
      openModal(svg);
    });
  });

  modal.querySelectorAll("[data-radar-close]").forEach(function (el) {
    el.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modal.hidden) closeModal();
  });
});
