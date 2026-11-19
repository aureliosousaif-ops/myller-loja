"""Funções auxiliares reutilizadas pelos testes automatizados do projeto MYLLER.

O nome do arquivo evita o padrão `test*.py` para não ser coletado como módulo
de testes pelo Django test runner.
"""
from decimal import Decimal

from categorias.models import Categoria
from clientes.models import Cliente
from produtos.models import Cor, Produto, Tamanho, Variacao
from django.contrib.auth.models import User


def criar_usuario(username="cliente", email="cliente@myller.com.br",
                  senha="senha-forte-123", **kwargs):
    """Cria (ou recupera) um usuário com senha conhecida."""
    usuario = User.objects.filter(username=username).first()
    if usuario is None:
        usuario = User.objects.create_user(
            username=username, email=email, password=senha, **kwargs
        )
    return usuario


def criar_staff(username="gerente", senha="senha-forte-123"):
    """Cria um usuário com permissão de staff (painel)."""
    usuario = criar_usuario(username=username, senha=senha)
    usuario.is_staff = True
    usuario.is_superuser = True
    usuario.save(update_fields=["is_staff", "is_superuser"])
    return usuario


def criar_cliente(usuario):
    cliente, _ = Cliente.objects.get_or_create(usuario=usuario)
    return cliente


def criar_categoria(nome="Masculino", **kwargs):
    defaults = {"descricao": f"Categoria {nome}"}
    defaults.update(kwargs)
    return Categoria.objects.get_or_create(nome=nome, defaults=defaults)[0]


def criar_produto(nome="Camiseta MYLLER", preco="149.90", promo=None,
                  estoque=10, status=Produto.Status.PUBLICADO, categoria=None,
                  tamanhos=None, cores=None, **kwargs):
    """Cria um produto publicado com tamanho/cor padrão e estoque."""
    categoria = categoria or criar_categoria()
    produto = Produto.objects.create(
        nome=nome,
        categoria=categoria,
        descricao=f"Descrição detalhada do produto {nome}.",
        preco=Decimal(preco),
        preco_promocional=Decimal(promo) if promo else None,
        status=status,
        **kwargs,
    )
    tamanhos = tamanhos or [Tamanho.objects.get_or_create(
        nome="M", defaults={"ordem": 3})[0]]
    cores = cores or [Cor.objects.get_or_create(
        nome="Branco", defaults={"codigo_hex": "#FFFFFF"})[0]]

    for tamanho in tamanhos:
        for cor in cores:
            Variacao.objects.create(
                produto=produto,
                tamanho=tamanho,
                cor=cor,
                estoque=estoque,
                sku=f"{produto.sku}-{tamanho.nome}-{cor.nome}",
            )
    return produto


def primeira_variacao(produto):
    return produto.variacoes.select_related("tamanho", "cor").first()


def dados_checkout(**extra):
    """Payload válido do formulário de checkout."""
    dados = {
        "nome": "Maria Silva",
        "email": "maria@example.com",
        "telefone": "(11) 99999-0000",
        "cep": "01310-100",
        "logradouro": "Av. Paulista",
        "numero": "1000",
        "complemento": "Apto 42",
        "bairro": "Bela Vista",
        "cidade": "São Paulo",
        "estado": "SP",
        "observacao": "Entregar no período da tarde.",
    }
    dados.update(extra)
    return dados
