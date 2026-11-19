# MYLLER — Plataforma E-commerce

Sistema completo de comércio eletrônico construído com **Django 6.1** e **Python 3.13**:
loja virtual, carrinho, checkout, pedidos, estoque, área do cliente e painel administrativo
próprio — com testes automatizados em todos os módulos.

> Projeto pensado para produção: banco SQLite em desenvolvimento e PostgreSQL em produção,
> segredos somente em `.env`, CSRF em todos os formulários, rotas administrativas protegidas
> e **nenhuma simulação de aprovação de pagamento**.

---

## Sumário

1. [Funcionalidades](#1-funcionalidades)
2. [Tecnologias](#2-tecnologias)
3. [Instalação e execução](#3-instalação-e-execução)
4. [Estrutura do projeto](#4-estrutura-do-projeto)
5. [Mapa de rotas](#5-mapa-de-rotas)
6. [Fluxo de pagamento (sem simulação)](#6-fluxo-de-pagamento-sem-simulação)
7. [Estoque](#7-estoque)
8. [Frete e endereço](#8-frete-e-endereço)
9. [Segurança](#9-segurança)
10. [Testes](#10-testes)
11. [Deploy](#11-deploy)
12. [Integrações que exigem credenciais](#12-integrações-que-exigem-credenciais)
13. [Imagens e identidade visual](#13-imagens-e-identidade-visual)

---

## 1. Funcionalidades

### Loja (storefront)
- Home com destaques, novidades e promoções; páginas institucionais dinâmicas.
- Listagem de produtos com filtros (categoria, preço, tamanho, cor, ordenação), paginação
  e busca por AJAX (`/api/busca/`).
- Detalhe do produto com galeria, variações (tamanho/cor), avaliações e SEO/Open Graph.
- Carrinho completo via AJAX: adicionar, atualizar quantidade, remover, limpar, cupom de
  desconto e cálculo de frete — tudo com respostas JSON.
- Checkout com dados de contato, endereço (autocomplete ViaCEP), escolha de frete, cupom
  e revisão do pedido.
- Favoritos (alternância via AJAX, persistida por usuário).
- Área do cliente: perfil, endereços (múltiplos, endereço padrão), meus pedidos, detalhe do
  pedido com rastreio de status, alteração de senha e recuperação de senha por e-mail.

### Painel administrativo (`/painel/`)
- Dashboard com KPIs (faturamento, pedidos, ticket médio, estoque baixo) e gráficos em CSS
  puro (sem dependência de biblioteca externa).
- Produtos: CRUD completo, publicar/despublicar, variações inline (formset) e galeria de imagens.
- Pedidos: listagem com filtros, detalhe completo e atualização de status com trilha de
  alterações (histórico).
- Clientes: listagem com busca e detalhe com pedidos e endereços.
- Categorias, cupons de desconto, estoque (entrada/saída manual com motivo),
  newsletter (exportação CSV) e configurações da loja.
- Sidebar responsiva com destaque da rota ativa, confirmações de exclusão e trava de
  duplo envio em formulários.

### Domínio
- **11 apps**: `core`, `usuarios`, `clientes`, `categorias`, `produtos`, `estoque`,
  `carrinho`, `favoritos`, `pedidos`, `pagamentos`, `dashboard`.
- Status de pedido: `Aguardando pagamento` → `Pagamento aprovado` → `Em preparação` →
  `Enviado` → `Entregue`, mais `Cancelado`.
- Estoque baixado de forma **atômica** na criação do pedido e devolvido em caso de
  cancelamento.

---

## 2. Tecnologias

| Camada | Tecnologia |
| --- | --- |
| Backend | Django 6.1 (Python 3.13) |
| Frontend | HTML5, CSS3, JavaScript vanilla (Fetch API) |
| UI | Bootstrap 5, Bootstrap Icons, CSS próprio (`static/css/myller.css`, `painel.css`) |
| Banco | SQLite (dev) / PostgreSQL (produção) |
| E-mails | Console (dev) / SMTP (produção) |
| Servidor | Gunicorn + WhiteNoise (produção) |

---

## 3. Instalação e execução

```bash
# 1) Ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 2) Dependências
pip install -r requirements.txt

# 3) Configuração
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/macOS
# Edite .env e defina DJANGO_SECRET_KEY

# 4) Banco de dados
python manage.py migrate

# 5) Dados de demonstração (opcional, recomendado)
python manage.py seed_myller --admin
# Cria: configuração da loja, 12 categorias, 14 produtos com 93 variações,
# 988 itens em estoque, 2 cupons e 4 páginas institucionais.
# Com --admin também cria o usuário administrador inicial.

# 6) Servidor
python manage.py runserver
```

- Loja: <http://localhost:8000/>
- Painel: <http://localhost:8000/painel/>
- Admin clássico Django: <http://localhost:8000/django-admin/>

**Conta de demonstração criada pelo seed:** `admin` / `admin123`
(altere a senha imediatamente em produção).

### Comandos úteis

```bash
python manage.py check            # verificações do projeto
python manage.py check --deploy   # verificações de produção
python manage.py test             # roda toda a suíte de testes
python manage.py seed_myller      # popular dados (idempotente)
python manage.py makemigrations   # gerar migrations
python manage.py migrate
python manage.py collectstatic    # produção
```

---

## 4. Estrutura do projeto

```
myller/
├── core/            # configuração da loja, páginas institucionais, newsletter, ViaCEP
├── usuarios/        # login, cadastro, recuperação de senha, perfil
├── clientes/        # perfis, endereços
├── categorias/      # árvore de categorias
├── produtos/        # produtos, variações, imagens, avaliações, busca
├── estoque/         # movimentações de estoque (entrada/saída/ajuste)
├── carrinho/        # carrinho em sessão, cupom, frete (AJAX)
├── favoritos/       # lista de favoritos
├── pedidos/         # pedidos, itens, status, frete, serviços de checkout
├── pagamentos/      # camada abstrata de pagamento + webhooks
├── dashboard/       # painel administrativo (views, forms, decorators, templates)
├── myller/          # settings, urls, wsgi/asgi, utilitários de teste
├── templates/       # templates da loja e do painel
├── static/          # css, js, imagens (SVG)
├── media/           # uploads de imagens dos produtos
├── db.sqlite3       # banco de desenvolvimento (não versionado)
├── .env.example     # modelo de variáveis de ambiente
├── requirements.txt
└── requirements-production.txt
```

---

## 5. Mapa de rotas

### Loja
| Método/URL | Descrição |
| --- | --- |
| `/` | Home |
| `/produtos/` | Catálogo com filtros |
| `/categoria/<slug>/` | Categoria |
| `/produto/<slug>/` | Detalhe do produto |
| `/produto/<slug>/avaliar/` | Enviar avaliação |
| `/busca/?q=` | Resultado da busca |
| `/api/busca/` | Busca em tempo real (JSON) |
| `/pagina/<slug>/` | Página institucional |
| `/newsletter/` | Assinatura da newsletter |
| `/api/cep/<cep>/` | Autocomplete de endereço (ViaCEP) |

### Carrinho e checkout
| Método/URL | Descrição |
| --- | --- |
| `/carrinho/` | Página do carrinho |
| `/carrinho/adicionar/` | Adicionar item (AJAX) |
| `/carrinho/atualizar/` | Atualizar quantidade (AJAX) |
| `/carrinho/remover/` | Remover item (AJAX) |
| `/carrinho/limpar/` | Esvaziar carrinho |
| `/carrinho/cupom/` | Aplicar/remover cupom |
| `/api/frete/` | Calcular frete (AJAX) |
| `/checkout/` | Finalizar pedido |
| `/pedido/<numero>/` | Confirmação / detalhe do pedido |
| `/pedido/<numero>/status/` | Status do pedido (polling JSON) |
| `/pedido/<numero>/cancelar/` | Cancelar pedido (cliente) |

### Usuários e favoritos
| Método/URL | Descrição |
| --- | --- |
| `/entrar/`, `/sair/`, `/cadastro/` | Login, logout, cadastro |
| `/senha/redefinir/...` | Recuperação de senha |
| `/conta/` | Perfil, dados, endereços, meus pedidos, senha |
| `/favoritos/` | Lista de favoritos |
| `/api/favoritos/alternar/` | Adicionar/remover favorito (AJAX) |

### Painel (`/painel/...`) — exige staff
Dashboard, produtos (CRUD + variações + imagens), pedidos (lista, detalhe, status),
clientes, categorias, cupons, estoque, newsletter e configurações.

### Webhooks
| URL | Descrição |
| --- | --- |
| `/webhooks/mercadopago/` | Notificações do Mercado Pago |
| `/webhooks/stripe/` | Eventos do Stripe |

---

## 6. Fluxo de pagamento (sem simulação)

O pagamento é uma **camada abstrata** selecionada pela variável `PAYMENT_GATEWAY`:

```
PAYMENT_GATEWAY = none | mercadopago | stripe
```

1. O cliente finaliza o checkout → o pedido é criado com status
   **`Aguardando pagamento`** e o estoque é baixado atomicamente.
2. `pagamentos.gateways` cria uma cobrança real no provedor e devolve a **URL de checkout**
   do gateway; o cliente é redirecionado para o checkout oficial (Mercado Pago/Stripe).
3. O provedor notifica `/webhooks/mercadopago/` ou `/webhooks/stripe/`.
4. O webhook **valida a assinatura** (`x-signature` / `Stripe-Signature`) e, apenas após
   confirmação autêntica, chama `alterar_status_pedido` → `Pagamento aprovado`.
5. O cliente volta ao site e o status é atualizado por polling (`/pedido/<numero>/status/`).

**Garantias:**
- Nenhum botão, view ou teste altera o status para aprovado sem confirmação do gateway.
- Sem credenciais (`PAYMENT_GATEWAY=none`), o pedido permanece eternamente em
  `Aguardando pagamento` — é o comportamento esperado, não um atalho.
- Webhook sem assinatura válida retorna `400` e não altera nada.
- Cancelamento devolve o estoque automaticamente.

---

## 7. Estoque

- Cada variação possui saldo (`estoque`); `estoque_total` do produto é a soma.
- Movimentações ficam registradas em `estoque.Movimentacao` (origem, quantidade, motivo,
  usuário), auditáveis no painel (`/painel/estoque/`).
- Baixa atômica com `select_for_update()` na criação do pedido; devolução no cancelamento.
- Painel sinaliza produtos com estoque baixo/zero (KPI e filtro).

---

## 8. Frete e endereço

- `FRETE_BACKEND`:
  - **`tabela`** (padrão): cálculo interno por peso e faixa de CEP — sempre disponível,
    rotulado como *estimativa*.
  - **`melhorenvio`**: cotação real via API da Melhor Envio (exige `MELHOR_ENVIO_TOKEN`).
  - **`correios`**: contrato Correios (exige `CORREIOS_CONTRATO` e `CORREIOS_SENHA`).
- Endereço: consulta pública ao **ViaCEP** (sem credenciais) em `/api/cep/<cep>/`.

---

## 9. Segurança

- `CsrfViewMiddleware` ativo em todos os formulários (inclusive AJAX via `X-CSRFToken`).
- Rotas do painel protegidas pelo decorador `painel_requerido` (staff/superuser);
  usuário não autenticado é redirecionado para o login preservando a rota original (`next`).
- Validação de formulários em servidor (formulários e formsets) — nada é confiado ao cliente.
- Segredos lidos exclusivamente de variáveis de ambiente (`.env`, não versionado).
- Validação de upload de imagens: tipos permitidos e limite de 8 MB por arquivo.
- Webhooks com validação de assinatura e comparação em tempo constante (`hmac.compare_digest`).
- Com `DEBUG=False`: cookies seguros, HSTS, SSL redirect, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff` e política de referrer.
- Senhas com os validadores padrão do Django (tamanho, comum, numérica, similaridade).

---

## 10. Testes

```bash
python manage.py test
```

**Resultado: 171 testes, todos passando (0 falhas).**

| App | Cobre |
| --- | --- |
| `core` | home, páginas institucionais, newsletter, ViaCEP, 404/500 |
| `usuarios` | cadastro, login (e-mail ou usuário), logout, recuperação de senha, perfil |
| `clientes` | perfil, endereços CRUD, endereço padrão |
| `produtos` | listagem, filtros, busca, detalhe, variações, avaliações |
| `carrinho` | adicionar/atualizar/remover/limpar, cupom, frete, limites de estoque, merge de sessão |
| `estoque` | movimentações, saldos, histórico |
| `pedidos` | criação, numeração, status, cancelamento + devolução de estoque, frete |
| `pagamentos` | gateway `none`, webhooks MP/Stripe, validação e rejeição de assinaturas |
| `favoritos` | alternar, listagem, persistência |
| `dashboard` | KPIs, CRUD de produtos (com formset), status de pedidos, estoque, proteção de rotas |

Os testes usam banco de dados descartável (`test_*.sqlite3`) e nunca tocam no `db.sqlite3`
de desenvolvimento.

---

## 11. Deploy

### 11.1 Railway (plano Free) — passo a passo

1. **Repositório**: código no GitHub
   (`https://github.com/aureliosousaif-ops/myller-loja.git`, branch `main`).
2. **Serviço web**: no painel da Railway, crie um projeto → *New Service* →
   *Deploy from GitHub repo* → aponte para `myller-loja`.
   O build usa o `requirements.txt` automaticamente (Nixpacks).
3. **PostgreSQL**: no mesmo projeto → *New Service* → *PostgreSQL*.
   A Railway injeta `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
   `POSTGRES_HOST` e `POSTGRES_PORT` no serviço web — o Django troca o
   SQLite pelo PostgreSQL automaticamente quando `POSTGRES_DB` existe.
4. **Variáveis de ambiente** (aba *Variables* do serviço web):

   | Variável | Obrigatória | Valor |
   | --- | --- | --- |
   | `DJANGO_SECRET_KEY` | **sim** | gere com<br>`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
   | `DJANGO_DEBUG` | não | `False` (padrão já é `False` na Railway) |
   | `DJANGO_ALLOWED_HOSTS` | não | o domínio `*.up.railway.app` é detectado automaticamente; use para domínio próprio |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | não | idem, com `https://` (ex.: `https://www.seudominio.com.br`) |
   | `SITE_URL` | recomendado | `https://SEUAPP.up.railway.app` |
   | `DJANGO_SECURE_SSL_REDIRECT` | não | `True` (padrão em produção) |
   | `SERVE_MEDIA` | não | `True` (padrão) — imagens servidas pelo Django |

   > O build **falha de propósito** se `DJANGO_SECRET_KEY` não estiver
   > definida — não existe chave de fábrica em produção.
5. **Inicialização**: o `Procfile` do projeto roda, a cada deploy:
   `migrate` → `seed_myller` → `gerar_imagens_demo` → `collectstatic` →
   `gunicorn myller.wsgi:application`.
6. **Conta do proprietário**: o seed **não** cria usuário administrativo
   (por segurança). Crie o seu uma única vez pela Railway:
   ```bash
   railway run python manage.py createsuperuser
   ```
   ou de forma não interativa:
   ```bash
   $env:DJANGO_SUPERUSER_PASSWORD="senha-forte-unica"
   railway run python manage.py createsuperuser --username SEUUSER --email SEU@EMAIL --noinput
   ```
7. **Deploy**: a Railway faz o deploy automático a cada push na `main`.
   O site fica em `https://SEUAPP.up.railway.app`.

**Limites do plano Free (esperado, não é 24/7):** crédito de US$ 1/mês,
serviços hibernam quando ociosos (acordam em ~30-60s na primeira requisição),
disco efêmero — uploads feitos **após** o deploy são perdidos no próximo
deploy (mídia demo versionada no Git + regenerada por
`gerar_imagens_demo`; pendência real: migrar uploads para S3-compatible).

### 11.2 Deploy genérico (qualquer servidor)

1. **Dependências**: `pip install -r requirements.txt`
   (já inclui gunicorn, WhiteNoise, psycopg e Pillow).
2. **`.env`**: `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` forte,
   `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` com o domínio (`https://...`).
3. **Banco**: preencha `POSTGRES_DB/USER/PASSWORD/HOST/PORT` para usar PostgreSQL.
4. **Migrar e coletar estáticos**:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```
5. **Servidor**: `gunicorn myller.wsgi:application`
   (WhiteNoise serve os estáticos comprimidos automaticamente).
6. **Verificações**: `python manage.py check --deploy`
7. **Webhooks**: aponte o painel do gateway para
   `https://SEUDOMINIO/webhooks/mercadopago/` ou `https://SEUDOMINIO/webhooks/stripe/`
   e configure o segredo correspondente no `.env`.
8. **Backup**: rotina de `pg_dump` para PostgreSQL e cópia de `media/`.

---

## 12. Integrações que exigem credenciais

| Integração | Variáveis no `.env` | Status |
| --- | --- | --- |
| Mercado Pago | `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_PUBLIC_KEY`, `MERCADOPAGO_WEBHOOK_SECRET` | Código pronto; aguardando credenciais |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` | Código pronto; aguardando credenciais |
| Melhor Envio | `MELHOR_ENVIO_TOKEN` | Código pronto; aguardando token |
| Correios | `CORREIOS_CONTRATO`, `CORREIOS_SENHA` | Código pronto; aguardando contrato |
| SMTP (e-mail) | `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Padrão é console; aguardando credenciais SMTP reais |
| Imagens (logo, banner, fotos) | — | Geradas por `manage.py gerar_imagens_demo` (Pillow); substitua pelas fotos reais no painel |

> Enquanto `PAYMENT_GATEWAY=none`, nenhum pagamento é aprovado — por decisão de projeto.

---

## 13. Imagens e identidade visual

- Paleta obrigatória aplicada em `static/css/myller.css`:
  **Azul `#275B85`**, **Azul claro `#95C2DF`**, **Branco `#FFFFFF`**, **Bege `#C0B7A6`**.
- Logo, favicon e placeholders de produto são **SVGs provisórios**; basta substituir os
  arquivos em `static/` e enviar as fotos reais para `media/` (o painel aceita upload direto).
- Design responsivo (mobile-first), animações suaves, Bootstrap Icons para a interface.

---

### Licença
Projeto privado — MYLLER.
