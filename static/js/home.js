/* ==========================================================================
   MYLLER — Homepage
   Carrosséis de produtos, navegação por teclado e microinterações.
   ========================================================================== */
(function () {
  "use strict";

  var reduzirMovimento =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------------------------------- Carrosséis ---- */
  function inicializarCarrossel(wrap) {
    var trilho = wrap.querySelector(".carrossel-trilho");
    if (!trilho) return;

    var botoes = Array.prototype.slice.call(
      wrap.querySelectorAll(".carrossel-nav")
    );

    function passo() {
      var card = trilho.querySelector(":scope > *");
      if (!card) return 320;
      var estilo = window.getComputedStyle(trilho);
      var gap = parseFloat(estilo.columnGap || estilo.gap || "24") || 24;
      return card.getBoundingClientRect().width + gap;
    }

    function quantos() {
      if (window.innerWidth > 992) return 2;
      if (window.innerWidth > 576) return 1;
      return 1;
    }

    botoes.forEach(function (botao) {
      botao.addEventListener("click", function () {
        var direcao = parseInt(botao.dataset.dir, 10) || 1;
        trilho.scrollBy({
          left: passo() * quantos() * direcao,
          behavior: reduzirMovimento ? "auto" : "smooth",
        });
      });
    });

    function atualizar() {
      var max = trilho.scrollWidth - trilho.clientWidth - 4;
      botoes.forEach(function (botao) {
        var esquerda = botao.dataset.dir === "-1";
        botao.disabled = esquerda
          ? trilho.scrollLeft <= 2
          : trilho.scrollLeft >= max;
      });
    }

    trilho.addEventListener("scroll", atualizar, { passive: true });
    window.addEventListener("resize", atualizar);

    // Navegação por teclado quando o carrossel está focado
    trilho.setAttribute("tabindex", "0");
    trilho.addEventListener("keydown", function (evento) {
      if (evento.key === "ArrowRight") {
        evento.preventDefault();
        trilho.scrollBy({ left: passo(), behavior: "smooth" });
      } else if (evento.key === "ArrowLeft") {
        evento.preventDefault();
        trilho.scrollBy({ left: -passo(), behavior: "smooth" });
      }
    });

    atualizar();
  }

  document.querySelectorAll("[data-carrossel]").forEach(inicializarCarrossel);

  /* --------------------------------- Newsletter: feedback sem recarregar -- */
  var formNewsletter = document.querySelector(".newsletter-form");
  if (formNewsletter) {
    formNewsletter.addEventListener("submit", function (evento) {
      var botao = formNewsletter.querySelector("button[type='submit']");
      if (botao) {
        var original = botao.innerHTML;
        botao.disabled = true;
        botao.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando...';
        setTimeout(function () {
          botao.disabled = false;
          botao.innerHTML = original;
        }, 4000);
      }
    });
  }
})();
