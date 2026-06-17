"""
generate_diagrams.py
====================
Generates 7 presentation reveal diagrams for the Bilge Pump SysML model.
Each diagram maps to one primary .sysml file and is revealed after a group
paper-modelling exercise.

Output: bilgepump/presentation/diagram_N_<concept>.png  (1280 × 720 px each)
Style:  white / light background, teal + blue accents, navy headers
"""

import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Color palette  (teal + blue + navy on white/light)
# ---------------------------------------------------------------------------
C = {
    "bg": "#FFFFFF",
    "bg2": "#F0F4F8",
    "navy": "#0B2340",
    "teal": "#0D9488",
    "teal_lt": "#CCFBF1",
    "blue": "#2563EB",
    "blue_lt": "#DBEAFE",
    "green": "#16A34A",
    "green_lt": "#DCFCE7",
    "amber": "#D97706",
    "amber_lt": "#FEF3C7",
    "red": "#DC2626",
    "red_lt": "#FEE2E2",
    "grey": "#94A3B8",
    "grey_lt": "#F1F5F9",
    "text": "#18202C",
    "muted": "#64748B",
    "border": "#CBD5E1",
    "code_bg": "#E8EFF6",
    "code_fg": "#0B2340",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
MONO = "Consolas, Courier New, monospace"


def fig_ax(title_left="", title_right=""):
    """Create a 1280×720 figure with slide header and footer."""
    fig = plt.figure(figsize=(16, 9), dpi=80)
    fig.patch.set_facecolor(C["bg"])

    # header band
    hdr = fig.add_axes([0, 0.888, 1, 0.112])
    hdr.set_facecolor(C["navy"])
    hdr.set_xlim(0, 1)
    hdr.set_ylim(0, 1)
    hdr.axis("off")
    hdr.text(
        0.035,
        0.5,
        title_left,
        color="white",
        fontsize=18,
        fontweight="bold",
        va="center",
        ha="left",
        fontfamily="sans-serif",
    )
    if title_right:
        hdr.text(
            0.965,
            0.5,
            title_right,
            color=C["teal"],
            fontsize=11,
            fontweight="bold",
            va="center",
            ha="right",
            fontfamily="monospace",
        )

    # footer strip
    ftr = fig.add_axes([0, 0, 1, 0.055])
    ftr.set_facecolor(C["bg2"])
    ftr.set_xlim(0, 1)
    ftr.set_ylim(0, 1)
    ftr.axis("off")
    ftr.axhline(1.0, color=C["teal"], linewidth=2.5)
    ftr.text(
        0.035,
        0.42,
        "SysML v2 · Bilge Pump System",
        color=C["navy"],
        fontsize=9,
        fontweight="bold",
        va="center",
    )
    ftr.text(
        0.5,
        0.42,
        "Group Exercise Reveal",
        color=C["muted"],
        fontsize=9,
        va="center",
        ha="center",
    )
    ftr.text(
        0.965,
        0.42,
        "ManuelReta / SysMLInfra",
        color=C["muted"],
        fontsize=9,
        va="center",
        ha="right",
    )

    ax = fig.add_axes([0.025, 0.09, 0.95, 0.78])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_facecolor(C["bg"])
    return fig, ax


def box(
    ax,
    x,
    y,
    w,
    h,
    label,
    sublabel="",
    fc=C["blue_lt"],
    ec=C["blue"],
    lw=1.5,
    fs=10,
    bold=False,
    stereotype="",
    radius=0.012,
):
    """Draw a rounded rectangle with centred label."""
    rect = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
        zorder=3,
    )
    ax.add_patch(rect)
    cy = y + h / 2
    if stereotype:
        ax.text(
            x + w / 2,
            cy + h * 0.17,
            f"«{stereotype}»",
            ha="center",
            va="center",
            fontsize=7.5,
            color=C["muted"],
            fontstyle="italic",
            zorder=4,
        )
        cy -= h * 0.08
    ax.text(
        x + w / 2,
        cy,
        label,
        ha="center",
        va="center",
        fontsize=fs,
        fontweight="bold" if bold else "normal",
        color=C["navy"],
        zorder=4,
    )
    if sublabel:
        ax.text(
            x + w / 2,
            y + h * 0.22,
            sublabel,
            ha="center",
            va="center",
            fontsize=7.5,
            color=C["muted"],
            zorder=4,
            fontstyle="italic",
        )


def header_box(
    ax, x, y, w, h, label, fc=C["teal"], tc="white", fs=11, stereotype="", radius=0.012
):
    """Solid-fill header block (used as part def header compartment)."""
    rect = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=0,
        facecolor=fc,
        zorder=3,
    )
    ax.add_patch(rect)
    if stereotype:
        ax.text(
            x + w / 2,
            y + h * 0.72,
            f"«{stereotype}»",
            ha="center",
            va="center",
            fontsize=7,
            color="white",
            fontstyle="italic",
            zorder=4,
        )
    ax.text(
        x + w / 2,
        y + h * (0.35 if stereotype else 0.5),
        label,
        ha="center",
        va="center",
        fontsize=fs,
        fontweight="bold",
        color=tc,
        zorder=4,
    )


def arrow(
    ax,
    x0,
    y0,
    x1,
    y1,
    color=C["navy"],
    lw=1.5,
    style="->",
    label="",
    label_color=None,
    label_fs=8,
    mid_offset=0,
):
    """Draw a straight arrow with optional label."""
    ax.annotate(
        "",
        xy=(x1, y1),
        xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle=style, color=color, lw=lw, connectionstyle="arc3,rad=0"
        ),
        zorder=5,
    )
    if label:
        mx, my = (x0 + x1) / 2 + mid_offset, (y0 + y1) / 2
        ax.text(
            mx,
            my,
            label,
            ha="center",
            va="bottom",
            fontsize=label_fs,
            color=label_color or color,
            zorder=6,
        )


def curved_arrow(
    ax, x0, y0, x1, y1, rad=0.15, color=C["navy"], lw=1.5, label="", label_fs=8
):
    ax.annotate(
        "",
        xy=(x1, y1),
        xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle="->", color=color, lw=lw, connectionstyle=f"arc3,rad={rad}"
        ),
        zorder=5,
    )
    if label:
        mx = (x0 + x1) / 2
        my = (y0 + y1) / 2 + abs(rad) * 0.25
        ax.text(
            mx,
            my,
            label,
            ha="center",
            va="bottom",
            fontsize=label_fs,
            color=color,
            zorder=6,
        )


def port_square(ax, x, y, size=0.018, color=C["teal"]):
    sq = plt.Rectangle(
        (x - size / 2, y - size / 2),
        size,
        size,
        facecolor=color,
        edgecolor=C["navy"],
        linewidth=1,
        zorder=6,
    )
    ax.add_patch(sq)


def code_inset(ax, x, y, lines, w=0.38, title="SysML v2"):
    """Monospace code snippet box."""
    lh = 0.038
    h = lh * (len(lines) + 1.4)
    rect = FancyBboxPatch(
        (x, y - h),
        w,
        h,
        boxstyle="round,pad=0,rounding_size=0.008",
        linewidth=1.2,
        edgecolor=C["teal"],
        facecolor=C["code_bg"],
        zorder=7,
    )
    ax.add_patch(rect)
    ax.text(
        x + 0.012,
        y - 0.018,
        title,
        fontsize=7.5,
        color=C["teal"],
        fontweight="bold",
        va="top",
        fontfamily="monospace",
        zorder=8,
    )
    for i, line in enumerate(lines):
        ax.text(
            x + 0.012,
            y - 0.015 - lh * (i + 1.1),
            line,
            fontsize=8,
            color=C["code_fg"],
            va="top",
            fontfamily="monospace",
            zorder=8,
        )


def save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=80, bbox_inches="tight", facecolor=C["bg"], edgecolor="none")
    plt.close(fig)
    print(f"  saved: {name}")


# ===========================================================================
# DIAGRAM 1 — Architecture.sysml — System Context
# ===========================================================================
def diagram_1():
    fig, ax = fig_ax("1 · System Context", "Architecture.sysml")

    # ── system boundary ──────────────────────────────────────────────────
    bnd = FancyBboxPatch(
        (0.16, 0.07),
        0.66,
        0.84,
        boxstyle="round,pad=0,rounding_size=0.02",
        linewidth=2.5,
        linestyle="--",
        edgecolor=C["navy"],
        facecolor=C["bg2"],
        zorder=1,
    )
    ax.add_patch(bnd)
    ax.text(
        0.49,
        0.965,
        "BilgePumpSystem",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color=C["navy"],
        zorder=4,
    )
    ax.text(
        0.49,
        0.935,
        "part def  ·  Architecture.sysml",
        ha="center",
        va="center",
        fontsize=8.5,
        color=C["muted"],
        fontstyle="italic",
        zorder=4,
    )

    # ── inner part usages: 2 rows × 4 ────────────────────────────────────
    parts = [
        ("sensor", "BilgeWaterSensor", 0.20, 0.72),
        ("controller", "PumpController", 0.36, 0.72),
        ("power", "PowerSupply", 0.52, 0.72),
        ("alarm", "AlarmSystem", 0.68, 0.72),
        ("pumpA", "BilgePumpA", 0.20, 0.39),
        ("pumpB", "BilgePumpB", 0.36, 0.39),
        ("discharge", "DischargeLine", 0.52, 0.39),
        ("ui", "OperatorInterface", 0.68, 0.39),
    ]
    pw, ph = 0.135, 0.22
    for name, ptype, px, py in parts:
        header_box(ax, px, py + ph * 0.62, pw, ph * 0.38, name, fc=C["teal"], fs=9)
        rect = FancyBboxPatch(
            (px, py),
            pw,
            ph * 0.62,
            boxstyle="round,pad=0,rounding_size=0.008",
            linewidth=1.5,
            edgecolor=C["teal"],
            facecolor="white",
            zorder=3,
        )
        ax.add_patch(rect)
        ax.text(
            px + pw / 2,
            py + ph * 0.31,
            f": {ptype}",
            ha="center",
            va="center",
            fontsize=7,
            color=C["muted"],
            fontstyle="italic",
            zorder=4,
        )

    # ── simple internal flow arrows ───────────────────────────────────────
    # sensor → controller
    arrow(ax, 0.335, 0.835, 0.36, 0.835, color=C["teal"], lw=1.2)
    # controller → pumpA/pumpB
    arrow(ax, 0.43, 0.72, 0.29, 0.61, color=C["teal"], lw=1.2)
    arrow(ax, 0.44, 0.72, 0.44, 0.61, color=C["teal"], lw=1.2)
    # pumpA/B → discharge
    arrow(ax, 0.335, 0.5, 0.52, 0.5, color=C["teal"], lw=1.2)
    arrow(ax, 0.495, 0.5, 0.52, 0.5, color=C["teal"], lw=1.2)
    # controller → alarm → ui
    arrow(ax, 0.43, 0.835, 0.68, 0.835, color=C["amber"], lw=1.2)
    arrow(ax, 0.815, 0.72, 0.755, 0.61, color=C["amber"], lw=1.2)

    # ── external actors ───────────────────────────────────────────────────
    # Each actor sits on the nearest side → short, non-crossing arrows
    #   LEFT  : MachinerySpace  → sensor   (top-left block)
    #   RIGHT top: VesselPowerSystem → alarm (top-right block)
    #   RIGHT bot: Operator/Crew     → ui   (bottom-right block)
    #   BOTTOM: Sea/Discharge   ← discharge (bottom-centre block, outflow)
    actors = [
        (
            "MachinerySpace",
            "flooding inflow",
            0.010,
            0.760,
            0.130,
            0.115,
            (0.140, 0.8175),
            (0.200, 0.835),
            C["red"],
        ),
        (
            "VesselPower\nSystem",
            "IEC 61850 bus",
            0.855,
            0.760,
            0.130,
            0.115,
            (0.855, 0.8175),
            (0.815, 0.835),
            C["blue"],
        ),
        (
            "Operator / Crew",
            "HMI override",
            0.855,
            0.390,
            0.130,
            0.115,
            (0.855, 0.4475),
            (0.815, 0.500),
            C["blue"],
        ),
        (
            "Sea / Discharge",
            "MARPOL overboard",
            0.475,
            0.010,
            0.155,
            0.070,
            (0.5875, 0.390),
            (0.5875, 0.082),
            C["green"],
        ),
    ]
    for lbl, sub, ax_, ay_, aw, ah, astart, aend, ac in actors:
        rect = FancyBboxPatch(
            (ax_, ay_),
            aw,
            ah,
            boxstyle="round,pad=0,rounding_size=0.012",
            linewidth=1.5,
            linestyle=":",
            edgecolor=ac,
            facecolor="white",
            zorder=3,
        )
        ax.add_patch(rect)
        ax.text(
            ax_ + aw / 2,
            ay_ + ah * 0.62,
            lbl,
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color=C["navy"],
            zorder=4,
        )
        ax.text(
            ax_ + aw / 2,
            ay_ + ah * 0.28,
            sub,
            ha="center",
            va="center",
            fontsize=7,
            color=C["muted"],
            fontstyle="italic",
            zorder=4,
        )
        arrow(ax, astart[0], astart[1], aend[0], aend[1], color=ac, lw=1.5)

    # ── code snippet ──────────────────────────────────────────────────────
    code_inset(
        ax,
        0.635,
        0.285,
        [
            "part sensor : BilgeWaterSensor;",
            "part pumpA  : BilgePumpA;",
            "part discharge : DischargeLine;",
        ],
        w=0.335,
        title="Architecture.sysml",
    )

    save(fig, "diagram_1_system_context.png")


# ===========================================================================
# DIAGRAM 2 — Library.sysml — Block Attribute Definitions
# ===========================================================================
def diagram_2():
    fig, ax = fig_ax("2 · Type Definitions & Attributes", "Library.sysml")

    # Fixed layout: 2 columns × 2 rows
    # BH=0.38 → bottom row y=0.03, top row y=0.57
    # Gap between rows = 0.16 — fits the code inset
    BW = 0.44
    BH = 0.38  # fixed block height
    HDR = 0.065
    ATTR_LH = 0.042  # line height per attribute
    PORT_LH = 0.038  # line height per port
    DIV = 0.008  # divider padding

    def draw_block(x, y, name, attrs, ports):
        """Draw a fixed-height BDD block with header/attr/port compartments."""
        # outer shadow
        outer = FancyBboxPatch(
            (x - 0.004, y - 0.004),
            BW + 0.008,
            BH + 0.008,
            boxstyle="round,pad=0,rounding_size=0.014",
            linewidth=0,
            facecolor=C["border"],
            zorder=2,
        )
        ax.add_patch(outer)

        # white body
        body = FancyBboxPatch(
            (x, y),
            BW,
            BH,
            boxstyle="round,pad=0,rounding_size=0.012",
            linewidth=2,
            edgecolor=C["teal"],
            facecolor="white",
            zorder=3,
        )
        ax.add_patch(body)

        # header band (top)
        header_box(
            ax,
            x,
            y + BH - HDR,
            BW,
            HDR,
            name,
            fc=C["teal"],
            fs=10.5,
            stereotype="part def",
            radius=0.010,
        )

        # attributes section
        attr_top = y + BH - HDR - DIV
        for i, attr in enumerate(attrs):
            ty = attr_top - ATTR_LH * (i + 0.7)
            ax.text(
                x + 0.016,
                ty,
                attr,
                fontsize=8,
                color=C["navy"],
                va="center",
                fontfamily="monospace",
                zorder=4,
            )

        # divider before ports
        div_y = attr_top - ATTR_LH * len(attrs) - DIV
        ax.plot(
            [x + 0.01, x + BW - 0.01],
            [div_y, div_y],
            color=C["border"],
            lw=1.0,
            zorder=4,
        )

        # teal port band at bottom
        port_band_h = PORT_LH * len(ports) + 0.028
        port_rect = FancyBboxPatch(
            (x, y),
            BW,
            port_band_h,
            boxstyle="square,pad=0",
            linewidth=0,
            facecolor=C["teal_lt"],
            zorder=3,
        )
        ax.add_patch(port_rect)
        ax.text(
            x + 0.012,
            y + port_band_h - 0.010,
            "ports:",
            fontsize=7,
            color=C["muted"],
            va="center",
            fontstyle="italic",
            zorder=4,
        )
        for i, pt in enumerate(ports):
            py2 = y + port_band_h - 0.022 - PORT_LH * (i + 0.8)
            port_square(ax, x + 0.024, py2, size=0.015, color=C["teal"])
            ax.text(
                x + 0.040,
                py2,
                pt,
                fontsize=7.5,
                color=C["teal"],
                va="center",
                fontfamily="monospace",
                zorder=4,
            )

    # ── top-left: BilgeWaterSensor ─────────────────────────────────────
    draw_block(
        0.03,
        0.57,
        "BilgeWaterSensor",
        [
            "attribute waterLevel      : Real",
            "attribute triggerLevel_m  : Real",
            "attribute sampleRate_Hz   : Real",
        ],
        ["levelOut : LevelSignalPort"],
    )

    # ── top-right: PumpController ──────────────────────────────────────
    draw_block(
        0.54,
        0.57,
        "PumpController",
        [
            "attribute responseTime_s  : Real",
            "attribute failoverTime_s  : Real",
            "attribute commandDelay_ms : Real",
        ],
        ["levelIn     : ~LevelSignalPort", "pumpAControl : PumpControlPort"],
    )

    # ── bottom-left: BilgePumpA ────────────────────────────────────────
    draw_block(
        0.03,
        0.03,
        "BilgePumpA",
        [
            "attribute flowRate        : Real",
            "attribute pumpEfficiency  : Real",
            "attribute isRedundant     : Boolean",
            "attribute NPSH_m          : Real",
        ],
        ["controlIn : ~PumpControlPort", "flowOut   : FluidFlowPort"],
    )

    # ── bottom-right: DischargeLine ────────────────────────────────────
    draw_block(
        0.54,
        0.03,
        "DischargeLine",
        [
            "attribute pipeLossFactor  : Real",
            "attribute designInflow    : Real",
            "attribute dischargePressure_bar : Real",
        ],
        ["flowInA : ~FluidFlowPort", "flowInB : ~FluidFlowPort"],
    )

    # ── connecting arrows ──────────────────────────────────────────────
    # top row y=0.57, BH=0.38 → block mid = 0.57+0.38/2 = 0.76
    # Sensor ↔ Controller (same row, via LevelSignalPort)
    ax.annotate(
        "",
        xy=(0.54, 0.855),
        xytext=(0.47, 0.855),
        arrowprops=dict(arrowstyle="<->", color=C["navy"], lw=1.5),
        zorder=6,
    )
    ax.text(
        0.505,
        0.870,
        "LevelSignalPort",
        ha="center",
        fontsize=8,
        color=C["navy"],
        fontstyle="italic",
        zorder=7,
    )

    # Controller ↔ PumpA (cross-row, PumpControlPort)
    # top-right controller at x=0.54+0.44=0.98 right edge; bottom-left at x=0.47 right edge
    ax.annotate(
        "",
        xy=(0.47, 0.28),
        xytext=(0.54, 0.66),
        arrowprops=dict(
            arrowstyle="<->", color=C["blue"], lw=1.5, connectionstyle="arc3,rad=-0.18"
        ),
        zorder=6,
    )
    ax.text(
        0.46,
        0.485,
        "PumpControlPort",
        ha="right",
        fontsize=8,
        color=C["blue"],
        fontstyle="italic",
        zorder=7,
    )

    # PumpA → DischargeLine (same bottom row, FluidFlowPort)
    ax.annotate(
        "",
        xy=(0.54, 0.195),
        xytext=(0.47, 0.195),
        arrowprops=dict(arrowstyle="->", color=C["green"], lw=1.5),
        zorder=6,
    )
    ax.text(
        0.505,
        0.210,
        "FluidFlowPort",
        ha="center",
        fontsize=8,
        color=C["green"],
        fontstyle="italic",
        zorder=7,
    )

    # ── code snippet: placed in the inter-row gap (y=0.41..0.57) ─────────
    # 2 lines → h = 0.038*(2+1.4) = 0.129; snippet top=0.555, bottom=0.426
    code_inset(
        ax,
        0.28,
        0.555,
        ["attribute flowRate : Real;", "port levelOut : LevelSignalPort;"],
        w=0.40,
        title="Library.sysml",
    )

    save(fig, "diagram_2_attributes_library.png")


# ===========================================================================
# DIAGRAM 3 — Architecture.sysml — Internal Block Diagram (ports/connectors)
# ===========================================================================
def diagram_3():
    fig, ax = fig_ax("3 · Port Connections  (IBD)", "Architecture.sysml")

    # Four component blocks laid out left → right
    # Slightly narrower to avoid right-edge clipping
    comps = [
        ("sensor", "BilgeWaterSensor", 0.02, 0.35, 0.155, 0.30),
        ("controller", "PumpController", 0.27, 0.18, 0.185, 0.64),
        ("pumpA", "BilgePumpA", 0.58, 0.52, 0.155, 0.30),
        ("discharge", "DischargeLine", 0.78, 0.35, 0.155, 0.30),
    ]

    for name, ptype, bx, by, bw, bh in comps:
        header_box(ax, bx, by + bh * 0.72, bw, bh * 0.28, name, fc=C["navy"], fs=9.5)
        body = FancyBboxPatch(
            (bx, by),
            bw,
            bh * 0.72,
            boxstyle="round,pad=0,rounding_size=0.01",
            linewidth=2,
            edgecolor=C["navy"],
            facecolor=C["bg2"],
            zorder=3,
        )
        ax.add_patch(body)
        ax.text(
            bx + bw / 2,
            by + bh * 0.35,
            f": {ptype}",
            ha="center",
            va="center",
            fontsize=7.5,
            color=C["muted"],
            fontstyle="italic",
            zorder=4,
        )

    # ── PORTS ─────────────────────────────────────────────────────────────
    # helper: port squares on right / left edges
    def right_port(bx, bw, by, bh, frac, label, text_right=True):
        px = bx + bw
        py = by + bh * frac
        port_square(ax, px, py)
        if text_right:
            ax.text(
                px + 0.015,
                py,
                label,
                fontsize=7.5,
                color=C["teal"],
                va="center",
                fontfamily="monospace",
                zorder=6,
            )
        else:
            ax.text(
                px - 0.015,
                py,
                label,
                fontsize=7.5,
                color=C["teal"],
                va="center",
                ha="right",
                fontfamily="monospace",
                zorder=6,
            )
        return px, py

    def left_port(bx, by, bh, frac, label):
        px = bx
        py = by + bh * frac
        port_square(ax, px, py)
        ax.text(
            px + 0.015,
            py,
            label,
            fontsize=7.5,
            color=C["teal"],
            va="center",
            fontfamily="monospace",
            zorder=6,
        )
        return px, py

    # sensor.levelOut  (right side)
    sx, sy_h, sw, sh = 0.02, 0.35, 0.155, 0.30
    lo_x, lo_y = right_port(sx, sw, sy_h, sh, 0.65, "levelOut", False)

    # controller.levelIn (left side)
    cx, cy, cw, ch = 0.27, 0.18, 0.185, 0.64
    li_x, li_y = left_port(cx, cy, ch, 0.82, "levelIn")
    # controller.pumpAControl (right side)
    pa_x, pa_y = right_port(cx, cw, cy, ch, 0.62, "pumpAControl", False)
    # controller.alarmOut (right side, lower)
    ao_x, ao_y = right_port(cx, cw, cy, ch, 0.38, "alarmOut", False)
    # controller.statusOut (right side)
    so_x, so_y = right_port(cx, cw, cy, ch, 0.20, "statusOut", False)
    # controller.overrideIn (left side)
    ov_x, ov_y = left_port(cx, cy, ch, 0.20, "overrideIn")

    # pumpA.controlIn (left side)
    pax, pay, paw, pah = 0.58, 0.52, 0.155, 0.30
    ci_x, ci_y = left_port(pax, pay, pah, 0.72, "controlIn")
    # pumpA.flowOut (right side)
    fo_x, fo_y = right_port(pax, paw, pay, pah, 0.40, "flowOut", False)

    # discharge.flowInA (left side)
    dx, dy, _, dh = 0.78, 0.35, 0.155, 0.30
    fi_x, fi_y = left_port(dx, dy, dh, 0.55, "flowInA")

    # ── CONNECTIONS ───────────────────────────────────────────────────────
    # [1] sensor.levelOut → controller.levelIn
    arrow(
        ax,
        lo_x,
        lo_y,
        li_x,
        li_y,
        color=C["teal"],
        lw=2,
        label="water level signal",
        label_fs=7.5,
        label_color=C["teal"],
    )

    # [2] controller.pumpAControl → pumpA.controlIn
    # goes right with slight jog
    ax.plot(
        [pa_x, pa_x + 0.02, pax - 0.02, pax],
        [pa_y, pa_y, ci_y, ci_y],
        color=C["blue"],
        lw=2,
        zorder=5,
    )
    ax.annotate(
        "",
        xy=(ci_x, ci_y),
        xytext=(ci_x - 0.005, ci_y),
        arrowprops=dict(arrowstyle="->", color=C["blue"], lw=2),
        zorder=6,
    )
    ax.text(
        (pa_x + pax) / 2,
        pa_y + 0.03,
        "pump command",
        ha="center",
        fontsize=7.5,
        color=C["blue"],
        zorder=6,
    )

    # [3] pumpA.flowOut → discharge.flowInA
    arrow(
        ax,
        fo_x,
        fo_y,
        fi_x,
        fi_y,
        color=C["green"],
        lw=2,
        label="fluid flow  (m³/s)",
        label_fs=7.5,
        label_color=C["green"],
    )

    # ── legend panel ──────────────────────────────────────────────────────
    lx, ly = 0.03, 0.20
    for color, label in [
        (C["teal"], "signal flow"),
        (C["blue"], "control command"),
        (C["green"], "fluid flow"),
    ]:
        ax.plot([lx, lx + 0.05], [ly, ly], color=color, lw=2.5)
        ax.annotate(
            "",
            xy=(lx + 0.05, ly),
            xytext=(lx + 0.045, ly),
            arrowprops=dict(arrowstyle="->", color=color, lw=2.5),
            zorder=6,
        )
        ax.text(lx + 0.065, ly, label, fontsize=8, color=color, va="center")
        ly -= 0.055

    # ── SysML port type labels ────────────────────────────────────────────
    ax.text(
        0.20,
        0.69,
        "LevelSignalPort",
        fontsize=7.5,
        color=C["muted"],
        ha="center",
        fontstyle="italic",
    )
    ax.text(
        0.545,
        0.685,
        "PumpControlPort",
        fontsize=7.5,
        color=C["muted"],
        ha="center",
        fontstyle="italic",
    )
    ax.text(
        0.755,
        0.52,
        "FluidFlowPort",
        fontsize=7.5,
        color=C["muted"],
        ha="center",
        fontstyle="italic",
    )

    # ── code snippet ──────────────────────────────────────────────────────
    code_inset(
        ax,
        0.58,
        0.42,
        [
            "connect sensor.levelOut",
            "    to controller.levelIn;",
            "connect pumpA.flowOut",
            "    to discharge.flowInA;",
        ],
        w=0.39,
        title="Architecture.sysml",
    )

    save(fig, "diagram_3_port_connections.png")


# ===========================================================================
# DIAGRAM 4 — StateMachine.sysml — Controller State Machine
# ===========================================================================
def diagram_4():
    fig, ax = fig_ax("4 · Controller Behaviour  (State Machine)", "StateMachine.sysml")

    # States: (id, label, x, y, w, h, fc, ec)
    states = {
        "IDLE": ("IDLE", 0.39, 0.82, 0.20, 0.11, C["grey_lt"], C["grey"]),
        "MONITORING": ("MONITORING", 0.39, 0.63, 0.20, 0.11, C["blue_lt"], C["blue"]),
        "PUMP_A_ACTIVE": (
            "PUMP_A_ACTIVE",
            0.39,
            0.44,
            0.20,
            0.11,
            C["teal_lt"],
            C["teal"],
        ),
        "DUAL_PUMP_ACTIVE": (
            "DUAL_PUMP\nACTIVE",
            0.68,
            0.44,
            0.18,
            0.11,
            "#DCFCE7",
            C["green"],
        ),
        "ALARM_TRIGGERED": (
            "ALARM\nTRIGGERED",
            0.68,
            0.25,
            0.18,
            0.11,
            C["amber_lt"],
            C["amber"],
        ),
        "FAILOVER": ("FAILOVER", 0.39, 0.25, 0.18, 0.11, "#FEF9C3", "#CA8A04"),
        "FAULT": ("FAULT", 0.12, 0.25, 0.16, 0.11, C["red_lt"], C["red"]),
    }

    for sid, (lbl, sx, sy, sw, sh, fc, ec) in states.items():
        rect = FancyBboxPatch(
            (sx, sy),
            sw,
            sh,
            boxstyle="round,pad=0,rounding_size=0.018",
            linewidth=2.2,
            edgecolor=ec,
            facecolor=fc,
            zorder=3,
        )
        ax.add_patch(rect)
        ax.text(
            sx + sw / 2,
            sy + sh / 2,
            lbl,
            ha="center",
            va="center",
            fontsize=9.5,
            fontweight="bold",
            color=C["navy"],
            zorder=4,
        )

    # initial pseudo-state
    circ = plt.Circle((0.49, 0.955), 0.018, color=C["navy"], zorder=5)
    ax.add_patch(circ)
    arrow(ax, 0.49, 0.937, 0.49, 0.93, color=C["navy"], lw=1.5)

    # helper centre positions
    def ctr(sid):
        sx, sy, sw, sh = states[sid][1], states[sid][2], states[sid][3], states[sid][4]
        return sx + sw / 2, sy + sh / 2

    def top(sid):
        sx, sy, sw, sh = states[sid][1], states[sid][2], states[sid][3], states[sid][4]
        return sx + sw / 2, sy + sh

    def bot(sid):
        sx, sy, sw, _ = states[sid][1], states[sid][2], states[sid][3], states[sid][4]
        return sx + sw / 2, sy

    def left_e(sid):
        sx, sy, _, sh = states[sid][1], states[sid][2], states[sid][3], states[sid][4]
        return sx, sy + sh / 2

    def right_e(sid):
        sx, sy, sw, sh = states[sid][1], states[sid][2], states[sid][3], states[sid][4]
        return sx + sw, sy + sh / 2

    # ── transitions ───────────────────────────────────────────────────────
    # startup: initial → IDLE
    arrow(
        ax,
        *top("IDLE"),
        *top("IDLE"),  # dummy; already done above
        color=C["navy"],
        lw=0,
    )

    # IDLE → MONITORING
    arrow(
        ax,
        *bot("IDLE"),
        *top("MONITORING"),
        color=C["navy"],
        lw=1.8,
        label="startup",
        label_fs=8,
    )

    # MONITORING → PUMP_A_ACTIVE
    arrow(
        ax,
        *bot("MONITORING"),
        *top("PUMP_A_ACTIVE"),
        color=C["teal"],
        lw=1.8,
        label="[waterLevel ≥ triggerLevel_m]",
        label_fs=7.5,
    )

    # PUMP_A_ACTIVE → DUAL_PUMP_ACTIVE (right)
    rx, ry = right_e("PUMP_A_ACTIVE")
    lx2, ly2 = left_e("DUAL_PUMP_ACTIVE")
    arrow(
        ax,
        rx,
        ry,
        lx2,
        ly2,
        color=C["green"],
        lw=1.8,
        label="[high demand]",
        label_fs=7.5,
        mid_offset=0.0,
    )

    # PUMP_A_ACTIVE → ALARM_TRIGGERED
    rx2, ry2 = right_e("PUMP_A_ACTIVE")
    ax.annotate(
        "",
        xy=(0.68, 0.305),
        xytext=(0.59, 0.45),
        arrowprops=dict(
            arrowstyle="->", color=C["amber"], lw=1.8, connectionstyle="arc3,rad=-0.25"
        ),
        zorder=5,
    )
    ax.text(
        0.69, 0.39, "[activationDelay ≤ 2s]", fontsize=7, color=C["amber"], va="center"
    )

    # PUMP_A_ACTIVE → FAILOVER (down)
    ax.annotate(
        "",
        xy=(0.485, 0.36),
        xytext=(0.48, 0.44),
        arrowprops=dict(arrowstyle="->", color="#CA8A04", lw=1.8),
        zorder=5,
    )
    ax.text(
        0.51,
        0.415,
        "[pumpA fault\nfailoverTime ≤ 3s]",
        fontsize=7,
        color="#CA8A04",
        va="center",
    )

    # PUMP_A_ACTIVE → FAULT (far left)
    ax.annotate(
        "",
        xy=(0.28, 0.305),
        xytext=(0.39, 0.45),
        arrowprops=dict(
            arrowstyle="->", color=C["red"], lw=1.8, connectionstyle="arc3,rad=0.3"
        ),
        zorder=5,
    )
    ax.text(
        0.27,
        0.39,
        "[responseTime > 5s\nFM-C-001]",
        fontsize=7,
        color=C["red"],
        va="center",
        ha="center",
    )

    # MONITORING ← PUMP_A_ACTIVE (left side, return arc)
    ax.annotate(
        "",
        xy=(0.37, 0.685),
        xytext=(0.37, 0.50),
        arrowprops=dict(
            arrowstyle="->", color=C["navy"], lw=1.4, connectionstyle="arc3,rad=0.35"
        ),
        zorder=5,
    )
    ax.text(
        0.30,
        0.59,
        "dewater\ncomplete",
        fontsize=7,
        color=C["navy"],
        va="center",
        ha="center",
    )

    # timing annotations
    for txt, x, y, c in [
        ("responseTime_s ≤ 5.0 s\n[BPS-REQ-005]", 0.12, 0.545, C["blue"]),
        ("failoverTime_s ≤ 3.0 s\n[BPS-REQ-006]", 0.02, 0.32, "#CA8A04"),
    ]:
        ax.text(
            x,
            y,
            txt,
            fontsize=7.5,
            color=c,
            va="center",
            ha="left",
            style="italic",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=c, lw=0.8, alpha=0.85),
        )

    # ── code snippet ──────────────────────────────────────────────────────
    code_inset(
        ax,
        0.02,
        0.96,
        [
            "state MONITORING;",
            "transition MONITORING to PUMP_A_ACTIVE",
            "  // guard: waterLevel ≥ triggerLevel_m",
            "  // timing: responseTime_s ≤ 5.0 s",
        ],
        w=0.38,
        title="StateMachine.sysml",
    )

    save(fig, "diagram_4_state_machine.png")


# ===========================================================================
# DIAGRAM 5 — Safety.sysml — Hazard-to-Requirement Trace
# ===========================================================================
def diagram_5():
    fig, ax = fig_ax("5 · Hazard  →  Safety Constraint  →  Requirement", "Safety.sysml")

    # Chain nodes — top to bottom: Loss → Hazard → UCA → SC → REQ
    chain = [
        {
            "label": "L-1",
            "sub": "Loss of vessel — sinking / capsize",
            "stereo": "Loss",
            "reg": "SOLAS Chapter II-1",
            "fc": "#FEE2E2",
            "ec": C["red"],
            "y": 0.825,
        },
        {
            "label": "H-1",
            "sub": "Bilge water exceeds damage stability threshold",
            "stereo": "Hazard",
            "reg": "STPA-BPS-001 §3.1",
            "fc": "#FFEDD5",
            "ec": "#EA580C",
            "y": 0.625,
        },
        {
            "label": "UCA-001",
            "sub": "Controller does NOT provide Pump A start\nwhen waterLevel ≥ threshold  [Not Provided]",
            "stereo": "UCA",
            "reg": "STPA-BPS-002 §4.1",
            "fc": C["amber_lt"],
            "ec": C["amber"],
            "y": 0.415,
        },
        {
            "label": "UCA_ControllerMustActivatePumpA",
            "sub": "controller.responseTime_s ≤ 5.0  [SR-001 / SR-005]",
            "stereo": "requirement def",
            "reg": "BPS-REQ-005 · STPA SR-001",
            "fc": C["blue_lt"],
            "ec": C["blue"],
            "y": 0.215,
        },
        {
            "label": "BPS-REQ-005",
            "sub": "ControllerActivationTimingRequirement\nresponseTime_s ≤ 5.0 s",
            "stereo": "requirement def",
            "reg": "Requirements.sysml",
            "fc": C["teal_lt"],
            "ec": C["teal"],
            "y": 0.025,
        },
    ]

    bx, bw, bh = 0.22, 0.50, 0.155
    for node in chain:
        ny = node["y"]
        rect = FancyBboxPatch(
            (bx, ny),
            bw,
            bh,
            boxstyle="round,pad=0,rounding_size=0.015",
            linewidth=2,
            edgecolor=node["ec"],
            facecolor=node["fc"],
            zorder=3,
        )
        ax.add_patch(rect)
        # stereotype
        ax.text(
            bx + bw / 2,
            ny + bh * 0.88,
            f"«{node['stereo']}»",
            ha="center",
            va="center",
            fontsize=8,
            fontstyle="italic",
            color=node["ec"],
            zorder=4,
        )
        # main label
        ax.text(
            bx + bw / 2,
            ny + bh * 0.60,
            node["label"],
            ha="center",
            va="center",
            fontsize=10.5,
            fontweight="bold",
            color=C["navy"],
            zorder=4,
        )
        # sub
        ax.text(
            bx + bw / 2,
            ny + bh * 0.30,
            node["sub"],
            ha="center",
            va="center",
            fontsize=7.5,
            color=C["muted"],
            zorder=4,
        )
        # reg badge
        ax.text(
            bx + bw - 0.01,
            ny + 0.008,
            node["reg"],
            ha="right",
            va="bottom",
            fontsize=6.5,
            color=node["ec"],
            fontstyle="italic",
            zorder=4,
        )

    # arrows between nodes
    for i in range(len(chain) - 1):
        ay0 = chain[i]["y"]
        ay1 = chain[i + 1]["y"] + bh
        arrow(
            ax, bx + bw / 2, ay0, bx + bw / 2, ay1, color=C["navy"], lw=2, style="-|>"
        )

    # ── constraint inset (right side, linked to UCA) ──────────────────────
    cx, cy = 0.77, 0.50
    cw, ch = 0.19, 0.12
    crect = FancyBboxPatch(
        (cx, cy),
        cw,
        ch,
        boxstyle="round,pad=0,rounding_size=0.012",
        linewidth=1.5,
        linestyle=":",
        edgecolor=C["navy"],
        facecolor=C["grey_lt"],
        zorder=3,
    )
    ax.add_patch(crect)
    ax.text(
        cx + cw / 2,
        cy + ch * 0.82,
        "«constraint»",
        ha="center",
        fontsize=7.5,
        fontstyle="italic",
        color=C["muted"],
        zorder=4,
    )
    ax.text(
        cx + cw / 2,
        cy + ch * 0.52,
        "waterLevel : Real",
        ha="center",
        fontsize=8,
        color=C["navy"],
        fontfamily="monospace",
        zorder=4,
    )
    ax.text(
        cx + cw / 2,
        cy + ch * 0.22,
        "threshold : Real",
        ha="center",
        fontsize=8,
        color=C["navy"],
        fontfamily="monospace",
        zorder=4,
    )
    # dashed link to UCA node
    uca = chain[2]
    ax.plot(
        [bx + bw, cx],
        [uca["y"] + bh / 2, cy + ch / 2],
        color=C["navy"],
        lw=1,
        linestyle=":",
        zorder=5,
    )

    # ── transitionRef annotation on UCA ─────────────────────────────────
    uca_y = chain[2]["y"]
    ax.text(
        bx + bw + 0.01,
        uca_y + bh * 0.55,
        "transitionRef:\nMONITORING_to_PUMP_A_ACTIVE",
        fontsize=7,
        color=C["amber"],
        fontstyle="italic",
        va="center",
        zorder=5,
        bbox=dict(
            boxstyle="round,pad=0.2", fc=C["amber_lt"], ec=C["amber"], lw=0.8, alpha=0.9
        ),
    )

    # ── code snippet (right side, safely above bottom) ────────────────────
    code_inset(
        ax,
        0.635,
        0.38,
        [
            "#UCA {",
            "  ucaId = 'UCA-001';",
            "  guideword = 'Not Provided';",
            "  transitionRef =",
            "    'MONITORING_to_PUMP_A_ACTIVE';",
            "}",
        ],
        w=0.34,
        title="Safety.sysml",
    )

    save(fig, "diagram_5_hazard_requirement_trace.png")


# ===========================================================================
# DIAGRAM 6 — Analysis.sysml — Verification & Analysis Cases
# ===========================================================================
def diagram_6():
    fig, ax = fig_ax("6 · Verification & Analysis Cases", "Analysis.sysml")

    # ── column headers ────────────────────────────────────────────────────
    cols = [
        (0.04, 0.17, "constraint def", C["navy"], "white"),
        (0.26, 0.22, "analysis def", C["teal"], "white"),
        (0.53, 0.22, "assert requirement", C["blue"], "white"),
        (0.80, 0.16, "FMEA  (negative)", C["red"], "white"),
    ]
    for cx_, cw_, ctxt, cfc, ctc in cols:
        hb = FancyBboxPatch(
            (cx_, 0.88),
            cw_,
            0.065,
            boxstyle="round,pad=0,rounding_size=0.01",
            linewidth=0,
            facecolor=cfc,
            zorder=3,
        )
        ax.add_patch(hb)
        ax.text(
            cx_ + cw_ / 2,
            0.913,
            ctxt,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color=ctc,
            zorder=4,
        )

    # ── constraint defs ───────────────────────────────────────────────────
    cdefs = [
        ("PumpFlowPhysics", "Q_net = (Q_A+Q_B)×η×(1−λ)", 0.73),
        ("StateTransitionTiming\nPhysics", "totalTime_s ≤ maxResponseTime_s", 0.44),
    ]
    for clbl, csub, cy in cdefs:
        box(
            ax,
            0.04,
            cy,
            0.17,
            0.16,
            clbl,
            sublabel=csub,
            fc=C["bg2"],
            ec=C["navy"],
            fs=8.5,
            bold=True,
        )

    # ── analysis defs ─────────────────────────────────────────────────────
    adefs = [
        ("BilgePump\nVerification", 0.65, "nominal  (positive)"),
        ("BilgePumpTiming\nVerification", 0.40, "timing budget"),
    ]
    for albl, ay, asub in adefs:
        box(
            ax,
            0.26,
            ay,
            0.22,
            0.16,
            albl,
            sublabel=asub,
            fc=C["teal_lt"],
            ec=C["teal"],
            fs=8.5,
            bold=True,
        )

    # ── requirements ──────────────────────────────────────────────────────
    reqs = [
        ("BPS-REQ-001", "WaterLevel ≤ 0.3 m", 0.76, C["green_lt"], C["green"]),
        ("BPS-REQ-002", "PumpB.isRedundant == true", 0.63, C["green_lt"], C["green"]),
        ("BPS-REQ-003", "alarmDelay ≤ 2.0 s", 0.50, C["green_lt"], C["green"]),
        ("BPS-REQ-004", "flowA+flowB ≥ designInflow", 0.37, C["green_lt"], C["green"]),
        ("BPS-REQ-005", "responseTime_s ≤ 5.0 s", 0.24, C["green_lt"], C["green"]),
        ("BPS-REQ-006", "failoverTime_s ≤ 3.0 s", 0.11, C["green_lt"], C["green"]),
    ]
    for rid, rsub, ry, rfc, rec in reqs:
        box(
            ax,
            0.53,
            ry,
            0.22,
            0.10,
            rid,
            sublabel=rsub,
            fc=rfc,
            ec=rec,
            fs=8.5,
            bold=False,
        )
        ax.text(
            0.75 + 0.008,
            ry + 0.05,
            "✓ SATISFIED",
            fontsize=7.5,
            color=C["green"],
            va="center",
            fontweight="bold",
            zorder=5,
        )

    # ── FMEA negative tests ────────────────────────────────────────────────
    fmeas = [
        ("FM-S-001", "Sensor fail-silent", 0.65),
        ("FM-C-001", "Controller hang", 0.44),
        ("FM-C-003", "Failover not triggered", 0.23),
    ]
    for fid, fsub, fy in fmeas:
        box(
            ax,
            0.80,
            fy,
            0.18,
            0.12,
            fid,
            sublabel=fsub,
            fc=C["red_lt"],
            ec=C["red"],
            fs=8,
            bold=True,
        )
        ax.text(
            0.98 + 0.003,
            fy + 0.06,
            "✗ VIOLATED",
            fontsize=7.5,
            color=C["red"],
            va="center",
            fontweight="bold",
            zorder=5,
        )

    # ── arrows: constraint → analysis ─────────────────────────────────────
    arrow(ax, 0.21, 0.81, 0.26, 0.73, color=C["navy"], lw=1.5)
    arrow(ax, 0.21, 0.52, 0.26, 0.48, color=C["navy"], lw=1.5)

    # analysis → requirements (fan out)
    for ry in [0.81, 0.68, 0.55, 0.42]:
        arrow(ax, 0.48, 0.73, 0.53, ry, color=C["teal"], lw=1.2)
    for ry in [0.29, 0.16]:
        arrow(ax, 0.48, 0.48, 0.53, ry, color=C["teal"], lw=1.2)

    # FMEA → analysis (dashed)
    for fy, ay in [(0.71, 0.73), (0.50, 0.48)]:
        ax.annotate(
            "",
            xy=(0.48, ay),
            xytext=(0.80, fy),
            arrowprops=dict(
                arrowstyle="->", color=C["red"], lw=1.2, linestyle="dashed"
            ),
            zorder=5,
        )

    # ── code snippet ──────────────────────────────────────────────────────
    code_inset(
        ax,
        0.04,
        0.37,
        [
            "analysis def BilgePumpVerification {",
            "  subject sys : BilgePumpSystem;",
            "  assert requirement",
            "    DischargeCapacityRequirement;",
            "}",
        ],
        w=0.195,
        title="Analysis.sysml",
    )

    save(fig, "diagram_6_verification_cases.png")


# ===========================================================================
# DIAGRAM 7 — RAAML.sysml — Safety Assurance Claim Tree
# ===========================================================================
def diagram_7():
    fig, ax = fig_ax("7 · Safety Assurance Claim Tree", "RAAML.sysml")

    # ── root claim ────────────────────────────────────────────────────────
    rx, ry, rw, rh = 0.29, 0.84, 0.42, 0.11
    root = FancyBboxPatch(
        (rx, ry),
        rw,
        rh,
        boxstyle="round,pad=0,rounding_size=0.018",
        linewidth=2.5,
        edgecolor=C["navy"],
        facecolor=C["navy"],
        zorder=3,
    )
    ax.add_patch(root)
    ax.text(
        rx + rw / 2,
        ry + rh * 0.65,
        "C1 — Top-Level Safety Claim",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="white",
        zorder=4,
    )
    ax.text(
        rx + rw / 2,
        ry + rh * 0.28,
        "BilgePumpSystem is MARPOL / SOLAS compliant",
        ha="center",
        va="center",
        fontsize=8,
        color=C["teal"],
        fontstyle="italic",
        zorder=4,
    )

    # ── sub-claims ────────────────────────────────────────────────────────
    subclaims = [
        ("C1.1", "Flow\nCapacity", 0.03, C["blue"]),
        ("C1.2", "Pump\nRedundancy", 0.26, C["blue"]),
        ("C1.3", "Alarm\nTiming", 0.52, C["blue"]),
        ("C1.4", "Controller\nBehaviour", 0.76, C["blue"]),
    ]
    scw, sch = 0.18, 0.11
    sc_y = 0.66
    for sid, slbl, sx, sc_col in subclaims:
        rect = FancyBboxPatch(
            (sx, sc_y),
            scw,
            sch,
            boxstyle="round,pad=0,rounding_size=0.015",
            linewidth=2,
            edgecolor=sc_col,
            facecolor=C["blue_lt"],
            zorder=3,
        )
        ax.add_patch(rect)
        ax.text(
            sx + scw / 2,
            sc_y + sch * 0.7,
            sid,
            ha="center",
            va="center",
            fontsize=9.5,
            fontweight="bold",
            color=C["navy"],
            zorder=4,
        )
        ax.text(
            sx + scw / 2,
            sc_y + sch * 0.28,
            slbl,
            ha="center",
            va="center",
            fontsize=8,
            color=C["muted"],
            zorder=4,
        )
        # line from root
        ax.plot(
            [rx + rw / 2, sx + scw / 2],
            [ry, sc_y + sch],
            color=C["navy"],
            lw=1.5,
            zorder=2,
        )

    # ── leaf nodes: req, verification, evidence ────────────────────────────
    leaf_data = [
        # (x, y, label, sub, shape, fc, ec)
        # C1.1 Flow Capacity
        (
            0.01,
            0.44,
            "BPS-REQ-004",
            "Discharge capacity",
            "rect",
            C["green_lt"],
            C["green"],
        ),
        (
            0.01,
            0.27,
            "AnalysePump\nOutCapacity",
            "analysis def",
            "rect",
            C["teal_lt"],
            C["teal"],
        ),
        (
            0.01,
            0.10,
            "OpenFOAM\ncurves",
            "CFD evidence",
            "diamond",
            C["amber_lt"],
            C["amber"],
        ),
        # C1.2 Redundancy
        (
            0.24,
            0.44,
            "BPS-REQ-002",
            "Pump redundancy",
            "rect",
            C["green_lt"],
            C["green"],
        ),
        (
            0.24,
            0.27,
            "VerifyRedun\ndancy",
            "analysis def",
            "rect",
            C["teal_lt"],
            C["teal"],
        ),
        (
            0.24,
            0.10,
            "DNV Pt.4\nCh.6",
            "regulatory ref",
            "diamond",
            C["amber_lt"],
            C["amber"],
        ),
        # C1.3 Alarm
        (0.50, 0.44, "BPS-REQ-003", "Alarm ≤ 2 s", "rect", C["green_lt"], C["green"]),
        (
            0.50,
            0.27,
            "VerifyAlarm\nResponse",
            "analysis def",
            "rect",
            C["teal_lt"],
            C["teal"],
        ),
        (
            0.50,
            0.10,
            "IEC 60945\n§4.3",
            "standard",
            "diamond",
            C["amber_lt"],
            C["amber"],
        ),
        # C1.4 Controller behaviour
        (0.75, 0.44, "BPS-REQ-005/6", "Timing reqs", "rect", C["green_lt"], C["green"]),
        (
            0.75,
            0.27,
            "StateMachine\nBehavior",
            "state def",
            "rect",
            C["teal_lt"],
            C["teal"],
        ),
        (
            0.75,
            0.10,
            "SIM-CTRL-001",
            "Simulink model",
            "diamond",
            C["amber_lt"],
            C["amber"],
        ),
    ]

    lw2, lh2 = 0.20, 0.10
    for lx, ly, llbl, lsub, lshape, lfc, lec in leaf_data:
        if lshape == "diamond":
            # diamond for evidence
            cx_ = lx + lw2 / 2
            cy_ = ly + lh2 / 2
            hw = lw2 / 2 * 0.82
            hh = lh2 / 2
            diamond = plt.Polygon(
                [[cx_, cy_ + hh], [cx_ + hw, cy_], [cx_, cy_ - hh], [cx_ - hw, cy_]],
                closed=True,
                linewidth=1.5,
                edgecolor=lec,
                facecolor=lfc,
                zorder=3,
            )
            ax.add_patch(diamond)
            ax.text(
                cx_,
                cy_ + 0.012,
                llbl,
                ha="center",
                va="center",
                fontsize=7.5,
                fontweight="bold",
                color=C["navy"],
                zorder=4,
            )
            ax.text(
                cx_,
                cy_ - 0.025,
                lsub,
                ha="center",
                va="center",
                fontsize=6.5,
                color=C["muted"],
                fontstyle="italic",
                zorder=4,
            )
        else:
            rect = FancyBboxPatch(
                (lx, ly),
                lw2,
                lh2,
                boxstyle="round,pad=0,rounding_size=0.01",
                linewidth=1.5,
                edgecolor=lec,
                facecolor=lfc,
                zorder=3,
            )
            ax.add_patch(rect)
            ax.text(
                lx + lw2 / 2,
                ly + lh2 * 0.66,
                llbl,
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
                color=C["navy"],
                zorder=4,
            )
            ax.text(
                lx + lw2 / 2,
                ly + lh2 * 0.26,
                lsub,
                ha="center",
                va="center",
                fontsize=6.5,
                color=C["muted"],
                fontstyle="italic",
                zorder=4,
            )
        # line up to sub-claim
        sub_idx = (lx // 0.24) if lx < 0.73 else 3
        sc_idx = min(int(sub_idx), 3)
        _ = subclaims[sc_idx][2] + scw / 2
        ax.plot(
            [lx + lw2 / 2, lx + lw2 / 2],
            [ly + lh2, sc_y],
            color=C["border"],
            lw=1,
            linestyle=":",
            zorder=2,
        )

    # ── RAAML metadata def labels (bottom) ────────────────────────────────
    for i, (mname, mc) in enumerate(
        [
            ("metadata def Hazard", C["red"]),
            ("metadata def UCA", C["amber"]),
            ("metadata def FailureMode", C["navy"]),
            ("metadata def SafetyRequirement", C["blue"]),
        ]
    ):
        bx2 = 0.02 + i * 0.245
        raaml_rect = FancyBboxPatch(
            (bx2, 0.00),
            0.22,
            0.065,
            boxstyle="round,pad=0,rounding_size=0.008",
            linewidth=1,
            linestyle="--",
            edgecolor=mc,
            facecolor="white",
            zorder=3,
        )
        ax.add_patch(raaml_rect)
        ax.text(
            bx2 + 0.11,
            0.033,
            mname,
            ha="center",
            va="center",
            fontsize=7.5,
            color=mc,
            fontfamily="monospace",
            zorder=4,
        )

    ax.text(
        0.5,
        -0.025,
        "RAAML.sysml — metadata def stereotypes annotate all elements above",
        ha="center",
        va="center",
        fontsize=8,
        color=C["muted"],
        fontstyle="italic",
        zorder=4,
    )

    # ── code snippet — top-right corner, clear of all tree nodes ──────────
    # Root claim ends at x=0.71; space x=0.72..1.0 is free above sub-claims
    # 3 lines: h=0.038*(3+1.4)=0.167; y_top=0.975 → y_bottom=0.808
    # Root claim occupies y=0.84..0.95 at x=0.29..0.71 — no x overlap here
    code_inset(
        ax,
        0.72,
        0.975,
        [
            "metadata def UCA {",
            "  attribute ucaId        : String;",
            "  attribute transitionRef: String;",
            "}",
        ],
        w=0.27,
        title="RAAML.sysml",
    )

    save(fig, "diagram_7_raaml_claim_tree.png")


# ===========================================================================
# Main
# ===========================================================================
if __name__ == "__main__":
    print("Generating 7 presentation diagrams …")
    diagram_1()
    diagram_2()
    diagram_3()
    diagram_4()
    diagram_5()
    diagram_6()
    diagram_7()
    print("\nDone. All diagrams written to:", OUT_DIR)
