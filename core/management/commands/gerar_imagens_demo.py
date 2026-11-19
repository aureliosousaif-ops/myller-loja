"""
Gera as imagens demonstrativas da loja MYLLER (logo, peças, categorias e banner).

Tudo é desenhado localmente com Pillow — sem dependência de imagens externas.

Uso:
    python manage.py gerar_imagens_demo            # cria apenas o que falta
    python manage.py gerar_imagens_demo --forcar    # recria todos os arquivos

Arquivos gerados:
    static/img/logo-myller.png          logo oficial recortada (fundo transparente)
    static/img/logo-myller-clara.png    logo para fundos escuros
    static/img/favicon.png              favicon quadrado
    media/produtos/<slug>-a.jpg         foto principal
    media/produtos/<slug>-b.jpg         foto secundária (hover)
    media/categorias/<slug>.jpg         imagem da categoria
    media/loja/banner/hero-myller.jpg   banner editorial da home
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from django.core.management.base import BaseCommand

BASE = Path(__file__).resolve().parent.parent.parent.parent  # raiz do projeto

# --------------------------------------------------------------------- paleta
AZUL = "#275B85"
AZUL_ESCURO = "#1C4463"
AZUL_CLARO = "#95C2DF"
AZUL_GELO = "#EAF3F9"
BEGE = "#C0B7A6"
BEGE_CLARO = "#F4F1EC"
AREIA = "#D8CFC0"
OFFWHITE = "#F1ECE4"
BRANCO = "#FAF9F7"
CINZA = "#9BA4AC"
CARVAO = "#33383D"
TERRACOTA = "#C39A85"
ROSA = "#D8BEBB"

FUNDOS = [
    ("#F6F2EC", "#E9E2D8"),
    ("#FFFFFF", "#F0EDE7"),
    ("#EAF3F9", "#D5E6F2"),
    ("#F1ECE4", "#E3D9CB"),
    ("#FFFFFF", "#E9F2F9"),
    ("#F4F1EC", "#DCE8F1"),
]


def rgb(hexcor: str) -> tuple[int, int, int]:
    h = hexcor.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def escurecer(cor, fator=0.78):
    return tuple(int(c * fator) for c in cor)


def clarear(cor, fator=0.18):
    return tuple(int(c + (255 - c) * fator) for c in cor)


def rgba(cor, alfa=255):
    return (cor[0], cor[1], cor[2], alfa)


# --------------------------------------------------------------------- utilitários
def gradiente(larg: int, alt: int, cor1, cor2, diagonal: bool = False) -> Image.Image:
    """Gradiente suave — calculado em miniatura e ampliado (rápido e sem serrilhado)."""
    c1 = rgb(cor1) if isinstance(cor1, str) else cor1
    c2 = rgb(cor2) if isinstance(cor2, str) else cor2
    mini = 64
    img = Image.new("RGB", (mini, mini))
    px = img.load()
    for y in range(mini):
        for x in range(mini):
            t = (x / mini + y / mini) / 2 if diagonal else y / mini
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return img.resize((larg, alt), Image.BICUBIC)


def bezier(p0, p1, p2, n=36):
    """Curva quadrática de Bézier (pontos normalizados)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


# --------------------------------------------------------------------- moldes
class Molde:
    """Desenha silhuetas em uma caixa normalizada.

    * silhueta -> desenhada na máscara (valor 255)
    * detalhes -> desenhados em uma camada RGBA sobre a peça
    """

    def __init__(self, caixa):
        self.x0, self.y0, self.x1, self.y1 = caixa

    def p(self, u, v):
        cx = (self.x0 + self.x1) / 2
        w = self.x1 - self.x0
        h = self.y1 - self.y0
        return (cx + u * w, self.y0 + v * h)

    def silhueta(self, alvo, pts, **kwargs):
        alvo.polygon([self.p(u, v) for u, v in pts], fill=255, **kwargs)

    def detalhe(self, alvo, pts, cor, alfa=255, **kwargs):
        alvo.polygon([self.p(u, v) for u, v in pts], fill=rgba(cor, alfa), **kwargs)

    def linha_silhueta(self, alvo, pts, largura=4):
        alvo.line([self.p(u, v) for u, v in pts], fill=255, width=largura, joint="curve")

    def linha_detalhe(self, alvo, pts, cor, largura=4, alfa=255):
        alvo.line([self.p(u, v) for u, v in pts], fill=rgba(cor, alfa),
                  width=largura, joint="curve")

    # ------------------------------------------------------------ superiores
    def corpo_superior(self, dm, dd, cor, v_barra=0.62, v_cintura=0.52,
                       larg_ombro=0.44, larg_cintura=0.36, larg_barra=0.46,
                       gola="redonda", manga="longa"):
        lo, lc, lb = larg_ombro, larg_cintura, larg_barra

        def perfil(v):
            """Largura lateral do corpo em um determinado altura normalizada."""
            if v <= 0.10:
                return lo / 2
            if v <= v_cintura:
                return lo / 2 + (lc / 2 - lo / 2) * (v - 0.10) / max(v_cintura - 0.10, 0.01)
            if v <= v_barra:
                return lc / 2 + (lb / 2 - lc / 2) * (v - v_cintura) / max(v_barra - v_cintura, 0.01)
            return lb / 2

        # ---------------------------------------------------------- gola
        if gola == "redonda":
            meio = bezier((-lo / 2 + 0.09, 0.10), (0, 0.19), (lo / 2 - 0.09, 0.10), 24)
        elif gola == "v":
            meio = bezier((-lo / 2 + 0.08, 0.10), (0, 0.28), (lo / 2 - 0.08, 0.10), 24)
        else:  # quadrada
            meio = [(-lo / 2 + 0.08, 0.10), (-0.11, 0.13), (-0.11, 0.25),
                    (0.11, 0.25), (0.11, 0.13), (lo / 2 - 0.08, 0.10)]

        corpo = [
            (-lo / 2, 0.10),
            (-lc / 2, v_cintura),
            (-lb / 2, v_barra),
            (lb / 2, v_barra),
            (lc / 2, v_cintura),
            (lo / 2, 0.10),
        ] + meio[::-1]
        self.silhueta(dm, corpo)

        # ---------------------------------------------------------- mangas
        v_punho = 0.80 if manga == "longa" else 0.50
        if manga in ("longa", "curta"):
            v_punho = min(v_punho, max(v_cintura + 0.20, 0.46))
            espessura = 0.15 if manga == "longa" else 0.13
            alturas = [0.09, 0.22, 0.40, 0.58, v_punho]
            for s in (-1, 1):
                externo = [
                    (s * (perfil(v) + espessura * (0.45 + 0.55 * (v / max(v_punho, 0.01)))), v)
                    for v in alturas
                ]
                interno = [(s * perfil(v), v) for v in reversed(alturas)]
                self.silhueta(dm, externo + interno)

        # ---------------------------------------------------------- detalhes
        sombra = escurecer(cor, 0.86)

        # barra inferior
        self.linha_detalhe(dd, [(-lb / 2, v_barra), (lb / 2, v_barra)], sombra, 6, 190)
        # pregas do corpo
        for u in (-0.13, 0.0, 0.13):
            self.linha_detalhe(dd, [(u, v_cintura + 0.04), (u * 1.15, v_barra - 0.05)],
                               escurecer(cor, 0.92), 4, 150)
        # costura de manga (separa braço do corpo)
        if manga in ("longa", "curta"):
            for s in (-1, 1):
                self.linha_detalhe(dd, [
                    (s * perfil(0.11), 0.11),
                    (s * perfil((0.11 + v_punho) / 2), (0.11 + v_punho) / 2),
                    (s * perfil(v_punho), v_punho),
                ], escurecer(cor, 0.84), 5, 190)
                # punho
                self.linha_detalhe(dd, [
                    (s * (perfil(v_punho) + 0.02), v_punho - 0.03),
                    (s * (perfil(v_punho) + espessura * 0.9), v_punho - 0.03),
                ], escurecer(cor, 0.80), 7, 220)
        # cinto do vestido
        if v_barra > 0.9:
            self.detalhe(dd, [(-0.175, 0.435), (0.175, 0.435), (0.175, 0.495), (-0.175, 0.495)],
                         escurecer(cor, 0.74), 235)
            self.detalhe(dd, [(-0.038, 0.425), (0.038, 0.425), (0.038, 0.505), (-0.038, 0.505)],
                         escurecer(cor, 0.60), 255)
        # gola em V
        if gola == "v":
            self.linha_detalhe(dd, [(-lo / 2 + 0.08, 0.11), (0, 0.27), (lo / 2 - 0.08, 0.11)],
                               escurecer(cor, 0.88), 5, 210)

        return clarear(cor, 0.16)

    def colarinho(self, dm, dd, cor):
        claro = clarear(cor, 0.18)
        for s in (-1, 1):
            self.detalhe(dd, [(s * 0.05, 0.10), (s * 0.21, 0.14),
                              (s * 0.14, 0.28), (s * 0.03, 0.18)], claro, 245)
        self.linha_detalhe(dd, [(0, 0.18), (0, 0.72)], escurecer(cor, 0.86), 4, 220)
        for v in (0.26, 0.35, 0.44, 0.53, 0.62):
            self.detalhe(dd, [(-0.014, v), (0.014, v), (0.014, v + 0.024), (-0.014, v + 0.024)],
                         escurecer(cor, 0.70), 255)

    def lapela(self, dm, dd, cor):
        claro = clarear(cor, 0.20)
        for s in (-1, 1):
            self.detalhe(dd, [(s * 0.05, 0.11), (s * 0.19, 0.15),
                              (s * 0.11, 0.44), (s * 0.02, 0.34)], claro, 245)
        self.linha_detalhe(dd, [(0, 0.20), (0, 0.74)], escurecer(cor, 0.80), 4, 220)
        for v in (0.34, 0.46, 0.58):
            self.detalhe(dd, [(-0.013, v), (0.013, v), (0.013, v + 0.022), (-0.013, v + 0.022)],
                         escurecer(cor, 0.72), 255)

    # ------------------------------------------------------------ inferiores
    def calca(self, dm, dd, cor, v_cintura=0.12, v_barra=0.97,
              larg_cintura=0.62, larg_barra=0.72):
        lc, lb = larg_cintura, larg_barra
        self.silhueta(dm, [
            (-lc / 2, v_cintura),
            (-lb / 2, v_barra),
            (-0.05, v_barra),
            (0.0, (v_cintura + v_barra) / 2 + 0.03),
            (0.05, v_barra),
            (lb / 2, v_barra),
            (lc / 2, v_cintura),
        ])
        # cintura
        self.silhueta(dm, [(-lc / 2, v_cintura - 0.05), (lc / 2, v_cintura - 0.05),
                           (lc / 2, v_cintura), (-lc / 2, v_cintura)])
        self.linha_detalhe(dd, [(-lc / 2, v_cintura), (lc / 2, v_cintura)],
                           escurecer(cor, 0.80), 5, 220)
        for s in (-1, 1):
            self.linha_detalhe(dd, [(s * 0.13, v_cintura + 0.07), (s * 0.16, v_barra - 0.07)],
                               escurecer(cor, 0.90), 4, 160)
        # bolso discreto
        self.linha_detalhe(dd, [(-lc / 2 + 0.03, v_cintura + 0.08),
                                (-lc / 2 + 0.14, v_cintura + 0.14)],
                           escurecer(cor, 0.88), 4, 170)

    def saia(self, dm, dd, cor, v_cintura=0.12, v_barra=0.95,
             larg_cintura=0.52, larg_barra=0.86):
        lc, lb = larg_cintura, larg_barra
        onda = []
        passos = 16
        for i in range(passos + 1):
            t = i / passos
            onda.append((-lb / 2 + t * lb, v_barra + 0.02 * math.sin(t * math.pi * 5)))
        self.silhueta(dm, [(-lc / 2, v_cintura)] + onda + [(lc / 2, v_cintura)])
        self.silhueta(dm, [(-lc / 2, v_cintura - 0.05), (lc / 2, v_cintura - 0.05),
                           (lc / 2, v_cintura), (-lc / 2, v_cintura)])
        self.linha_detalhe(dd, [(-lc / 2, v_cintura), (lc / 2, v_cintura)],
                           escurecer(cor, 0.80), 5, 220)
        for u in (-0.28, -0.14, 0.0, 0.14, 0.28):
            self.linha_detalhe(dd, [(u * 0.5, v_cintura + 0.07), (u * 1.4, v_barra - 0.05)],
                               escurecer(cor, 0.90), 4, 155)

    def bolsa(self, dm, dd, cor):
        x0, y0 = self.p(-0.34, 0.44)
        x1, y1 = self.p(0.34, 0.94)
        raio = int((x1 - x0) * 0.11)
        # alça (desenhada na silhueta para o recorte)
        a, b = self.p(-0.21, 0.46), self.p(0.21, 0.46)
        topo = self.p(0.0, 0.17)
        dm.line(bezier(a, topo, b, 40), fill=255,
                width=max(4, int((x1 - x0) * 0.055)), joint="curve")
        # corpo
        dm.rounded_rectangle([x0, y0, x1, y1], radius=raio, fill=255)
        # detalhes
        dd.rounded_rectangle([x0, y0, x1, y0 + (y1 - y0) * 0.36],
                             radius=raio, fill=rgba(clarear(cor, 0.16), 255))
        dd.line(bezier(a, topo, b, 40), fill=rgba(escurecer(cor, 0.86), 255),
                width=max(4, int((x1 - x0) * 0.055)), joint="curve")
        cx, cy = self.p(0.0, 0.62)
        r = (x1 - x0) * 0.05
        dd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgba(escurecer(cor, 0.72), 255))


# --------------------------------------------------------------------- peças
def peca_vestido(dm, dd, caixa, cor):
    m = Molde(caixa)
    m.corpo_superior(dm, dd, cor, v_barra=0.97, v_cintura=0.46, larg_ombro=0.42,
                     larg_cintura=0.30, larg_barra=0.66, manga="longa")


def peca_blusa(dm, dd, caixa, cor):
    m = Molde(caixa)
    m.corpo_superior(dm, dd, cor, v_barra=0.66, v_cintura=0.50, larg_ombro=0.44,
                     larg_cintura=0.38, larg_barra=0.48, manga="longa")


def peca_cropped(dm, dd, caixa, cor):
    m = Molde(caixa)
    m.corpo_superior(dm, dd, cor, v_barra=0.44, v_cintura=0.36, larg_ombro=0.46,
                     larg_cintura=0.40, larg_barra=0.48, manga="curta")


def peca_camisa(dm, dd, caixa, cor):
    m = Molde(caixa)
    m.corpo_superior(dm, dd, cor, v_barra=0.74, v_cintura=0.54, larg_ombro=0.46,
                     larg_cintura=0.40, larg_barra=0.52, gola="quadrada", manga="longa")
    m.colarinho(dm, dd, cor)


def peca_jaqueta(dm, dd, caixa, cor):
    m = Molde(caixa)
    m.corpo_superior(dm, dd, cor, v_barra=0.76, v_cintura=0.56, larg_ombro=0.50,
                     larg_cintura=0.44, larg_barra=0.56, gola="quadrada", manga="longa")
    m.lapela(dm, dd, cor)


def peca_calca(dm, dd, caixa, cor):
    Molde(caixa).calca(dm, dd, cor, larg_cintura=0.56, larg_barra=0.74)


def peca_wide_leg(dm, dd, caixa, cor):
    Molde(caixa).calca(dm, dd, cor, larg_cintura=0.50, larg_barra=0.96)


def peca_saia(dm, dd, caixa, cor):
    Molde(caixa).saia(dm, dd, cor, larg_cintura=0.46, larg_barra=0.86)


def peca_short(dm, dd, caixa, cor):
    Molde(caixa).calca(dm, dd, cor, v_cintura=0.18, v_barra=0.68,
                       larg_cintura=0.58, larg_barra=0.80)


def peca_conjunto(dm, dd, caixa, cor):
    m = Molde(caixa)
    m.corpo_superior(dm, dd, cor, v_barra=0.42, v_cintura=0.34, larg_ombro=0.44,
                     larg_cintura=0.38, larg_barra=0.46, manga="curta")
    m.calca(dm, dd, cor, v_cintura=0.52, v_barra=0.98, larg_cintura=0.54, larg_barra=0.82)


def peca_bolsa(dm, dd, caixa, cor):
    Molde(caixa).bolsa(dm, dd, cor)


MOLDES = {
    "vestido": peca_vestido,
    "blusa": peca_blusa,
    "cropped": peca_cropped,
    "camisa": peca_camisa,
    "jaqueta": peca_jaqueta,
    "calca": peca_calca,
    "wide_leg": peca_wide_leg,
    "saia": peca_saia,
    "short": peca_short,
    "conjunto": peca_conjunto,
    "bolsa": peca_bolsa,
}


# --------------------------------------------------------------------- composição
def montar_peca(tipo: str, cor_hex: str, fundo, variante: int = 0,
                larg: int = 900, alt: int = 1125) -> Image.Image:
    """Fundo + luz + sombra + peça + detalhes + vinheta."""
    cor = rgb(cor_hex)
    desenho = MOLDES[tipo]

    bg = gradiente(larg, alt, *fundo, diagonal=(variante == 1))

    # luz de estúdio atrás da peça
    luz = Image.new("L", (larg, alt), 0)
    dl = ImageDraw.Draw(luz)
    raio = int(min(larg, alt) * 0.50)
    cx, cy = larg // 2, int(alt * 0.45)
    dl.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=95)
    luz = luz.filter(ImageFilter.GaussianBlur(90))
    bg.paste(Image.new("RGB", (larg, alt), (255, 255, 255)), (0, 0), luz)

    esc = 3
    W, H = larg * esc, alt * esc
    mascara = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(mascara)
    detalhes = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(detalhes)

    caixa = (int(W * 0.15), int(H * 0.11), int(W * 0.85), int(H * 0.93))
    desenho(dm, dd, caixa, cor)

    mask_s = mascara.resize((larg, alt), Image.LANCZOS)
    det_s = detalhes.resize((larg, alt), Image.LANCZOS)

    base = bg.copy()

    # sombra de contato
    sombra = Image.new("L", (larg, alt), 0)
    sombra.paste(mask_s, (int(larg * 0.012), int(alt * 0.018)))
    sombra = sombra.filter(ImageFilter.GaussianBlur(int(min(larg, alt) * 0.030)))
    sombra = sombra.point(lambda v: int(v * 0.34))
    base.paste(Image.new("RGB", (larg, alt), (16, 41, 61)), (0, 0), sombra)

    # corpo da peça com volume (gradiente claro -> escuro)
    topo = clarear(cor, 0.16)
    fundo_cor = escurecer(cor, 0.90)
    camada = gradiente(larg, alt, topo, fundo_cor)
    base.paste(camada, (0, 0), mask_s)

    # brilho suave no ombro
    brilho = Image.new("L", (larg, alt), 0)
    db = ImageDraw.Draw(brilho)
    br = int(min(larg, alt) * 0.34)
    db.ellipse([int(larg * 0.30) - br, int(alt * 0.18) - br,
                int(larg * 0.30) + br, int(alt * 0.18) + br], fill=70)
    brilho = brilho.filter(ImageFilter.GaussianBlur(70))
    base.paste(Image.new("RGB", (larg, alt), (255, 255, 255)), (0, 0),
               Image.composite(brilho, Image.new("L", (larg, alt), 0), mask_s))

    # detalhes (costuras, golas, botões)
    base.paste(det_s.convert("RGB"), (0, 0), det_s)

    # vinheta leve nas bordas
    vin = Image.new("L", (larg, alt), 255)
    ImageDraw.Draw(vin).ellipse([-int(larg * 0.30), -int(alt * 0.30),
                                 int(larg * 1.30), int(alt * 1.30)], fill=0)
    vin = Image.new("L", (larg, alt), 0)
    ImageDraw.Draw(vin).rectangle([0, 0, larg, alt], fill=255)
    ImageDraw.Draw(vin).ellipse([-int(larg * 0.28), -int(alt * 0.24),
                                 int(larg * 1.28), int(alt * 1.24)], fill=0)
    vin = vin.filter(ImageFilter.GaussianBlur(140))
    base.paste(Image.new("RGB", (larg, alt), (244, 241, 236)), (0, 0),
               vin.point(lambda v: int(v * 0.18)))

    return base


def peca_detalhe(peca: Image.Image, cor_hex: str) -> Image.Image:
    """Variante B: zoom na peça + amostra de tecido dobrada no canto."""
    larg, alt = peca.size
    zoom = peca.resize((int(larg * 1.28), int(alt * 1.28)), Image.LANCZOS)
    x = (zoom.size[0] - larg) // 2
    y = int((zoom.size[1] - alt) * 0.42)
    corte = zoom.crop((x, y, x + larg, y + alt))

    # amostra de tecido dobrada
    cor = rgb(cor_hex)
    sw = int(larg * 0.26)
    mx, my = larg - sw - int(larg * 0.09), alt - sw - int(alt * 0.07)
    sombra = Image.new("L", corte.size, 0)
    ImageDraw.Draw(sombra).rounded_rectangle(
        [mx + 8, my + 14, mx + sw + 8, my + sw + 14], radius=18, fill=90)
    sombra = sombra.filter(ImageFilter.GaussianBlur(14))
    corte.paste(Image.new("RGB", corte.size, (16, 41, 61)), (0, 0), sombra)

    camada = gradiente(sw, sw, clarear(cor, 0.20), escurecer(cor, 0.88), diagonal=True)
    masc = Image.new("L", (sw, sw), 0)
    ImageDraw.Draw(masc).rounded_rectangle([0, 0, sw, sw], radius=18, fill=255)
    corte.paste(camada, (mx, my), masc)
    # dobra
    dd = ImageDraw.Draw(corte)
    dd.line([(mx + 10, my + int(sw * 0.55)), (mx + sw - 10, my + int(sw * 0.48))],
            fill=rgba(escurecer(cor, 0.78), 160), width=4, joint="curve")
    dd.line([(mx + 10, my + int(sw * 0.72)), (mx + sw - 10, my + int(sw * 0.66))],
            fill=rgba(clarear(cor, 0.25), 140), width=3, joint="curve")
    return corte


# --------------------------------------------------------------------- banner
def gerar_banner(larg: int = 1920, alt: int = 1080) -> Image.Image:
    """Banner editorial: fitas de tecido fluidas em azul e bege."""
    base = gradiente(larg, alt, "#14344D", "#275B85", diagonal=True)

    fitas = [
        (AZUL_CLARO, 0.30, 0.0),
        ("#B9D6EC", 0.22, 0.35),
        (BEGE, 0.26, 0.7),
        (OFFWHITE, 0.14, 1.1),
        (AZUL_ESCURO, 0.34, 1.6),
    ]
    esc = 2
    W, H = larg * esc, alt * esc
    camada = Image.new("L", (W, H), 0)
    dc = ImageDraw.Draw(camada)

    for i, (cor, esp, fase) in enumerate(fitas):
        y0 = int(H * (0.30 + 0.11 * i))
        pts_topo = []
        pts_base = []
        n = 80
        for k in range(n + 1):
            t = k / n
            x = t * W
            y = y0 + math.sin(t * math.pi * 1.6 + fase) * H * 0.13 - t * H * 0.10
            largura = H * esp * (0.5 + 0.5 * math.sin(t * math.pi))
            pts_topo.append((x, y))
            pts_base.append((x, y + largura))
        dc.polygon(pts_topo + pts_base[::-1], fill=int(150 + i * 18))

    camada = camada.resize((larg, alt), Image.LANCZOS)
    camada = camada.filter(ImageFilter.GaussianBlur(2))
    cor_camada = gradiente(larg, alt, AZUL_CLARO, BEGE, diagonal=True)
    base.paste(cor_camada, (0, 0), camada)

    # luz suave à esquerda para o texto respirar
    luz = Image.new("L", (larg, alt), 0)
    dl = ImageDraw.Draw(luz)
    dl.ellipse([-int(larg * 0.20), -int(alt * 0.30), int(larg * 0.62), int(alt * 1.30)], fill=140)
    luz = luz.filter(ImageFilter.GaussianBlur(160))
    base.paste(Image.new("RGB", (larg, alt), (12, 40, 62)), (0, 0),
               luz.point(lambda v: int(v * 0.75)))

    # grão sutil
    ruido = Image.effect_noise((larg, alt), 14).convert("L")
    base.paste(Image.new("RGB", (larg, alt), (255, 255, 255)), (0, 0),
               ruido.point(lambda v: int(max(0, v - 150) * 0.25)))
    return base


# --------------------------------------------------------------------- logo
def processar_logo():
    """Recorta as margens transparentes e cria as versões clara/escura/favicon."""
    origem = BASE / "img" / "logo_myller-removebg-preview.png"
    if not origem.exists():
        return []
    criados = []
    img = Image.open(origem).convert("RGBA")
    bbox = img.split()[3].getbbox()
    recorte = img.crop(bbox) if bbox else img

    # mantém a proporção e adiciona uma margem mínima
    margem = int(max(recorte.size) * 0.06)
    canvas = Image.new("RGBA", (recorte.width + margem * 2, recorte.height + margem * 2),
                       (0, 0, 0, 0))
    canvas.paste(recorte, (margem, margem))

    destino = BASE / "static" / "img" / "logo-myller.png"
    canvas.save(destino, "PNG", optimize=True)
    criados.append(destino)

    # versão clara (para rodapé e painel escuro)
    canais = canvas.split()
    claro = Image.new("RGBA", canvas.size, (255, 255, 255, 0))
    claro.putalpha(canais[3])
    destino_clara = BASE / "static" / "img" / "logo-myller-clara.png"
    claro.save(destino_clara, "PNG", optimize=True)
    criados.append(destino_clara)

    # favicon quadrado com folga
    lado = max(canvas.size)
    fav = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    fav.paste(canvas, ((lado - canvas.width) // 2, (lado - canvas.height) // 2))
    fav = fav.resize((192, 192), Image.LANCZOS)
    destino_fav = BASE / "static" / "img" / "favicon.png"
    fav.save(destino_fav, "PNG", optimize=True)
    criados.append(destino_fav)
    return criados


# --------------------------------------------------------------------- comando
class Command(BaseCommand):
    help = "Gera as imagens demonstrativas da MYLLER (logo, peças, categorias e banner)."

    def add_arguments(self, parser):
        parser.add_argument("--forcar", action="store_true",
                            help="Recria os arquivos mesmo que já existam.")

    def handle(self, *args, **options):
        self.forcar = options["forcar"]
        self.stdout.write(self.style.MIGRATE_HEADING("Gerando imagens MYLLER..."))

        for caminho in processar_logo():
            self.stdout.write(f"  + {caminho.relative_to(BASE)}")

        self._categorias()
        self._banner()
        self._produtos()

        self.stdout.write(self.style.SUCCESS("Concluído."))

    # -------------------------------------------------------------- helpers
    def _salvar(self, caminho: Path, img: Image.Image, formato="JPEG", **kwargs):
        if caminho.exists() and not self.forcar:
            return False
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if formato == "JPEG":
            img.convert("RGB").save(caminho, "JPEG", quality=88, optimize=True, **kwargs)
        else:
            img.save(caminho, formato, **kwargs)
        return True

    def _categorias(self):
        from categorias.models import Categoria

        mapa = {
            "vestidos": "vestido",
            "blusas": "blusa",
            "croppeds": "cropped",
            "calcas": "wide_leg",
            "saias": "saia",
            "shorts": "short",
            "conjuntos": "conjunto",
            "jaquetas": "jaqueta",
            "camisas": "camisa",
            "acessorios": "bolsa",
            "feminino": "vestido",
            "masculino": "camisa",
            "calcados": "bolsa",
            "novidades": "conjunto",
            "promocoes": "saia",
        }
        cores = [AZUL, BEGE, AZUL_CLARO, OFFWHITE, CARVAO, TERRACOTA]
        criadas = 0
        for categoria in Categoria.objects.all():
            chave = slug(categoria.nome)
            tipo = mapa.get(chave)
            if tipo is None:
                continue
            destino = BASE / "media" / "categorias" / f"{chave}.jpg"
            idx = indice(chave, len(FUNDOS))
            img = montar_peca(tipo, cores[indice(chave + "c", len(cores))],
                              FUNDOS[idx], larg=900, alt=900)
            if self._salvar(destino, img):
                criadas += 1
            if not categoria.imagem:
                categoria.imagem = f"categorias/{chave}.jpg"
                categoria.save(update_fields=["imagem"])
        if criadas:
            self.stdout.write(f"  + {criadas} imagens de categoria")

    def _banner(self):
        destino = BASE / "media" / "loja" / "banner" / "hero-myller.jpg"
        if self._salvar(destino, gerar_banner()):
            self.stdout.write("  + banner editorial da home")

        from core.models import ConfiguracaoLoja

        loja = ConfiguracaoLoja.carregar()
        if not loja.banner_imagem:
            loja.banner_imagem = "loja/banner/hero-myller.jpg"
            loja.save(update_fields=["banner_imagem"])

    def _produtos(self):
        from produtos.models import Produto

        # (slug ou nome) -> (tipo de peça, cor)
        molde_por_categoria = {
            "vestidos": ("vestido", [AZUL, BEGE, OFFWHITE, AZUL_CLARO, CARVAO, ROSA]),
            "blusas": ("blusa", [OFFWHITE, AZUL_CLARO, BEGE, BRANCO, CINZA]),
            "croppeds": ("cropped", [BEGE, AZUL, OFFWHITE, ROSA, CARVAO]),
            "calcas": ("wide_leg", [AZUL_ESCURO, BEGE, CARVAO, AZUL, OFFWHITE]),
            "saias": ("saia", [BEGE, AZUL, CARVAO, AREIA, OFFWHITE]),
            "shorts": ("short", [AZUL_ESCURO, AREIA, OFFWHITE, CARVAO]),
            "conjuntos": ("conjunto", [AZUL, BEGE, OFFWHITE, AZUL_CLARO, CARVAO]),
            "jaquetas": ("jaqueta", [BEGE, AZUL_ESCURO, CARVAO, OFFWHITE]),
            "camisas": ("camisa", [BRANCO, AZUL_CLARO, OFFWHITE, AREIA, AZUL]),
            "acessorios": ("bolsa", [BEGE, CARVAO, AZUL, TERRACOTA, OFFWHITE]),
        }
        fallback = ("blusa", [BEGE, AZUL, OFFWHITE])

        criadas = 0
        for produto in Produto.objects.all().order_by("pk"):
            chave = slug(produto.categoria.nome)
            tipo, cores = molde_por_categoria.get(chave, fallback)
            cor = cores[indice(produto.slug, len(cores))]
            fundo = FUNDOS[indice(produto.slug + "f", len(FUNDOS))]

            principal = BASE / "media" / "produtos" / f"{produto.slug}-a.jpg"
            secundaria = BASE / "media" / "produtos" / f"{produto.slug}-b.jpg"

            if self._salvar(principal, montar_peca(tipo, cor, fundo)):
                criadas += 1
            if self._salvar(secundaria, peca_detalhe(montar_peca(tipo, cor, fundo, variante=1), cor)):
                criadas += 1

            if not produto.imagens.exists():
                from produtos.models import ProdutoImagem

                ProdutoImagem.objects.create(
                    produto=produto, imagem=f"produtos/{produto.slug}-a.jpg",
                    alt=f"{produto.nome} — imagem principal (demonstrativa)", ordem=0,
                )
                ProdutoImagem.objects.create(
                    produto=produto, imagem=f"produtos/{produto.slug}-b.jpg",
                    alt=f"{produto.nome} — imagem secundária (demonstrativa)", ordem=1,
                )
        if criadas:
            self.stdout.write(f"  + {criadas} imagens de produto")


def indice(texto: str, n: int) -> int:
    """Índice determinístico (o hash do Python muda a cada execução)."""
    return sum(ord(c) for c in texto) % max(n, 1)


def slug(texto: str) -> str:
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return (
        texto.lower()
        .replace("ç", "c")
        .replace(" ", "-")
        .replace("/", "-")
        .strip("-")
    )
