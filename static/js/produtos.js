/* ==========================================================================
   MYLLER — Catálogo
   Filtros sem recarregar a página (Fetch + History API), filtros mobile,
   estado de carregamento e revelação dos produtos inseridos.
   ========================================================================== */
(function () {
  "use strict";

  var reduzirMovimento =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------------------------ Filtros no mobile ----- */
  var botaoFiltros = document.getElementById("btnFiltrosMobile");
  var painelFiltros = document.querySelector(".filtros");
  if (botaoFiltros && painelFiltros) {
    botaoFiltros.addEventListener("click", function () {
      var aberto = painelFiltros.classList.toggle("aberto");
      botaoFiltros.setAttribute("aria-expanded", aberto ? "true" : "false");
      botaoFiltros.innerHTML = aberto
        ? '<i class="bi bi-funnel-fill"></i> Ocultar filtros'
        : '<i class="bi bi-funnel"></i> Filtrar produtos';
      if (aberto) {
        painelFiltros.scrollIntoView({
          behavior: reduzirMovimento ? "auto" : "smooth",
          block: "start",
        });
      }
    });
  }

  /* ----------------------------------------- Filtros sem recarregar ------ */
  var wrap = document.getElementById("resultadosCatalogo");
  var formFiltros = document.getElementById("formFiltros");
  var formOrdenacao = document.getElementById("formOrdenacao");

  if (!wrap || !formFiltros) return;

  var carregando = false;

  function montarURL(form) {
    var params = new URLSearchParams(new FormData(form));
    var query = params.toString();
    return window.location.pathname + (query ? "?" + query : "");
  }

  function revelarInseridos() {
    var elementos = Array.prototype.slice.call(
      wrap.querySelectorAll(".animar")
    );
    if (!elementos.length) return;

    if (reduzirMovimento || !("IntersectionObserver" in window)) {
      elementos.forEach(function (el) {
        el.classList.add("visivel");
      });
      return;
    }

    var observador = new IntersectionObserver(
      function (entradas) {
        entradas.forEach(function (entrada) {
          if (entrada.isIntersecting) {
            var indice = elementos.indexOf(entrada.target);
            setTimeout(function () {
              entrada.target.classList.add("visivel");
            }, Math.max(indice, 0) * 55);
            observador.unobserve(entrada.target);
          }
        });
      },
      { threshold: 0.08 }
    );
    elementos.forEach(function (el) {
      observador.observe(el);
    });
  }

  async function atualizar(url, empilhar) {
    if (carregando) return;
    carregando = true;
    wrap.classList.add("carregando");

    try {
      var resposta = await fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      if (!resposta.ok) throw new Error("HTTP " + resposta.status);

      var html = await resposta.text();
      var documento = new DOMParser().parseFromString(html, "text/html");
      var novosResultados = documento.getElementById("resultadosCatalogo");
      if (!novosResultados) throw new Error("Estrutura inesperada");

      wrap.innerHTML = novosResultados.innerHTML;

      var contagemNova = documento.querySelector(".contagem-produtos");
      var contagemAtual = document.querySelector(".contagem-produtos");
      if (contagemNova && contagemAtual) {
        contagemAtual.textContent = contagemNova.textContent;
      }

      if (empilhar !== false) {
        history.pushState({ myllerCatalogo: true }, "", url);
      }

      revelarInseridos();
      window.dispatchEvent(
        new CustomEvent("myller:catalogo-atualizado", { detail: { url: url } })
      );
    } catch (erro) {
      // Fallback: navegação completa mantém a funcionalidade garantida
      window.location.href = url;
      return;
    } finally {
      wrap.classList.remove("carregando");
      carregando = false;
    }
  }

  [formFiltros, formOrdenacao].forEach(function (form) {
    if (!form) return;
    form.addEventListener("submit", function (evento) {
      evento.preventDefault();
      atualizar(montarURL(form), true);
    });
  });

  // Botões de tamanho: clique no label dispara submit já tratado acima
  window.addEventListener("popstate", function (evento) {
    if (evento.state && evento.state.myllerCatalogo) {
      atualizar(
        window.location.pathname + window.location.search,
        false
      );
    } else {
      window.location.reload();
    }
  });

  revelarInseridos();
})();
