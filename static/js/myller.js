/* ==========================================================================
   MYLLER — JavaScript da loja (Fetch API, sem dependências externas)
   ========================================================================== */
(function () {
  "use strict";

  /* ------------------------------------------------------- Utilitários */
  function $(seletor, contexto) { return (contexto || document).querySelector(seletor); }
  function $$(seletor, contexto) { return Array.from((contexto || document).querySelectorAll(seletor)); }

  function moeda(valor) {
    const numero = parseFloat(valor);
    if (isNaN(numero)) return "R$ 0,00";
    return "R$ " + numero.toFixed(2).replace(".", ",");
  }

  function obterCSRF() {
    const cookie = document.cookie.split(";").find((c) => c.trim().startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
  }

  function postForm(url, dados) {
    const corpo = new URLSearchParams(dados);
    return fetch(url, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": obterCSRF(),
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      body: corpo,
    }).then((resposta) => resposta.json());
  }

  /* ------------------------------------------------------- Navbar fixa + animações */
  const navbar = $("#navbarLoja");
  if (navbar) {
    const aoRolar = () => navbar.classList.toggle("fixo", window.scrollY > 60);
    window.addEventListener("scroll", aoRolar, { passive: true });
    aoRolar();
  }

  const elementos = $$(".animar");
  if (elementos.length && "IntersectionObserver" in window) {
    const observador = new IntersectionObserver(
      (entradas) => {
        entradas.forEach((entrada, indice) => {
          if (entrada.isIntersecting) {
            setTimeout(() => entrada.target.classList.add("visivel"), indice * 60);
            observador.unobserve(entrada.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    elementos.forEach((el) => observador.observe(el));
  } else {
    elementos.forEach((el) => el.classList.add("visivel"));
  }

  /* ------------------------------------------------------- Alertas (auto-fechar) */
  setTimeout(() => {
    $$(".alerta, .painel-alerta").forEach((alerta) => {
      alerta.style.transition = "opacity .4s, transform .4s";
      alerta.style.opacity = "0";
      alerta.style.transform = "translateX(30px)";
      setTimeout(() => alerta.remove(), 420);
    });
  }, 5200);

  /* ------------------------------------------------------- Busca em tempo real */
  const inputBusca = $("#inputBusca");
  const caixaSugestoes = $("#sugestoesBusca");
  if (inputBusca && caixaSugestoes) {
    let temporizador = null;

    inputBusca.addEventListener("input", () => {
      const termo = inputBusca.value.trim();
      clearTimeout(temporizador);
      if (termo.length < 2) { caixaSugestoes.classList.remove("ativo"); return; }
      temporizador = setTimeout(async () => {
        try {
          const resposta = await fetch(`/api/busca/?q=${encodeURIComponent(termo)}`);
          const dados = await resposta.json();
          if (!dados.ok) return;
          if (!dados.resultados.length) {
            caixaSugestoes.innerHTML = '<div class="sugestoes-vazio">Nenhum produto encontrado.</div>';
          } else {
            caixaSugestoes.innerHTML = dados.resultados
              .map(
                (r) => `
                <a class="sugestao-item" href="${r.url}">
                  ${r.imagem ? `<img src="${r.imagem}" alt="">` : '<span style="width:40px"></span>'}
                  <span>
                    <span class="s-nome">${r.nome}</span><br>
                    <span class="s-cat">${r.categoria}</span>
                  </span>
                  <span class="s-preco">${r.preco}</span>
                </a>`
              )
              .join("");
          }
          caixaSugestoes.classList.add("ativo");
        } catch (erro) { /* rede indisponível — mantém silencioso */ }
      }, 220);
    });

    inputBusca.addEventListener("focus", () => {
      if (caixaSugestoes.innerHTML.trim()) caixaSugestoes.classList.add("ativo");
    });

    document.addEventListener("click", (evento) => {
      if (!evento.target.closest("#formBuscaTopo")) caixaSugestoes.classList.remove("ativo");
    });
  }

  /* ------------------------------------------------------- Favoritos */
  document.addEventListener("click", async (evento) => {
    const botao = evento.target.closest("[data-favorito]");
    if (!botao) return;
    evento.preventDefault();

    try {
      const dados = await postForm("/api/favoritos/alternar/", { produto_id: botao.dataset.favorito });
      if (!dados.ok && dados.login_necessario) {
        window.location.href = `/entrar/?next=${encodeURIComponent(window.location.pathname)}`;
        return;
      }
      botao.classList.toggle("ativo", dados.adicionado);
      const icone = botao.querySelector("i, bi");
      if (icone) {
        icone.className = dados.adicionado ? "bi bi-heart-fill" : "bi bi-heart";
      }
      if (dados.adicionado) {
        botao.animate(
          [{ transform: "scale(1)" }, { transform: "scale(1.3)" }, { transform: "scale(1)" }],
          { duration: 320 }
        );
      }
      avisar(dados.mensagem);
    } catch (erro) {
      avisar("Não foi possível atualizar os favoritos.");
    }
  });

  function avisar(texto) {
    if (!texto) return;
    let caixa = $("#caixaAlertas");
    if (!caixa) {
      caixa = document.createElement("div");
      caixa.id = "caixaAlertas";
      caixa.className = "alertas";
      document.body.appendChild(caixa);
    }
    const alerta = document.createElement("div");
    alerta.className = "alerta alerta-info";
    alerta.innerHTML = `<i class="bi bi-info-circle-fill"></i><div>${texto}</div>`;
    caixa.appendChild(alerta);
    setTimeout(() => {
      alerta.style.transition = "opacity .4s";
      alerta.style.opacity = "0";
      setTimeout(() => alerta.remove(), 420);
    }, 4000);
  }

  /* ------------------------------------------------------- Página do produto */
  const mapaEl = $("#mapaVariacoes");
  let mapaVariacoes = {};
  if (mapaEl) {
    try { mapaVariacoes = JSON.parse(mapaEl.textContent); } catch (erro) { mapaVariacoes = {}; }
  }

  // Galeria: miniaturas (troca suave com fade)
  const imgPrincipal = $("#imgPrincipal");
  const movimentoReduzido =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  $$(".miniatura").forEach((miniatura) => {
    miniatura.addEventListener("click", () => {
      if (!imgPrincipal) return;
      $$(".miniatura").forEach((m) => m.classList.remove("ativa"));
      miniatura.classList.add("ativa");

      const trocar = () => {
        imgPrincipal.src = miniatura.dataset.src;
        imgPrincipal.classList.remove("img-trocando");
      };

      if (movimentoReduzido) {
        trocar();
        return;
      }
      imgPrincipal.classList.add("img-trocando");
      setTimeout(trocar, 200);
    });
  });

  // Galeria: zoom
  const galeria = $("#galeriaPrincipal");
  if (galeria) {
    galeria.addEventListener("click", () => galeria.classList.toggle("zoom-ativo"));
    galeria.addEventListener("mousemove", (evento) => {
      const retangulo = galeria.getBoundingClientRect();
      const x = ((evento.clientX - retangulo.left) / retangulo.width) * 100;
      const y = ((evento.clientY - retangulo.top) / retangulo.height) * 100;
      if (imgPrincipal) imgPrincipal.style.transformOrigin = `${x}% ${y}%`;
    });
    galeria.addEventListener("mouseleave", () => galeria.classList.remove("zoom-ativo"));
  }

  // Seleção de tamanho/cor → variação
  const selecaoTamanho = $("#selecaoTamanho");
  const selecaoCor = $("#selecaoCor");
  const inputVariacao = $("#variacaoId");
  const avisoEstoque = $("#avisoEstoque");
  const btnAdd = $("#btnAddCarrinho");
  const precoUnitario = $("#precoUnitario");
  let tamanhoEscolhido = null;
  let corEscolhida = null;

  function atualizarVariacao() {
    if (!inputVariacao) return;
    const temOpcoes = !!selecaoTamanho || !!selecaoCor;
    if (!temOpcoes) return;

    const chave = `${tamanhoEscolhido || ""}|${corEscolhida || ""}`;
    const temTamanho = !!selecaoTamanho;
    const temCor = !!selecaoCor;
    const parcial = tamanhoEscolhido || corEscolhida;
    let variacao = mapaVariacoes[chave];

    // Se só existe uma opção em um dos lados, tenta completar automaticamente
    if (!variacao && parcial) {
      const chaves = Object.keys(mapaVariacoes);
      const candidata = chaves.find((k) => {
        const [t, c] = k.split("|");
        return (temTamanho ? t === tamanhoEscolhido : true) &&
               (temCor ? c === corEscolhida : true);
      });
      if (candidata) variacao = mapaVariacoes[candidata];
    }

    if (!variacao || !variacao.ativo || variacao.estoque <= 0) {
      inputVariacao.value = "";
      if (btnAdd) btnAdd.disabled = true;
      mostrarAviso(
        !parcial
          ? "Selecione " + [temTamanho ? "o tamanho" : "", temCor ? "a cor" : ""].filter(Boolean).join(" e ") + "."
          : "Essa combinação não está disponível no momento. Escolha outra opção.",
        !parcial ? "escasso" : "esgotado"
      );
      return;
    }

    inputVariacao.value = variacao.id;
    if (btnAdd) btnAdd.disabled = false;
    mostrarAviso(
      variacao.estoque <= 5
        ? `Últimas unidades: apenas ${variacao.estoque} disponível(is).`
        : `Em estoque: ${variacao.estoque} unidade(s).`,
      variacao.estoque <= 5 ? "escasso" : "disponivel"
    );
    if (precoUnitario && variacao.preco) precoUnitario.textContent = moeda(variacao.preco);

    const campoQtd = $("#quantidade");
    if (campoQtd) campoQtd.max = variacao.estoque;
  }

  function mostrarAviso(texto, classe) {
    if (!avisoEstoque) return;
    avisoEstoque.style.display = "flex";
    avisoEstoque.className = `aviso-estoque mb-3 ${classe}`;
    avisoEstoque.innerHTML = `<i class="bi ${classe === "disponivel" ? "bi-check-circle" : "bi-exclamation-circle"}"></i> ${texto}`;
  }

  if (selecaoTamanho) {
    $$(".chip-selecao", selecaoTamanho).forEach((chip) => {
      chip.addEventListener("click", () => {
        if (chip.disabled) return;
        $$(".chip-selecao", selecaoTamanho).forEach((c) => c.classList.remove("selecionado"));
        chip.classList.add("selecionado");
        tamanhoEscolhido = chip.dataset.tamanho;
        const rotulo = $("#rotuloTamanho");
        if (rotulo) rotulo.textContent = tamanhoEscolhido;
        atualizarVariacao();
      });
    });
  }

  if (selecaoCor) {
    $$(".chip-selecao", selecaoCor).forEach((chip) => {
      chip.addEventListener("click", () => {
        if (chip.disabled) return;
        $$(".chip-selecao", selecaoCor).forEach((c) => c.classList.remove("selecionado"));
        chip.classList.add("selecionado");
        corEscolhida = chip.dataset.cor;
        const rotulo = $("#rotuloCor");
        if (rotulo) rotulo.textContent = corEscolhida;
        atualizarVariacao();
      });
    });
  }

  // Quantidade
  const campoQtd = $("#quantidade");
  if (campoQtd) {
    const limite = () => parseInt(campoQtd.max || "99", 10);
    const alterar = (delta) => {
      let valor = parseInt(campoQtd.value || "1", 10) + delta;
      valor = Math.max(1, Math.min(valor, limite()));
      campoQtd.value = valor;
    };
    const btnDiminui = $("#diminuiQtd");
    const btnAumenta = $("#aumentaQtd");
    if (btnDiminui) btnDiminui.addEventListener("click", () => alterar(-1));
    if (btnAumenta) btnAumenta.addEventListener("click", () => alterar(1));
  }

  // Envio do formulário de adicionar ao carrinho
  const formAdd = $("#formAddCarrinho");
  if (formAdd) {
    formAdd.addEventListener("submit", (evento) => {
      const temOpcoes = !!selecaoTamanho || !!selecaoCor;
      if (temOpcoes && (!inputVariacao || !inputVariacao.value)) {
        evento.preventDefault();
        atualizarVariacao();
        mostrarAviso("Selecione o tamanho e a cor antes de adicionar.", "escasso");
        return;
      }
      if (btnAdd) {
        btnAdd.disabled = true;
        const original = btnAdd.innerHTML;
        btnAdd.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adicionando...';
        setTimeout(() => { btnAdd.innerHTML = original; btnAdd.disabled = false; }, 4000);
      }
    });
    atualizarVariacao();
  }

  // Abas do produto
  $$(".nav-aba").forEach((aba) => {
    aba.addEventListener("click", () => {
      $$(".nav-aba").forEach((a) => a.classList.remove("ativa"));
      $$(".conteudo-aba").forEach((c) => c.classList.remove("ativa"));
      aba.classList.add("ativa");
      const alvo = $(`#aba-${aba.dataset.aba}`);
      if (alvo) alvo.classList.add("ativa");
    });
  });

  /* ------------------------------------------------------- Carrinho: atualização AJAX */
  function recalcularResumo(dados) {
    const sub = $("#resumoSubtotal");
    const desc = $("#resumoDesconto");
    const frete = $("#resumoFrete");
    const total = $("#resumoTotal");
    if (sub && dados.subtotal !== undefined) sub.textContent = moeda(dados.subtotal);
    if (desc && dados.desconto !== undefined) {
      desc.textContent = "- " + moeda(dados.desconto);
      const linha = desc.closest(".linha-resumo");
      if (linha) linha.style.display = parseFloat(dados.desconto) > 0 ? "flex" : "none";
    }
    if (frete && dados.frete !== undefined && parseFloat(dados.frete) > 0) frete.textContent = moeda(dados.frete);
    if (total && dados.total !== undefined) total.textContent = moeda(dados.total);
    const contador = $("#contadorCarrinho");
    if (contador && dados.carrinho_qtd !== undefined) {
      contador.textContent = dados.carrinho_qtd;
      contador.classList.toggle("oculto", parseInt(dados.carrinho_qtd, 10) === 0);
    }
  }

  $$(".form-item-carrinho").forEach((form) => {
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const dados = Object.fromEntries(new FormData(form).entries());
      try {
        const resposta = await fetch(form.action, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": obterCSRF(),
          },
          body: new FormData(form),
        }).then((r) => r.json());

        if (!resposta.ok) { window.location.reload(); return; }

        const item = form.closest(".item-carrinho");
        const idItem = dados.item_id;
        if (resposta.quantidades && resposta.quantidades[idItem] !== undefined) {
          const qtd = resposta.quantidades[idItem];
          const spanQtd = item.querySelector(".qtd-atual");
          const inputQtd = item.querySelector(".qtd-valor");
          const botaoDiminui = item.querySelector('[value="diminuir"]');
          const botaoAumenta = item.querySelector('[value="aumentar"]');
          if (spanQtd) spanQtd.textContent = qtd;
          if (inputQtd) inputQtd.value = qtd;
          if (botaoDiminui) botaoDiminui.disabled = qtd <= 1;
          if (botaoAumenta && botaoAumenta.hasAttribute("data-estoque")) {
            botaoAumenta.disabled = qtd >= parseInt(botaoAumenta.dataset.estoque, 10);
          }
        }
        if (resposta.itens && resposta.itens[idItem] !== undefined && item) {
          const totalItem = item.querySelector(".item-total");
          if (totalItem) totalItem.textContent = moeda(resposta.itens[idItem]);
        }
        recalcularResumo(resposta);
      } catch (erro) {
        window.location.reload();
      }
    });
  });

  /* ------------------------------------------------------- Frete (CEP) */
  function mascaraCEP(campo) {
    let valor = campo.value.replace(/\D/g, "").slice(0, 8);
    if (valor.length > 5) valor = valor.slice(0, 5) + "-" + valor.slice(5);
    campo.value = valor;
  }

  $$("input[data-cep]").forEach((campo) => {
    campo.addEventListener("input", () => mascaraCEP(campo));
  });

  async function calcularFrete() {
    const campoCEP = $("#cepFrete");
    const caixa = $("#resultadoFrete");
    if (!campoCEP || !caixa) return;

    const cep = campoCEP.value.replace(/\D/g, "");
    if (cep.length !== 8) {
      caixa.style.display = "block";
      caixa.innerHTML = '<span class="nota-frete" style="color:var(--erro)">Informe um CEP com 8 dígitos.</span>';
      return;
    }

    const botao = $("#btnCalcularFrete");
    if (botao) { botao.disabled = true; botao.textContent = "Calculando..."; }

    try {
      const corpo = new URLSearchParams({ cep });
      const resposta = await fetch("/api/frete/", {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": obterCSRF(),
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        body: corpo,
      }).then((r) => r.json());

      caixa.style.display = "block";
      if (!resposta.ok) {
        caixa.innerHTML = `<span class="nota-frete" style="color:var(--erro)">${resposta.mensagem}</span>`;
      } else {
        caixa.innerHTML = `
          <div class="opcao-frete">
            <span><i class="bi bi-truck me-1"></i>${resposta.transportadora} — ${resposta.prazo}</span>
            <strong>${moeda(resposta.valor)}</strong>
          </div>
          <span class="nota-frete">${resposta.mensagem}</span>`;
        recalcularResumo(resposta);
        avisar("Frete calculado com sucesso.");
      }
    } catch (erro) {
      caixa.style.display = "block";
      caixa.innerHTML = '<span class="nota-frete" style="color:var(--erro)">Serviço de frete indisponível no momento.</span>';
    } finally {
      if (botao) { botao.disabled = false; botao.textContent = "Calcular frete"; }
    }
  }

  const btnFrete = $("#btnCalcularFrete");
  if (btnFrete) btnFrete.addEventListener("click", calcularFrete);
  const campoCEPFrete = $("#cepFrete");
  if (campoCEPFrete) {
    campoCEPFrete.addEventListener("input", () => mascaraCEP(campoCEPFrete));
    campoCEPFrete.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter") { evento.preventDefault(); calcularFrete(); }
    });
  }

  /* ------------------------------------------------------- Autocompletar endereço (ViaCEP) */
  $$("input[data-cep]").forEach((campoCEP) => {
    campoCEP.addEventListener("blur", async () => {
      const cep = campoCEP.value.replace(/\D/g, "");
      if (cep.length !== 8) return;
      try {
        const resposta = await fetch(`/api/cep/${cep}/`);
        if (!resposta.ok) return;
        const dados = (await resposta.json()).endereco;
        if (!dados) return;
        const formulario = campoCEP.form;
        if (!formulario) return;
        const preencher = (nome, valor) => {
          const campo = formulario.querySelector(`[name="${nome}"]`);
          if (campo && !campo.value && valor) campo.value = valor;
        };
        preencher("logradouro", dados.logradouro);
        preencher("bairro", dados.bairro);
        preencher("cidade", dados.cidade);
        preencher("estado", dados.estado);
        const numero = formulario.querySelector('[name="numero"]');
        if (numero) numero.focus();
      } catch (erro) { /* ViaCEP fora do ar — deixa o usuário preencher */ }
    });
  });

  /* ------------------------------------------------------- Checkout: evitar duplo envio */
  const formCheckout = $("#formCheckout");
  if (formCheckout) {
    formCheckout.addEventListener("submit", (evento) => {
      const botao = $("#btnFinalizar");
      if (botao && !botao.disabled) {
        setTimeout(() => { botao.disabled = true; }, 10);
        botao.dataset.original = botao.innerHTML;
        setTimeout(() => {
          botao.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processando...';
        }, 15);
        setTimeout(() => {
          if (botao.disabled) {
            botao.disabled = false;
            botao.innerHTML = botao.dataset.original || botao.innerHTML;
          }
        }, 8000);
      }
    });
  }

  /* ------------------------------------------------------- Mostrar/ocultar senha */
  document.addEventListener("click", (evento) => {
    const gatilho = evento.target.closest("[data-alterna-senha]");
    if (!gatilho) return;
    const campo = document.getElementById(gatilho.dataset.alternaSenha);
    if (!campo) return;
    const oculta = campo.type === "password";
    campo.type = oculta ? "text" : "password";
    gatilho.setAttribute("aria-pressed", String(oculta));
    gatilho.querySelector("i")?.classList.toggle("bi-eye-slash", oculta);
    gatilho.querySelector("i")?.classList.toggle("bi-eye", !oculta);
  });
})();
