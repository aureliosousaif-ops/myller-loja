/* =========================================================================
   MYLLER — Painel administrativo
   Sidebar responsiva, confirmações, formset de variações e alertas.
   ========================================================================= */
(function () {
  'use strict';

  /* ------------------------------------------------------------ Sidebar */
  var sidebar = document.getElementById('painelSidebar');
  var fundo = document.getElementById('sidebarFundo');
  var abre = document.getElementById('abreSidebar');
  var fecha = document.getElementById('fechaSidebar');

  function abrirSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('aberto');
    if (fundo) fundo.classList.add('ativo');
    document.body.style.overflow = 'hidden';
  }

  function fecharSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('aberto');
    if (fundo) fundo.classList.remove('ativo');
    document.body.style.overflow = '';
  }

  if (abre) abre.addEventListener('click', abrirSidebar);
  if (fecha) fecha.addEventListener('click', fecharSidebar);
  if (fundo) fundo.addEventListener('click', fecharSidebar);
  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape') fecharSidebar();
  });

  /* --------------------------------------- Confirmação de ações destrutivas */
  document.addEventListener('submit', function (evento) {
    var formulario = evento.target;
    if (!(formulario instanceof HTMLFormElement)) return;
    if (evento.defaultPrevented) return;

    var aviso = formulario.getAttribute('data-confirm');
    if (aviso && !window.confirm(aviso)) {
      evento.preventDefault();
      return;
    }

    // Evita duplo clique: trava o botão de envio.
    var botao = formulario.querySelector('[type="submit"]');
    if (botao && !botao.disabled) {
      botao.disabled = true;
      botao.dataset.textoOriginal = botao.innerHTML;
      botao.insertAdjacentHTML('beforeend', ' <span class="spin"></span>');
    }
  });

  /* ------------------------------------------------- Alertas automáticos */
  var alertas = document.querySelectorAll('.painel-alerta');
  window.setTimeout(function () {
    alertas.forEach(function (alerta) {
      alerta.style.transition = 'opacity .4s ease, transform .4s ease';
      alerta.style.opacity = '0';
      alerta.style.transform = 'translateY(-6px)';
      window.setTimeout(function () {
        alerta.remove();
      }, 420);
    });
  }, 6000);

  /* ------------------------------------------------ Formset de variações */
  var botaoAdicionar = document.getElementById('adicionarLinha');
  var templateLinha = document.getElementById('formsetTemplate');

  function campoGestao(nome) {
    return document.querySelector('input[name$="-' + nome + '"]');
  }

  if (botaoAdicionar && templateLinha) {
    botaoAdicionar.addEventListener('click', function () {
      var total = campoGestao('TOTAL_FORMS');
      if (!total) return;

      var indice = parseInt(total.value, 10) || 0;
      var html = templateLinha.innerHTML.replace(/__prefix__/g, String(indice));

      var container = botaoAdicionar.parentElement;
      container.insertBefore(
        document.createRange().createContextualFragment(html),
        botaoAdicionar
      );

      total.value = String(indice + 1);

      var novaLinha = container.querySelectorAll('.formset-linha');
      var ultima = novaLinha[novaLinha.length - 1];
      if (ultima) {
        var foco = ultima.querySelector('select, input');
        if (foco) foco.focus();
      }
    });
  }

  // Remoção de linhas (classe .formset-remover, gerada no template)
  document.addEventListener('click', function (evento) {
    var alvo = evento.target.closest('[data-remover-linha]');
    if (!alvo) return;

    var linha = alvo.closest('.formset-linha');
    if (!linha) return;

    var marcadorExclusao = linha.querySelector('input[type="checkbox"][name$="-DELETE"]');
    if (marcadorExclusao) {
      // Linha já existente no banco: marca para excluir no próximo save.
      marcadorExclusao.checked = !marcadorExclusao.checked;
      linha.classList.toggle('marcada-exclusao', marcadorExclusao.checked);
      alvo.textContent = marcadorExclusao.checked ? 'Desfazer' : 'Remover';
      return;
    }

    var total = campoGestao('TOTAL_FORMS');
    var inicial = campoGestao('INITIAL_FORMS');
    var quantidade = document.querySelectorAll('.formset-linha').length;
    var minimo = inicial ? parseInt(inicial.value, 10) || 0 : 0;

    if (quantidade <= minimo) {
      window.alert('Ao menos uma variação deve permanecer no formulário.');
      return;
    }

    linha.remove();
    if (total) {
      total.value = String(Math.max((parseInt(total.value, 10) || 1) - 1, minimo));
    }
  });

  /* ------------------------------------- Envio duplo em botões de painel */
  document.querySelectorAll('form[data-unico-submit]').forEach(function (form) {
    form.addEventListener('submit', function () {
      var botao = form.querySelector('[type="submit"]');
      if (botao) botao.disabled = true;
    });
  });
})();
