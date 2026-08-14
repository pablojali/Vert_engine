// Lightweight auto-rotating carousel for the homepage's featured-race
// banner. No-op on pages without .featured-carousel.

(function () {
  document.querySelectorAll(".featured-carousel").forEach((carousel) => {
    const slides = carousel.querySelectorAll(".carousel-slide");
    const dots = carousel.querySelectorAll(".carousel-dot");
    const prevBtn = carousel.querySelector(".carousel-nav-prev");
    const nextBtn = carousel.querySelector(".carousel-nav-next");
    if (slides.length <= 1) return;

    let current = 0;
    let timer;

    function show(index) {
      slides[current].classList.remove("active");
      if (dots[current]) dots[current].classList.remove("active");
      current = (index + slides.length) % slides.length;
      slides[current].classList.add("active");
      if (dots[current]) dots[current].classList.add("active");
    }

    function restart() {
      clearInterval(timer);
      timer = setInterval(() => show(current + 1), 6000);
    }

    dots.forEach((dot, i) => {
      dot.addEventListener("click", () => {
        show(i);
        restart();
      });
    });

    if (prevBtn) prevBtn.addEventListener("click", () => { show(current - 1); restart(); });
    if (nextBtn) nextBtn.addEventListener("click", () => { show(current + 1); restart(); });

    carousel.addEventListener("mouseenter", () => clearInterval(timer));
    carousel.addEventListener("mouseleave", restart);

    restart();
  });
})();
