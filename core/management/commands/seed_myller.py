"""
Popula o banco com os dados de demonstração da MYLLER — moda feminina.

Uso:
    python manage.py seed_myller                # popula o que faltar (idempotente)
    python manage.py seed_myller --admin        # cria também um superusuário do painel

Regras:
    * Idempotente: rodar várias vezes não duplica nada.
    * Nunca apaga nem altera produtos criados manualmente.
    * Nunca mexe no estoque de produtos já existentes.
    * Todo produto criado por aqui nasce com ``demonstracao=True``.
    * Os produtos antigos de demonstração (catálogo genérico anterior) são
      apenas *ocultados* (status rascunho) — continuam 100% gerenciáveis
      pelo painel e podem ser republicados com um clique.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from categorias.models import Categoria
from core.models import ConfiguracaoLoja, PaginaInstitucional
from pedidos.models import CupomDesconto
from produtos.models import Cor, Produto, Tamanho, Variacao

# --------------------------------------------------------------------- catálogo
# (nome, categoria, preço, promocional, resumo, cores, estoque, destaque, novidade)
CATALOGO = [
    # ---------------------------------------------------------------- vestidos
    ("Vestido Elegance Midi", "Vestidos", 189.90, 149.90,
     "Vestido midi de cimento impecável, cintura marcada e saia esvoaçante.",
     ["Azul MYLLER", "Bege"], 12, True, True),
    ("Vestido Bella", "Vestidos", 199.90, None,
     "Transparência leve, decote elegante e caimento que valoriza a silhueta.",
     ["Off-white", "Preto"], 10, True, True),
    ("Vestido Slip Noite", "Vestidos", 179.90, None,
     "Viscose com brilho sutil e alças finas — a peça certa para a noite.",
     ["Azul marinho", "Off-white"], 8, False, True),
    ("Vestido Midi Plissado Íris", "Vestidos", 229.90, 189.90,
     "Plissê permanente que acompanha o movimento sem pesar no corpo.",
     ["Rosa antigo", "Azul claro"], 9, True, False),
    ("Vestido Ombro Afora Marina", "Vestidos", 169.90, None,
     "Ombro afora com babadinho na manga e comprimento acima do joelho.",
     ["Azul claro", "Bege"], 11, False, True),

    # ------------------------------------------------------------------ blusas
    ("Blusa Aurora", "Blusas", 89.90, 69.90,
     "Malha leve de toque fresco, perfeita para compor looks de trabalho.",
     ["Branco", "Azul claro"], 16, True, True),
    ("Blusa Canelada Essência", "Blusas", 79.90, None,
     "Canelado fino que abraça o corpo com conforto e stretch generoso.",
     ["Off-white", "Preto", "Bege"], 18, False, True),
    ("Blusa Seda Cetim Brisa", "Blusas", 129.90, 109.90,
     "Cetim com brilho discreto e babado no ombro para uma noite especial.",
     ["Off-white", "Rosa antigo"], 7, True, False),
    ("Blusa Tricô Leve", "Blusas", 119.90, None,
     "Tricô de fio fino com gola careca — abrigo sem volume.",
     ["Bege", "Azul claro"], 9, False, False),

    # --------------------------------------------------------------- croppeds
    ("Cropped Luna", "Croppeds", 69.90, None,
     "Cropped de decote redondo com acabamento duplo e caimento reto.",
     ["Bege", "Preto", "Off-white"], 14, True, True),
    ("Cropped Fitness Mia", "Croppeds", 59.90, None,
     "Tecnologia dry em compressão suave para treino e lazer.",
     ["Preto", "Azul MYLLER"], 15, False, False),
    ("Cropped Ribana Vera", "Croppeds", 74.90, 59.90,
     "Ribana de elástico confortável com manga raglan.",
     ["Rosa antigo", "Off-white"], 12, False, True),

    # ------------------------------------------------------------------ calças
    ("Calça Wide Leg Premium", "Calças", 159.90, 129.90,
     "Cintura alta e perna ampla em alfaiataria fluida que alonga a silhueta.",
     ["Azul marinho", "Preto", "Bege"], 14, True, True),
    ("Calça Alfaiataria Studio", "Calças", 189.90, None,
     "Pregas frontais marcadas e caimento retro — do escritório ao jantar.",
     ["Preto", "Azul MYLLER"], 10, True, False),
    ("Calça Jogger Conforto", "Calças", 119.90, None,
     "Jogger de sarja leve com cordão e bolsos embutidos.",
     ["Areia", "Carvão"], 13, False, True),
    ("Calça Cargo Feminina Terra", "Calças", 149.90, 129.90,
     "Cargo com bolso aplicado na lateral e cintura alta.",
     ["Areia", "Off-white"], 9, False, True),

    # ------------------------------------------------------------------- saias
    ("Saia Midi Sofia", "Saias", 129.90, None,
     "Midi de cintura alta com fenda discreta e tecido que não amassa.",
     ["Bege", "Preto"], 12, True, True),
    ("Saia Plissada Aura", "Saias", 139.90, 109.90,
     "Plissê leve com forro interno e movimento elegante ao andar.",
     ["Azul claro", "Rosa antigo"], 10, False, True),
    ("Saia Jeans Retrô", "Saias", 119.90, None,
     "Jeans com lavagem clássica, cós alto e viés lateral.",
     ["Azul MYLLER", "Areia"], 11, False, False),

    # ----------------------------------------------------------------- shorts
    ("Short Jeans Classic", "Shorts", 99.90, None,
     "Denim com lavagem média, barra desfiada e modelagem confortável.",
     ["Azul MYLLER", "Azul marinho"], 15, True, True),
    ("Short Alfaiataria Line", "Shorts", 89.90, 74.90,
     "Short de alfaiataria com prega frontal para um visual mais polido.",
     ["Preto", "Bege"], 12, False, True),
    ("Short Praia Solar", "Shorts", 69.90, None,
     "Tecido secagem rápida com forro e elástico embutido.",
     ["Azul claro", "Off-white"], 16, False, False),

    # --------------------------------------------------------------- conjuntos
    ("Conjunto Serena", "Conjuntos", 219.90, 189.90,
     "Blusa e calça em alfaiataria fluida — um look completo em uma peça.",
     ["Bege", "Azul MYLLER"], 10, True, True),
    ("Conjunto Essence", "Conjuntos", 249.90, None,
     "Dois em um de tricô fino com calça de perna reta e cintura alta.",
     ["Off-white", "Carvão"], 8, True, True),
    ("Conjunto Tricô Inverno", "Conjuntos", 199.90, None,
     "Suéter e saia coordenados em fio quente com textura canelada.",
     ["Bege", "Rosa antigo"], 9, False, True),
    ("Conjunto Linho Verão", "Conjuntos", 229.90, 199.90,
     "Linho misto respirável com blusa de manga bufante e short alongado.",
     ["Off-white", "Areia"], 7, False, True),

    # --------------------------------------------------------------- jaquetas
    ("Jaqueta Jeans Urbana", "Jaquetas", 259.90, None,
     "Jeans com lavagem stone, recortes na frente e botões envelhecidos.",
     ["Azul MYLLER", "Azul marinho"], 8, True, True),
    ("Blazer Alfaiataria Nômade", "Jaquetas", 289.90, 239.90,
     "Blazer de ombro estruturado com forro listrado e lapela fina.",
     ["Bege", "Preto"], 7, True, False),
    ("Jaqueta Corta-Vento Leve", "Jaquetas", 179.90, None,
     "Impermeável com capuz dobrável e bolso interno para o celular.",
     ["Azul MYLLER", "Carvão"], 11, False, True),

    # ---------------------------------------------------------------- camisas
    ("Camisa Urban Chic", "Camisas", 139.90, None,
     "Popeline com colarinho estruturado e corte oversized elegante.",
     ["Branco", "Azul claro"], 13, True, True),
    ("Camisa Linho Areia", "Camisas", 149.90, 119.90,
     "Linho misto com toque natural e manga de punho ajustável.",
     ["Areia", "Off-white"], 9, False, True),
    ("Camisa Oversized Brisa", "Camisas", 129.90, None,
     "Volume generoso, ombro caído e barra arredondada para um visual descontraído.",
     ["Off-white", "Rosa antigo"], 12, False, True),

    # ------------------------------------------------------------- acessórios
    ("Bolsa Tote Couro Areia", "Acessórios", 279.90, 239.90,
     "Tote estruturada com alças em couro sintético e bolso interno com zíper.",
     ["Bege"], 6, True, True),
    ("Bolsa Mini Cinturão Azul", "Acessórios", 189.90, None,
     "Mini bolsa com corrente removível e fecho magnético.",
     ["Azul MYLLER", "Preto"], 7, False, True),
    ("Lenço de Seda Sereno", "Acessórios", 89.90, 69.90,
     "Seda sintética 90x90 com estampa geométrica em tons de azul e bege.",
     ["Azul claro", "Bege"], 14, False, True),
]

# Descrição complementar por categoria (composta com o resumo de cada produto).
COMPLEMENTO = {
    "Vestidos": (
        "Peça de vestir completa: caimento testado em corpo real, forro suave "
        "e zíper embutido nas costuras."
    ),
    "Blusas": (
        "Uma base versátil que combina com alfaiataria, jeans e saias midi."
    ),
    "Croppeds": (
        "Pequena no tamanho, confortável no uso — perfeita com high waist."
    ),
    "Calças": (
        "Cintura alta com elástico interno discreto para manter a linha limpa."
    ),
    "Saias": (
        "Cós estruturado e tecido com queda — não marca o corpo."
    ),
    "Shorts": (
        "Comprimento pensado para o dia a dia, com forro em todas as cores claras."
    ),
    "Conjuntos": (
        "Coordenado que já resolve o look — use junto ou separe as peças."
    ),
    "Jaquetas": (
        "Estrutura leve com forro respirável para transitar entre estações."
    ),
    "Camisas": (
        "Perfeita abrindo por cima de regatas ou fechada com alfaiataria."
    ),
    "Acessórios": (
        "O detalhe que muda tudo: fechos metálicos, forro interno e acabamento à mão."
    ),
}

CARENCIA_LEGADA = [
    # catálogo anterior (genérico) — apenas ocultado, nunca apagado
    "Camiseta Essencial MYLLER", "Camiseta Tech Comfort", "Calça Alfaiataria Premium",
    "Bermuda Cargo Urbana", "Vestido Midi Essência", "Vestido Chemise Conforto",
    "Camiseta Feminina Soft", "Calça Wide Leg MYLLER", "Tênis Minimal Street",
    "Mocassim Couro Premium", "Relógio MYLLER Time", "Bolsa Estrutura Bege",
    "Boné Logotipo MYLLER", "Camiseta Oversized Statement",
]


class Command(BaseCommand):
    help = "Popula o banco com dados de demonstração da MYLLER (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin",
            action="store_true",
            help="Cria/atualiza um superusuário para o painel (admin/admin123 por padrão).",
        )

    # ---------------------------------------------------------------- helpers
    def _get_or_create(self, modelo, lookup, defaults=None, rotulo="registro"):
        obj, criado = modelo.objects.get_or_create(**lookup, defaults=defaults or {})
        if criado:
            self.stdout.write(f"  + {rotulo}")
        return obj

    def _atualizar_se_padrao(self, obj, campo, valor, padroes):
        """Só escreve se o valor atual ainda for um padrão (não mexe em customização)."""
        atual = getattr(obj, campo)
        if atual in padroes:
            setattr(obj, campo, valor)
            return True
        return False

    # ------------------------------------------------------------- execução
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Populando dados MYLLER (moda feminina)..."))

        self._configuracao()
        self._tamanhos_cores()
        categorias = self._categorias(categorias_raiz())
        self._ocultar_legado()
        self._produtos(categorias)
        self._cupons()
        self._paginas()

        if options["admin"]:
            self._admin()

        self.stdout.write(self.style.SUCCESS("Concluído."))
        if not options["admin"]:
            self.stdout.write(
                "Dica: use --admin para criar o usuário administrador do painel."
            )

    # --------------------------------------------------------------- dados
    def _configuracao(self):
        loja = ConfiguracaoLoja.carregar()
        atualizacoes = {}
        campos_padrao = {
            "nome_loja": "MYLLER",
            "banner_titulo": "MYLLER",
            "banner_subtitulo": "Essência, estilo e tecnologia em cada detalhe.",
            "banner_botao_texto": "Comprar agora",
            "banner_botao_link": "/produtos/",
            "telefone_contato": "(63) 9107-3145",
            "whatsapp": "6391073145",
            "cnpj": "12.345.678/0001-90",
            "endereco_loja": "Av. Paulista, 1000 — São Paulo/SP",
            "instagram": "https://www.instagram.com/myller_my/",
            "facebook": "https://facebook.com/myller",
            "youtube": "https://youtube.com/@myller",
            "meta_description": (
                "MYLLER — roupas e acessórios premium com design sofisticado, "
                "conforto e tecnologia em cada coleção."
            ),
        }
        for campo, valor in campos_padrao.items():
            if not getattr(loja, campo):
                atualizacoes[campo] = valor

        # Copy editorial da nova homepage (só substitui valores ainda padrão)
        editoriais = [
            ("banner_titulo", "SEU ESTILO, SUA ESSÊNCIA.",
             ("MYLLER", "myller", "Moda premium, essência e tecnologia")),
            ("banner_subtitulo",
             "Descubra peças que combinam com você. Vista sua personalidade com MYLLER.",
             ("Essência, estilo e tecnologia em cada detalhe.",
              "Descubra uma nova forma de expressar quem você é.")),
            ("banner_botao_texto", "EXPLORAR COLEÇÃO", ("Comprar agora", "Comprar agora ",)),
            ("banner_botao_link", "/produtos/", ("#",)),
            ("telefone_contato", "(63) 9107-3145",
             ("(11) 4002-8922", "(63) 9107-3145", "")),
            ("whatsapp", "6391073145", ("1140028922", "6391073145", "")),
            ("instagram", "https://www.instagram.com/myller_my/",
             ("https://instagram.com/myller", "https://www.instagram.com/myller_my/", "")),
            ("titulo_novidades", "Novidades", ("Novidades",)),
            ("titulo_mais_vendidos", "Mais vendidos da MYLLER", ("Mais vendidos",)),
            ("titulo_categorias", "Coleção feminina", ("Categorias em destaque",)),
            ("titulo_promocoes", "Ofertas especiais", ("Promoções",)),
            ("newsletter_titulo", "Entre para o universo MYLLER",
             ("Entre para o universo MYLLER",)),
            ("frase_apresentacao",
             "A MYLLER veste mulheres reais: peças sofisticadas, confortáveis "
             "e feitas para durar além da temporada.",
             ("A MYLLER nasce para quem veste tecnologia como estilo de vida. "
              "Peças premium, design sofisticado e conforto em cada coleção.",)),
        ]
        for campo, valor, padroes in editoriais:
            if self._atualizar_se_padrao(loja, campo, valor, padroes):
                atualizacoes[campo] = valor

        if atualizacoes:
            for campo, valor in atualizacoes.items():
                setattr(loja, campo, valor)
            loja.save()
            self.stdout.write(f"  + Configurações da loja ({len(atualizacoes)} campos)")
        else:
            self.stdout.write("  = Configurações da loja já presentes")

    def _tamanhos_cores(self):
        tamanhos_seed = [
            ("PP", 1), ("P", 2), ("M", 3), ("G", 4), ("GG", 5), ("XG", 6),
            ("36", 20), ("37", 21), ("38", 22), ("39", 23), ("40", 24),
            ("41", 25), ("42", 26), ("43", 27), ("44", 28),
            ("Único", 99),
        ]
        for nome, ordem in tamanhos_seed:
            self._get_or_create(
                Tamanho, {"nome": nome}, {"ordem": ordem}, rotulo=f"Tamanho {nome}",
            )

        for nome, hexcor in [
            ("Branco", "#FFFFFF"),
            ("Preto", "#1A1A1A"),
            ("Azul MYLLER", "#275B85"),
            ("Azul claro", "#95C2DF"),
            ("Bege", "#C0B7A6"),
            ("Areia", "#D8CFC0"),
            ("Off-white", "#F1ECE4"),
            ("Azul marinho", "#1C4463"),
            ("Carvão", "#33383D"),
            ("Rosa antigo", "#D8BEBB"),
            ("Terracota", "#C39A85"),
        ]:
            self._get_or_create(
                Cor, {"nome": nome}, {"codigo_hex": hexcor}, rotulo=f"Cor {nome}",
            )

    def _categorias(self, raizes):
        categorias = {}
        for nome, ordem, icone, mostrar_home, descricao in raizes:
            categoria = self._get_or_create(
                Categoria,
                {"nome": nome},
                {
                    "ordem": ordem,
                    "icone": icone,
                    "mostrar_home": mostrar_home,
                    "descricao": descricao,
                    "ativa": True,
                },
                rotulo=f"Categoria {nome}",
            )
            # reposiciona no novo mapa de navegação sem apagar nada
            if categoria.ordem != ordem or not categoria.mostrar_home == mostrar_home:
                categoria.ordem = ordem
                categoria.mostrar_home = mostrar_home
                categoria.icone = icone
                categoria.save(update_fields=["ordem", "mostrar_home", "icone"])
            categorias[nome] = categoria

        # subcategorias do catálogo legado (mantidas, apenas reposicionadas)
        for nome, pai, ordem, icone in [
            ("Camisetas", "Masculino", 11, "bi-shirt"),
            ("Calças", "Masculino", 12, "bi-person"),
            ("Bermudas", "Masculino", 13, "bi-clipboard"),
            ("Vestidos", "Feminino", 21, "bi-handbag"),
            ("Camisetas", "Feminino", 22, "bi-shirt"),
            ("Calças", "Feminino", 23, "bi-person"),
        ]:
            if pai not in categorias:
                continue
            chave = f"{pai}:{nome}"
            categorias[chave] = self._get_or_create(
                Categoria,
                {"nome": f"{nome} {pai}", "pai": categorias[pai]},
                {"ordem": ordem, "icone": icone, "mostrar_home": False,
                 "descricao": f"{nome} para {pai}."},
                rotulo=f"Categoria {chave}",
            )
        return categorias

    def _ocultar_legado(self):
        """Oculta (não apaga) o catálogo genérico anterior e suas categorias-raiz."""
        ocultos = 0
        for nome in CARENCIA_LEGADA:
            produto = Produto.objects.filter(nome=nome).first()
            if produto is None:
                continue
            alterado = False
            if not produto.demonstracao:
                produto.demonstracao = True
                alterado = True
            if produto.status != Produto.Status.RASCUNHO:
                produto.status = Produto.Status.RASCUNHO
                alterado = True
            if alterado:
                produto.save(update_fields=["demonstracao", "status"])
                ocultos += 1
        if ocultos:
            self.stdout.write(
                f"  = {ocultos} produtos legados ocultados (status rascunho, "
                "nenhum apagado)"
            )

        for nome in ("Masculino", "Feminino", "Calçados"):
            categoria = Categoria.objects.filter(nome=nome, pai__isnull=True).first()
            if categoria and (categoria.ativa or categoria.mostrar_home):
                categoria.ativa = False
                categoria.mostrar_home = False
                categoria.save(update_fields=["ativa", "mostrar_home"])
                self.stdout.write(f"  = Categoria {nome} oculta do menu")

    def _produtos(self, categorias):
        tamanhos = {t.nome: t for t in Tamanho.objects.all()}
        cores = {c.nome: c for c in Cor.objects.all()}

        criados = 0
        for (nome, cat_nome, preco, promo, resumo, cors, estoque,
             destaque, novidade) in CATALOGO:
            if Produto.objects.filter(nome=nome).exists():
                continue  # idempotente: já foi criado antes

            categoria = categorias.get(cat_nome)
            if categoria is None:
                continue

            complemento = COMPLEMENTO.get(cat_nome, "")
            produto = Produto.objects.create(
                nome=nome,
                categoria=categoria,
                resumo=resumo,
                descricao=(
                    f"{resumo} {complemento}\n\n"
                    "• Tecido selecionado de toque macio e queda elegante\n"
                    "• Modelagem pensada para valorizar a silhueta\n"
                    "• Costuras reforçadas e acabamento premium\n"
                    "• Combina com peças neutras da coleção MYLLER\n\n"
                    "Cuidados: lavagem à mão ou máquina em ciclo delicado com "
                    "sabão neutro. Não usar alvejante. Secar à sombra.\n\n"
                    "Produto demonstrativo — imagens e estoque fictícios."
                ),
                preco=Decimal(str(preco)),
                preco_promocional=Decimal(str(promo)) if promo else None,
                status=Produto.Status.PUBLICADO,
                destaque_home=destaque,
                eh_novidade=novidade,
                demonstracao=True,
                peso_kg=Decimal("0.45"),
            )

            tam_nomes = ["Único"] if cat_nome == "Acessórios" else ["P", "M", "G", "GG"]
            tam_objs = [tamanhos[t] for t in tam_nomes if t in tamanhos]
            cor_objs = [cores[c] for c in cors if c in cores] or list(cores.values())[:1]

            for tam in tam_objs:
                for cor in cor_objs:
                    Variacao.objects.create(
                        produto=produto,
                        tamanho=tam,
                        cor=cor,
                        sku=(f"{produto.sku}-{slugify(tam.nome)[:4].upper()}-"
                             f"{slugify(cor.nome)[:5].upper()}"),
                        estoque=estoque,
                    )
            criados += 1

        if criados:
            self.stdout.write(f"  + {criados} produtos femininos com variações e estoque")
        else:
            self.stdout.write("  = Produtos já existentes (nada criado)")

    def _cupons(self):
        self._get_or_create(
            CupomDesconto,
            {"codigo": "MYLLER10"},
            {
                "tipo": CupomDesconto.Tipo.PERCENTUAL,
                "valor": Decimal("10"),
                "descricao": "10% de desconto na primeira compra.",
                "ativo": True,
            },
            rotulo="Cupom MYLLER10",
        )
        self._get_or_create(
            CupomDesconto,
            {"codigo": "BEMVINDO30"},
            {
                "tipo": CupomDesconto.Tipo.FIXO,
                "valor": Decimal("30"),
                "pedido_minimo": Decimal("200"),
                "descricao": "R$ 30 de desconto em compras acima de R$ 200.",
                "ativo": True,
            },
            rotulo="Cupom BEMVINDO30",
        )

    def _paginas(self):
        paginas = [
            (
                "Sobre a MYLLER",
                "sobre",
                """
                <h2>Sobre a MYLLER</h2>
                <p>A MYLLER nasce para mulheres que vestem estilo como forma de
                expressão. Cada peça é pensada para unir sofisticação, conforto
                e uma estética minimalista que atravessa temporadas.</p>
                <p>Nossa coleção feminina vai do vestido de festa à camisa de
                escritório, passando por conjuntos, alfaiataria e acessórios —
                sempre com materiais selecionados e acabamento premium.</p>
                <h3>Nossos valores</h3>
                <ul>
                  <li><strong>Qualidade real:</strong> costuras reforçadas, tecidos
                  testados e controle de estoque por variação.</li>
                  <li><strong>Transparência:</strong> preços claros, prazos honestos
                  e política de troca simples.</li>
                  <li><strong>Próximo do cliente:</strong> atendimento humano por
                  WhatsApp e acompanhamento de pedido em tempo real.</li>
                </ul>
                """,
            ),
            (
                "Trocas e Devoluções",
                "trocas-e-devolucoes",
                """
                <h2>Trocas e Devoluções</h2>
                <p>Você tem até <strong>7 dias corridos</strong> após o recebimento
                para solicitar troca ou devolução, conforme o Código de Defesa do
                Consumidor (art. 49).</p>
                <h3>Como solicitar</h3>
                <ol>
                  <li>Acesse a sua conta e abra o pedido em <em>Meus pedidos</em>.</li>
                  <li>Envie uma mensagem para a WhatsApp da loja com o número do pedido.</li>
                  <li>Em até 2 dias úteis você recebe as instruções de postagem.</li>
                </ol>
                <p>A peça deve estar sem uso, com etiquetas e embalagem original.
                O reembolso é feito pelo mesmo meio de pagamento após a chegada
                do produto em nosso centro de distribuição.</p>
                """,
            ),
            (
                "Termos de Uso",
                "termos",
                """
                <h2>Termos de Uso</h2>
                <p>Ao criar uma conta ou realizar uma compra na MYLLER, você
                concorda com as regras abaixo. Leia com atenção.</p>
                <h3>Conta do cliente</h3>
                <ul>
                  <li>As informações cadastrais devem ser verdadeiras e estar
                  atualizadas.</li>
                  <li>Sua senha é de uso pessoal e não deve ser compartilhada.</li>
                  <li>Você pode encerrar a sessão e solicitar a exclusão dos seus
                  dados a qualquer momento pelo atendimento.</li>
                </ul>
                <h3>Pedidos e pagamentos</h3>
                <ul>
                  <li>O pedido é confirmado somente após a aprovação do
                  pagamento pelo meio de pagamento escolhido.</li>
                  <li>Preços e disponibilidade podem ser alterados antes da
                  confirmação da compra.</li>
                </ul>
                <h3>Conteúdo e propriedade</h3>
                <p>Imagens, textos e marca MYLLER são protegidos. É vedada a
                reprodução comercial sem autorização.</p>
                """,
            ),
            (
                "Política de Privacidade",
                "privacidade",
                """
                <h2>Política de Privacidade</h2>
                <p>Respeitamos a sua privacidade. Dados pessoais são coletados apenas
                para processar pedidos, emitir notas fiscais e melhorar sua experiência
                de compra.</p>
                <h3>Coleta e uso</h3>
                <ul>
                  <li>Nome, e-mail, telefone e endereço: necessários para entrega.</li>
                  <li>Dados de pagamento: processados pelo gateway contratado
                  (Mercado Pago ou Stripe) — não armazenamos números de cartão.</li>
                  <li>Navegação: cookies essenciais de sessão e carrinho.</li>
                </ul>
                <p>Você pode solicitar a exclusão dos seus dados a qualquer
                momento pelo atendimento da loja — fale conosco pelo WhatsApp
                ou Instagram, links disponíveis no rodapé do site.</p>
                """,
            ),
            (
                "Entregas e Prazos",
                "entregas",
                """
                <h2>Entregas e Prazos</h2>
                <p>Entregamos para todo o Brasil. O frete é calculado no carrinho
                e no checkout conforme o CEP de destino e o peso dos itens.</p>
                <ul>
                  <li><strong>Frete estimado:</strong> quando a cotação automática
                  não está disponível, exibimos a tabela da loja identificada como
                  estimativa.</li>
                  <li><strong>Frete grátis:</strong> válido para pedidos acima do
                  valor configurado na loja.</li>
                  <li><strong>Prazo:</strong> contado em dias úteis após a
                  confirmação do pagamento.</li>
                </ul>
                <p>O rastreamento fica disponível em <em>Meus pedidos</em> assim
                que o pedido sai para entrega.</p>
                """,
            ),
        ]
        for titulo, slug, conteudo in paginas:
            self._get_or_create(
                PaginaInstitucional,
                {"slug": slug},
                {"titulo": titulo, "conteudo": conteudo.strip(), "ativa": True},
                rotulo=f"Página {titulo}",
            )

    def _admin(self):
        username = "admin"
        senha = "admin123"
        usuario = User.objects.filter(username=username).first()
        if usuario is None:
            User.objects.create_superuser(
                username=username, email="admin@myller.com.br", password=senha
            )
            self.stdout.write(
                self.style.WARNING(
                    f"  + Superusuário criado — login: {username} / senha: {senha}"
                )
            )
        else:
            if not usuario.is_superuser:
                usuario.is_superuser = True
                usuario.is_staff = True
                usuario.save(update_fields=["is_superuser", "is_staff"])
                self.stdout.write("  = Usuário promovido a superusuário")
            else:
                self.stdout.write("  = Superusuário já existente")
            self.stdout.write(
                f"    (senha mantida; redefina com: python manage.py changepassword {username})"
            )


def categorias_raiz():
    """Mapa de navegação da loja feminina: (nome, ordem, ícone, home, descrição)."""
    return [
        ("Vestidos", 10, "bi-bag-heart", True,
         "Vestidos midi, longos e curtos para todos os momentos."),
        ("Blusas", 20, "bi-shirt", True,
         "Blusas, tricôs e cetins que compõem o look de todo dia."),
        ("Croppeds", 30, "bi-stars", True,
         "Croppeds modernos paralooks despojados."),
        ("Calças", 40, "bi-person", True,
         "Wide leg, alfaiataria e jogger com cintura alta."),
        ("Saias", 50, "bi-flower1", True,
         "Midi, plissadas e jeans com caimento impecável."),
        ("Shorts", 60, "bi-sun", True,
         "Shorts de alfaiataria, jeans e praia."),
        ("Conjuntos", 70, "bi-collection", True,
         "Coordenados que resolvem o look em um toque."),
        ("Jaquetas", 80, "bi-cloud", True,
         "Jaquetas, blazers e corta-vento para transitar entre estações."),
        ("Camisas", 90, "bi-hand-index", True,
         "Camisas de popeline, linho e ombro caído."),
        ("Acessórios", 100, "bi-handbag", True,
         "Bolsas, lenços e detalhes que finalizam a produção."),
        ("Novidades", 500, "bi-stars", False, "Últimos lançamentos da coleção."),
        ("Promoções", 600, "bi-tag", False, "Ofertas especiais por tempo limitado."),
        # raízes do catálogo anterior — mantidas no banco, ocultas do menu
        ("Masculino", 810, "bi-gender-male", False, "Coleção masculina (legada)."),
        ("Feminino", 820, "bi-gender-female", False, "Coleção feminina (legada)."),
        ("Calçados", 830, "bi-shoe", False, "Calçados (legado)."),
    ]
