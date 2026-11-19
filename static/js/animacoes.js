/* ==========================================================================
   MYLLER — Animações globais e experiência interativa
   Barra de progresso · voltar ao topo · contador dinâmico · compra rápida ·
   voar-para-o-carrinho · revelação de banner · prefers-reduced-motion
   ========================================================================== */
(function () {
  "use strict";

  var reduzirMovimento =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function $(seletor, contexto) {
    return (contexto || document).querySelector(seletor);
  }
  function $$(seletor, contexto) {
    return Array.from((contexto || document).querySelectorAll(seletor));
  }

  function obterCSRF() {
    var cookie = document.cookie
      .split(";")
      .find(function (c) {
        return c.trim().startsWith("csrftoken=");
      });
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
  }

  function moeda(valor) {
    var numero = parseFloat(valor);
    if (isNaN(numero)) return "R$ 0,00";
    return "R$ " + numero.toFixed(2).replace(".", ",");
  }

  /* ------------------------------------------------- Toast de feedback ---- */
  function avisar(texto, tipo) {
    if (!texto) return;
    var caixa = $("#caixaAlertas");
    if (!caixa) {
      caixa = document.createElement("div");
      caixa.id = "caixaAlertas";
      caixa.className = "alertas";
      document.body.appendChild(caixa);
    }
    var alerta = document.createElement("div");
    alerta.className = "alerta alerta-" + (tipo || "info");
    alerta.innerHTML =
      '<i class="bi ' +
      (tipo === "success"
        ? "bi-check-circle-fill"
        : tipo === "error"
        ? "bi-x-circle-fill"
        : "bi-info-circle-fill") +
      '"></i><div></div>';
    alerta.querySelector("div").textContent = texto;
    caixa.appendChild(alerta);
    setTimeout(function () {
      alerta.style.transition = "opacity .4s";
      alerta.style.opacity = "0";
      setTimeout(function () {
        alerta.remove();
      }, 420);
    }, 3800);
  }

  /* -------------------------------------------- Barra de progresso -------- */
  (function barraProgresso() {
    var barra = $("#barraProgresso");
    if (!barra || reduzirMovimento) return;
    var preenchimento = barra.querySelector(".preenchimento");
    if (!preenchimento) return;

    barra.classList.add("ativa");
    preenchimento.style.width = "35%";

    function concluir() {
      preenchimento.style.width = "100%";
      barra.classList.add("concluida");
      setTimeout(function () {
        barra.classList.remove("ativa", "concluida");
        preenchimento.style.width = "0";
      }, 600);
    }

    if (document.readyState === "complete") {
      setTimeout(concluir, 150);
    } else {
      window.addEventListener("load", function () {
        setTimeout(concluir, 150);
      });
    }

    // Transições suaves entre páginas (navegação clássica)
    document.addEventListener("click", function (evento) {
      var link = evento.target.closest("a[href]");
      if (!link) return;
      var alvo = link.getAttribute("href");
      if (
        !alvo ||
        alvo.charAt(0) !== "#" ||
        link.target === "_blank" ||
        link.hasAttribute("data-bs-toggle")
      )
        return;
      if (link.hostname !== window.location.hostname) return;
      if (alvo === "#") return;
      barra.classList.add("ativa");
      preenchimento.style.width = "65%";
    });
  })();

  /* ---------------------------------------------- Voltar ao topo ---------- */
  (function voltarAoTopo() {
    var botao = $("#btnTopo");
    if (!botao) return;

    function alternar() {
      botao.classList.toggle("visivel", window.scrollY > 480);
    }

    window.addEventListener("scroll", alternar, { passive: true });
    alternar();

    botao.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: reduzirMovimento ? "auto" : "smooth" });
    });
  })();

  /* ------------------------------------- Contador do carrinho animado ----- */
  (function contadorAnimado() {
    var contador = $("#contadorCarrinho");
    if (!contador || !("MutationObserver" in window)) return;

    var observador = new MutationObserver(function () {
      if (reduzirMovimento) return;
      contador.classList.remove("pulsa");
      void contador.offsetWidth; // reinicia a animação
      contador.classList.add("pulsa");
      setTimeout(function () {
        contador.classList.remove("pulsa");
      }, 380);
    });

    observador.observe(contador, { childList: true, characterData: true, subtree: true });
  })();

  function atualizarContador(valor) {
    var contador = $("#contadorCarrinho");
    if (!contador) return;
    contador.textContent = valor;
    contador.classList.toggle("oculto", parseInt(valor, 10) === 0);
  }

  /* ---------------------------------- Voar produto até o carrinho --------- */
  function voarParaCarrinho(imagemOrigem) {
    if (reduzirMovimento || !imagemOrigem) return;
    var alvo = $("#contadorCarrinho") || $('.acao-icone[href*="carrinho"]');
    if (!alvo) return;

    var origem = imagemOrigem.getBoundingClientRect();
    var destino = alvo.getBoundingClientRect();

    var clone = document.createElement("img");
    clone.src = imagemOrigem.currentSrc || imagemOrigem.src;
    clone.className = "voando";
    clone.style.left = origem.left + origem.width / 2 - 27 + "px";
    clone.style.top = origem.top + origem.height / 2 - 33 + "px";
    document.body.appendChild(clone);

    var dx = destino.left + destino.width / 2 - (origem.left + origem.width / 2);
    var dy = destino.top + destino.height / 2 - (origem.top + origem.height / 2);

    requestAnimationFrame(function () {
      clone.style.transform =
        "translate(" + dx + "px, " + dy + "px) scale(0.12) rotate(12deg)";
      clone.style.opacity = "0";
    });

    setTimeout(function () {
      clone.remove();
    }, 760);
  }

  /* ------------------------------------------- Revelação de banner -------- */
  (function revelarBanner() {
    var banners = $$(".revelar-banner");
    if (!banners.length) return;
    if (reduzirMovimento || !("IntersectionObserver" in window)) {
      banners.forEach(function (b) {
        b.classList.add("visivel");
      });
      return;
    }
    var observador = new IntersectionObserver(
      function (entradas) {
        entradas.forEach(function (entrada) {
          if (entrada.isIntersecting) {
            entrada.target.classList.add("visivel");
            observador.unobserve(entrada.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    banners.forEach(function (b) {
      observador.observe(b);
    });
  })();

  /* ============================================ COMPRA RÁPIDA (modal) ===== */
  (function compraRapida() {
    var modalEl = $("#modalCompraRapida");
    if (!modalEl || typeof bootstrap === "undefined") return;

    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    var estado = { dados: null, tamanho: null, cor: null, variacao: null };

    var elImagem = $("#crImagem");
    var elNome = $("#crNome");
    var elCategoria = $("#crCategoria");
    var elPreco = $("#crPreco");
    var elGrupoTamanho = $("#crGrupoTamanho");
    var elTamanhos = $("#crTamanhos");
    var elTamanhoValor = $("#crTamanhoValor");
    var elGrupoCor = $("#crGrupoCor");
    var elCores = $("#crCores");
    var elCorValor = $("#crCorValor");
    var elVariacao = $("#crVariacao");
    var elAviso = $("#crAviso");
    var elAdicionar = $("#crAdicionar");
    var elLink = $("#crLink");
    var elCorpo = $("#crCorpo");

    function lerJSON(id) {
      var no = document.getElementById(id);
      if (!no) return null;
      try {
        return JSON.parse(no.textContent);
      } catch (erro) {
        return null;
      }
    }

    function resolverVariacao() {
      if (!estado.dados) return null;
      var mapa = estado.dados.mapa || {};
      var chave = (estado.tamanho || "") + "|" + (estado.cor || "");
      var variacao = mapa[chave];

      if (!variacao) {
        var chaves = Object.keys(mapa);
        var candidata = chaves.find(function (k) {
          var partes = k.split("|");
          return (
            (!estado.tamanho || partes[0] === estado.tamanho) &&
            (!estado.cor || partes[1] === estado.cor)
          );
        });
        if (candidata) variacao = mapa[candidata];
      }
      return variacao || null;
    }

    function atualizarEstado() {
      var variacao = resolverVariacao();
      estado.variacao = variacao;

      if (!variacao) {
        elVariacao.value = "";
        elAdicionar.disabled = true;
        var pendencias = [];
        if (estado.dados.tamanhos.length > 1 && !estado.tamanho) pendencias.push("o tamanho");
        if (estado.dados.cores.length > 1 && !estado.cor) pendencias.push("a cor");
        elAviso.textContent = pendencias.length
          ? "Selecione " + pendencias.join(" e ") + "."
          : "Indisponível no momento.";
        elAviso.className = "cr-aviso alerta-cor";
        return;
      }

      elVariacao.value = variacao.id;
      elAdicionar.disabled = false;
      if (parseInt(variacao.estoque, 10) <= 5) {
        elAviso.textContent =
          "Últimas unidades: apenas " + variacao.estoque + " disponível(is).";
        elAviso.className = "cr-aviso alerta-cor";
      } else {
        elAviso.textContent = "Pronta para envio — " + variacao.estoque + " em estoque.";
        elAviso.className = "cr-aviso ok";
      }
    }

    function renderizarOpcoes() {
      var dados = estado.dados;

      // Tamanhos
      if (dados.tamanhos.length > 1) {
        elGrupoTamanho.style.display = "";
        elTamanhos.innerHTML = "";
        dados.tamanhos.forEach(function (t) {
          var chip = document.createElement("button");
          chip.type = "button";
          chip.className = "cr-chip";
          chip.textContent = t;
          chip.addEventListener("click", function () {
            estado.tamanho = t;
            $$(".cr-chip", elTamanhos).forEach(function (c) {
              c.classList.remove("selecionado");
            });
            chip.classList.add("selecionado");
            elTamanhoValor.textContent = t;
            atualizarEstado();
          });
          elTamanhos.appendChild(chip);
        });
        estado.tamanho = null;
        elTamanhoValor.textContent = "selecione";
      } else if (dados.tamanhos.length === 1) {
        elGrupoTamanho.style.display = "";
        estado.tamanho = dados.tamanhos[0];
        elTamanhoValor.textContent = estado.tamanho;
        elTamanhos.innerHTML =
          '<button type="button" class="cr-chip selecionado">' +
          estado.tamanho +
          "</button>";
      } else {
        elGrupoTamanho.style.display = "none";
        estado.tamanho = null;
      }

      // Cores
      if (dados.cores.length > 1) {
        elGrupoCor.style.display = "";
        elCores.innerHTML = "";
        dados.cores.forEach(function (c) {
          var chip = document.createElement("button");
          chip.type = "button";
          chip.className = "cr-chip cr-chip-cor";
          chip.style.background = c.hex;
          chip.title = c.nome;
          chip.setAttribute("aria-label", c.nome);
          chip.addEventListener("click", function () {
            estado.cor = c.nome;
            $$(".cr-chip", elCores).forEach(function (x) {
              x.classList.remove("selecionado");
            });
            chip.classList.add("selecionado");
            elCorValor.textContent = c.nome;
            atualizarEstado();
          });
          elCores.appendChild(chip);
        });
        estado.cor = null;
        elCorValor.textContent = "selecione";
      } else if (dados.cores.length === 1) {
        elGrupoCor.style.display = "";
        estado.cor = dados.cores[0].nome;
        elCorValor.textContent = estado.cor;
        elCores.innerHTML =
          '<button type="button" class="cr-chip cr-chip-cor selecionado" style="background:' +
          dados.cores[0].hex +
          '" title="' +
          dados.cores[0].nome +
          '"></button>';
      } else {
        elGrupoCor.style.display = "none";
        estado.cor = null;
      }

      atualizarEstado();
    }

    function abrir(botao) {
      var idOpcoes = botao.dataset.opcoes;
      var dados = lerJSON(idOpcoes);
      if (!dados) {
        window.location.href = botao.dataset.produto || "/produtos/";
        return;
      }

      estado = { dados: dados, tamanho: null, cor: null, variacao: null };

      if (dados.imagem) {
        elImagem.src = dados.imagem;
        elImagem.alt = dados.nome;
        elImagem.style.display = "";
      } else {
        elImagem.removeAttribute("src");
        elImagem.style.display = "none";
      }
      elNome.textContent = dados.nome;
      elCategoria.textContent = dados.categoria || "MYLLER";

      var htmlPreco = '<span class="valor">' + moeda(dados.preco) + "</span>";
      if (dados.preco_original) {
        var percentual = Math.round(
          (1 - parseFloat(dados.preco) / parseFloat(dados.preco_original)) * 100
        );
        htmlPreco +=
          '<span class="antigo">' +
          moeda(dados.preco_original) +
          '</span><span class="desconto">-' +
          percentual +
          "%</span>";
      }
      elPreco.innerHTML = htmlPreco;

      elAdicionar.disabled = true;
      elAdicionar.innerHTML =
        '<i class="bi bi-bag-plus me-2"></i>Adicionar ao carrinho';
      elAdicionar.classList.remove("adicionado");
      elLink.setAttribute("href", dados.produto);

      renderizarOpcoes();

      if (elCorpo) {
        elCorpo.classList.remove("entra");
        void elCorpo.offsetWidth;
        elCorpo.classList.add("entra");
      }

      modal.show();
    }

    // Delegação: qualquer botão de compra rápida da página
    document.addEventListener("click", function (evento) {
      var botao = evento.target.closest(".btn-compra-rapida");
      if (!botao) return;
      evento.preventDefault();
      abrir(botao);
    });

    // Adicionar ao carrinho via Fetch API
    elAdicionar.addEventListener("click", async function () {
      if (!estado.variacao) return;

      elAdicionar.disabled = true;
      elAdicionar.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>Adicionando...';

      try {
        var corpo = new URLSearchParams({
          variacao_id: estado.variacao.id,
          quantidade: 1,
        });
        var resposta = await fetch("/carrinho/adicionar/", {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": obterCSRF(),
            "Content-Type":
              "application/x-www-form-urlencoded;charset=UTF-8",
          },
          body: corpo.toString(),
        }).then(function (r) {
          return r.json();
        });

        if (!resposta.ok) {
          avisar(resposta.mensagem || "Não foi possível adicionar.", "error");
          elAdicionar.disabled = false;
          elAdicionar.innerHTML =
            '<i class="bi bi-bag-plus me-2"></i>Adicionar ao carrinho';
          return;
        }

        voarParaCarrinho(elImagem);
        atualizarContador(resposta.carrinho_qtd);
        avisar(resposta.mensagem || "Adicionado ao carrinho!", "success");

        elAdicionar.classList.add("adicionado");
        elAdicionar.innerHTML =
          '<i class="bi bi-check-circle me-2"></i>Adicionado!';

        setTimeout(function () {
          modal.hide();
          setTimeout(function () {
            elAdicionar.classList.remove("adicionado");
            elAdicionar.innerHTML =
              '<i class="bi bi-bag-plus me-2"></i>Adicionar ao carrinho';
            elAdicionar.disabled = false;
          }, 400);
        }, 1100);
      } catch (erro) {
        avisar("Falha na conexão. Tente novamente.", "error");
        elAdicionar.disabled = false;
        elAdicionar.innerHTML =
          '<i class="bi bi-bag-plus me-2"></i>Adicionar ao carrinho';
      }
    });
  })();

  /* =============================== Feedback de adicionar (cards/clássico) = */
  // Botões "Escolher opções" já levam à página; aqui cuidamos do fly visual
  // quando o usuário usa compra rápida (acima) — mantido para extensão.
})();
