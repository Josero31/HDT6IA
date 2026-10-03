"""Genera los tres diagramas SVG de arquitectura."""

from pathlib import Path

W, H = 980, 660
AQUI = Path(__file__).parent

CSS = """
<style>
  .bg    { fill:#f7f8fa; }
  .title { font:700 22px 'Helvetica Neue',Arial,sans-serif; fill:#11161d; }
  .sub   { font:400 13px 'Helvetica Neue',Arial,sans-serif; fill:#5c6672; }
  .nameU { font:700 15px 'Helvetica Neue',Arial,sans-serif; fill:#ffffff; }
  .name  { font:700 15px 'Helvetica Neue',Arial,sans-serif; fill:#11161d; }
  .role  { font:400 12px 'Helvetica Neue',Arial,sans-serif; fill:#5c6672; }
  .tool  { font:400 11.5px 'Menlo',monospace; fill:#3d4854; }
  .edge  { font:600 11px 'Helvetica Neue',Arial,sans-serif; fill:#7a5cff; }
  .note  { font:400 12px 'Helvetica Neue',Arial,sans-serif; fill:#5c6672; }
  .lvl   { font:700 11px 'Helvetica Neue',Arial,sans-serif; fill:#98a2b0; letter-spacing:1px; }
  .box   { fill:#ffffff; stroke:#d6dbe3; stroke-width:1.5; }
  .boxU  { fill:#11161d; stroke:#11161d; }
  .boxO  { fill:#efeaff; stroke:#7a5cff; stroke-width:2; }
  .boxM  { fill:#e8f2ff; stroke:#2f7fe0; stroke-width:1.8; }
  .boxS  { fill:#ffffff; stroke:#98a2b0; stroke-width:1.5; }
  .boxT  { fill:#f2f4f7; stroke:#e2e6ec; stroke-width:1; }
  .line  { stroke:#7a5cff; stroke-width:2; fill:none; }
  .line2 { stroke:#98a2b0; stroke-width:1.6; fill:none; stroke-dasharray:5 4; }
</style>
<defs>
  <marker id="a" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
    <path d="M0,0 L9,4.5 L0,9 z" fill="#7a5cff"/>
  </marker>
  <marker id="b" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
    <path d="M0,0 L9,4.5 L0,9 z" fill="#98a2b0"/>
  </marker>
  <marker id="c" markerWidth="9" markerHeight="9" refX="2" refY="4.5" orient="auto-start-reverse">
    <path d="M0,0 L9,4.5 L0,9 z" fill="#7a5cff"/>
  </marker>
</defs>
"""


def box(x, y, w, h, clase, nombre, rol="", lineas=(), rx=10):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" class="{clase}"/>']
    cx = x + w / 2
    ty = y + (24 if rol or lineas else h / 2 + 5)
    cls = "nameU" if clase == "boxU" else "name"
    out.append(f'<text x="{cx}" y="{ty}" text-anchor="middle" class="{cls}">{nombre}</text>')
    if rol:
        out.append(f'<text x="{cx}" y="{ty + 17}" text-anchor="middle" class="role">{rol}</text>')
    for i, ln in enumerate(lineas):
        out.append(f'<text x="{x + 12}" y="{y + h - 12 - (len(lineas) - 1 - i) * 15}" class="tool">{ln}</text>')
    return "\n".join(out)


def arrow(x1, y1, x2, y2, clase="line", marker="a", doble=False):
    extra = ' marker-start="url(#c)"' if doble else ""
    return (
        f'<path d="M{x1},{y1} L{x2},{y2}" class="{clase}" '
        f'marker-end="url(#{marker})"{extra}/>'
    )


def elbow(x1, y1, x2, y2, clase="line", marker="a", doble=False):
    ym = (y1 + y2) / 2
    extra = ' marker-start="url(#c)"' if doble else ""
    return (
        f'<path d="M{x1},{y1} V{ym} H{x2} V{y2}" class="{clase}" '
        f'marker-end="url(#{marker})"{extra}/>'
    )


def label(x, y, texto, clase="edge", anchor="middle"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="{clase}">{texto}</text>'


def envolver(cuerpo, titulo, subtitulo):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
{CSS}
<rect width="{W}" height="{H}" class="bg"/>
<text x="40" y="46" class="title">{titulo}</text>
<text x="40" y="68" class="sub">{subtitulo}</text>
{cuerpo}
</svg>
"""


ESP = [
    ("Especialista FAQs", "Base de conocimiento", ["consultar_faqs()"]),
    ("Especialista Clima", "Open-Meteo", ["consultar_clima()", "fecha_actual()"]),
    ("Oficial de Seguridad", "Reglas de salto", ["evaluar_condiciones()", "evaluar_fecha()"]),
    ("Especialista Agenda", "Citas", ["consultar_horarios()", "agendar_cita()", "listar_citas()"]),
]


def recortar(c1, c2, w, h):
    """Recorta el segmento entre dos centros de caja hasta el borde de cada caja."""
    def borde(c, otro):
        dx, dy = otro[0] - c[0], otro[1] - c[1]
        if dx == 0 and dy == 0:
            return c
        tx = (w / 2) / abs(dx) if dx else float("inf")
        ty = (h / 2) / abs(dy) if dy else float("inf")
        t = min(tx, ty)
        return (c[0] + dx * t, c[1] + dy * t)
    p1 = borde(c1, c2)
    p2 = borde(c2, c1)
    return p1, p2


# ---------------------------------------------------------------- CENTRALIZADA
def centralizada():
    p = []
    p.append(box(400, 96, 180, 42, "boxU", "Usuario"))
    p.append(arrow(490, 138, 490, 172, "line", "a", doble=True))
    p.append(box(300, 174, 380, 74, "boxO", "Orquestador central",
                 "Único punto de decisión y única voz hacia el usuario"))

    xs = [40, 280, 520, 760]
    for x, (n, r, tl) in zip(xs, ESP):
        cx = x + 90
        p.append(elbow(490, 248, cx, 344, "line", "a", doble=True))
        p.append(box(x, 346, 180, 46 + 18 * len(tl), "boxS", n, r, tl))

    p.append(label(660, 288, "as_tool()"))
    p.append(label(40, 596, "El orquestador invoca a cada especialista como si fuera una función: la salida vuelve al orquestador, nunca al usuario.", "note", "start"))
    p.append(label(40, 618, "Ventaja: control total del flujo y una sola respuesta coherente. Costo: todo el contexto pasa por un solo agente.", "note", "start"))
    return envolver("\n".join(p), "Arquitectura CENTRALIZADA",
                    "Parachute S.A. — un orquestador, cuatro agentes expuestos como herramientas (agents-as-tools)")


# ---------------------------------------------------------------- JERÁRQUICA
def jerarquica():
    p = []
    p.append(box(400, 96, 180, 42, "boxU", "Usuario"))
    p.append(arrow(490, 138, 490, 166, "line", "a", doble=True))
    p.append(box(330, 168, 320, 64, "boxO", "Director de Operaciones",
                 "Coordina gerencias, redacta la respuesta final"))
    p.append(label(50, 196, "NIVEL 1", "lvl", "start"))
    p.append(label(50, 300, "NIVEL 2", "lvl", "start"))
    p.append(label(50, 440, "NIVEL 3", "lvl", "start"))

    p.append(elbow(490, 232, 300, 276, "line", "a", doble=True))
    p.append(elbow(490, 232, 690, 276, "line", "a", doble=True))
    p.append(box(150, 278, 300, 62, "boxM", "Gerencia de Información",
                 "Qué se sabe: conocimiento y datos"))
    p.append(box(540, 278, 300, 62, "boxM", "Gerencia de Operaciones",
                 "Qué se hace: dictamen y ejecución"))
    p.append(label(560, 246, "as_tool()"))

    nombres = ["Esp. FAQs", "Esp. Clima", "Esp. Seguridad", "Esp. Agenda"]
    xs = [120, 310, 520, 710]
    padres = [300, 300, 690, 690]
    for x, padre_cx, nombre, (_, r, tl) in zip(xs, padres, nombres, ESP):
        cx = x + 85
        p.append(elbow(padre_cx, 340, cx, 406, "line", "a", doble=True))
        p.append(box(x, 408, 170, 46 + 18 * len(tl), "boxS", nombre, r, tl))

    p.append(label(40, 596, "El director no toca ninguna integración: delega en gerencias y cada gerencia delega en sus especialistas.", "note", "start"))
    p.append(label(40, 618, "Ventaja: escala sin tocar la cima al crecer los requerimientos. Costo: más saltos, más latencia y más tokens.", "note", "start"))
    return envolver("\n".join(p), "Arquitectura JERÁRQUICA",
                    "Parachute S.A. — director → dos gerencias intermedias → cuatro especialistas (as_tool anidado)")


# ---------------------------------------------------------------- DESCENTRALIZADA
def descentralizada():
    p = []
    BW, BH = 180, 62

    nodos = {
        "Recepción": (540, 150, "Primer contacto"),
        "FAQs": (840, 300, "Base de conocimiento"),
        "Agenda": (740, 500, "Citas"),
        "Seguridad": (400, 520, "Reglas de salto"),
        "Clima": (250, 310, "Open-Meteo"),
    }

    aristas = [
        ("Recepción", "FAQs"),
        ("Recepción", "Clima"),
        ("Recepción", "Seguridad"),
        ("Recepción", "Agenda"),
        ("Clima", "Seguridad"),
        ("Seguridad", "Agenda"),
        ("FAQs", "Agenda"),
        ("Clima", "FAQs"),
    ]
    for a, b in aristas:
        c1 = nodos[a][:2]
        c2 = nodos[b][:2]
        (x1, y1), (x2, y2) = recortar(c1, c2, BW + 12, BH + 12)
        p.append(arrow(x1, y1, x2, y2, "line", "a", doble=True))

    for n, (cx, cy, r) in nodos.items():
        clase = "boxO" if n == "Recepción" else "boxS"
        p.append(box(cx - BW / 2, cy - BH / 2, BW, BH, clase, n, r))

    p.append(box(60, 110, 150, 42, "boxU", "Usuario"))
    (ux, uy), (rx, ry) = recortar((135, 131), (540, 150), 162, 54)
    p.append(arrow(ux, uy, rx, ry, "line2", "b", doble=True))
    p.append(label(355, 116, "el usuario entra por Recepción y luego conversa con el agente que tenga el control", "note"))
    p.append(label(700, 205, "handoff()"))

    p.append(label(40, 596, "No existe coordinador: cada agente decide a qué par transferir la conversación y quien recibe el control responde al usuario.", "note", "start"))
    p.append(label(40, 618, "Ventaja: menos saltos y prompts más cortos. Costo: nadie garantiza el orden clima → seguridad → agenda; es más difícil de auditar.", "note", "start"))
    return envolver("\n".join(p), "Arquitectura DESCENTRALIZADA",
                    "Parachute S.A. — red de agentes pares que se transfieren el control (handoffs)")


for nombre, fn in [
    ("centralizada", centralizada),
    ("jerarquica", jerarquica),
    ("descentralizada", descentralizada),
]:
    (AQUI / f"{nombre}.svg").write_text(fn(), encoding="utf-8")
    print("escrito", nombre)
