"""
Generates the Minesweeper.git social preview + README banner.
Output: SVG source files + rendered PNGs.
"""
from pathlib import Path
import cairosvg

OUT = Path("/home/claude/out")
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Shared palette (GitHub dark + contribution graph + classic minesweeper nums)
# ---------------------------------------------------------------------------
BG_DARK   = "#0d1117"
BG_DARKER = "#010409"
SURFACE   = "#161b22"
BORDER    = "#30363d"
TEXT_HI   = "#f0f6fc"
TEXT_MD   = "#c9d1d9"
TEXT_LO   = "#8b949e"

# contribution graph greens (darkest -> brightest)
CONTRIB = ["#0e4429", "#006d32", "#26a641", "#39d353"]

# number colors (GitHub-adapted minesweeper palette)
NUM_COLORS = {
    1: "#58a6ff",  # blue
    2: "#7ee787",  # green
    3: "#ff7b72",  # red
    4: "#d2a8ff",  # purple
    5: "#ffa657",  # orange
    6: "#79c0ff",  # cyan
    7: "#f0f6fc",  # white
    8: "#8b949e",  # gray
}

REVEAL_BG = "#1c2128"
REVEAL_BD = "#262c36"
MINE_BG   = "#3d1416"
MINE_BD   = "#f85149"

# ---------------------------------------------------------------------------
# Reusable icon definitions
# ---------------------------------------------------------------------------
DEFS = f"""
<defs>
  <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{BG_DARK}"/>
    <stop offset="1" stop-color="{BG_DARKER}"/>
  </linearGradient>

  <radialGradient id="glow" cx="0.3" cy="0.3" r="0.9">
    <stop offset="0" stop-color="#39d353" stop-opacity="0.08"/>
    <stop offset="1" stop-color="#39d353" stop-opacity="0"/>
  </radialGradient>

  <pattern id="dots" x="0" y="0" width="36" height="36" patternUnits="userSpaceOnUse">
    <circle cx="1" cy="1" r="1" fill="#30363d" opacity="0.35"/>
  </pattern>

  <filter id="cellShadow" x="-30%" y="-30%" width="160%" height="160%">
    <feDropShadow dx="0" dy="1.5" stdDeviation="1" flood-color="#000" flood-opacity="0.35"/>
  </filter>

  <!-- Classic spiked bomb, 40x40 viewbox centered -->
  <symbol id="bomb" viewBox="-20 -20 40 40" overflow="visible">
    <g fill="#0d1117">
      <rect x="-1.8" y="-15" width="3.6" height="5" rx="0.5"/>
      <rect x="-1.8" y="10" width="3.6" height="5" rx="0.5"/>
      <rect x="-15" y="-1.8" width="5" height="3.6" rx="0.5"/>
      <rect x="10" y="-1.8" width="5" height="3.6" rx="0.5"/>
      <g transform="rotate(45)">
        <rect x="-1.8" y="-14" width="3.6" height="4.5" rx="0.5"/>
        <rect x="-1.8" y="9.5" width="3.6" height="4.5" rx="0.5"/>
        <rect x="-14" y="-1.8" width="4.5" height="3.6" rx="0.5"/>
        <rect x="9.5" y="-1.8" width="4.5" height="3.6" rx="0.5"/>
      </g>
    </g>
    <circle cx="0" cy="0" r="9.5" fill="#0d1117" stroke="#484f58" stroke-width="0.6"/>
    <circle cx="-3" cy="-3" r="2.3" fill="#484f58"/>
    <circle cx="-3.5" cy="-3.5" r="1" fill="#8b949e"/>
    <path d="M 6.5,-6.5 Q 10,-10 12,-13" stroke="#8b949e" stroke-width="1.6"
          fill="none" stroke-linecap="round"/>
    <circle cx="13" cy="-14" r="3" fill="#f85149"/>
    <circle cx="13" cy="-14" r="1.5" fill="#ffa657"/>
    <circle cx="13" cy="-14" r="0.6" fill="#f0f6fc"/>
  </symbol>

  <!-- Lighter bomb for use on dark backgrounds (legend) -->
  <symbol id="bomb-light" viewBox="-20 -20 40 40" overflow="visible">
    <g fill="#8b949e">
      <rect x="-1.8" y="-15" width="3.6" height="5" rx="0.5"/>
      <rect x="-1.8" y="10" width="3.6" height="5" rx="0.5"/>
      <rect x="-15" y="-1.8" width="5" height="3.6" rx="0.5"/>
      <rect x="10" y="-1.8" width="5" height="3.6" rx="0.5"/>
      <g transform="rotate(45)">
        <rect x="-1.8" y="-14" width="3.6" height="4.5" rx="0.5"/>
        <rect x="-1.8" y="9.5" width="3.6" height="4.5" rx="0.5"/>
        <rect x="-14" y="-1.8" width="4.5" height="3.6" rx="0.5"/>
        <rect x="9.5" y="-1.8" width="4.5" height="3.6" rx="0.5"/>
      </g>
    </g>
    <circle cx="0" cy="0" r="9.5" fill="#30363d" stroke="#8b949e" stroke-width="0.8"/>
    <circle cx="-3" cy="-3" r="2.3" fill="#8b949e"/>
    <circle cx="-3.5" cy="-3.5" r="1" fill="#c9d1d9"/>
    <path d="M 6.5,-6.5 Q 10,-10 12,-13" stroke="#c9d1d9" stroke-width="1.6"
          fill="none" stroke-linecap="round"/>
    <circle cx="13" cy="-14" r="3" fill="#f85149"/>
    <circle cx="13" cy="-14" r="1.5" fill="#ffa657"/>
    <circle cx="13" cy="-14" r="0.6" fill="#f0f6fc"/>
  </symbol>

  <!-- Flag icon, 30x36 viewbox centered -->
  <symbol id="flag" viewBox="-15 -18 30 36" overflow="visible">
    <rect x="-0.9" y="-14" width="1.8" height="28" fill="#c9d1d9"/>
    <rect x="-6" y="11" width="13" height="2" rx="0.5" fill="#8b949e"/>
    <rect x="-7" y="13" width="15" height="2.5" rx="0.5" fill="#8b949e"/>
    <path d="M 1,-14 L 12,-7 L 1,0 Z" fill="#f85149"/>
    <path d="M 1,-14 L 12,-7 L 1,-12 Z" fill="#ff7b72" opacity="0.6"/>
  </symbol>
</defs>
"""

# ---------------------------------------------------------------------------
# Board grid rendering
# ---------------------------------------------------------------------------
# Cell codes:
#   h1/h2/h3/h4 = hidden (contribution green intensity 1..4)
#   _           = revealed blank (no adjacent mines)
#   1..8        = revealed numbered
#   F1..F4      = flagged (the N is the underlying hidden intensity)
#   *           = revealed mine (exploded)

def cell_svg(code: str, x: int, y: int, size: int = 50) -> str:
    r = 5  # corner radius
    # --- hidden cells (green) ---
    if code.startswith("h"):
        lvl = int(code[1]) - 1
        fill = CONTRIB[lvl]
        return (
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" '
            f'fill="{fill}" stroke="#000" stroke-opacity="0.25" stroke-width="0.5"/>'
        )
    # --- flagged cell (hidden + flag) ---
    if code.startswith("F"):
        lvl = int(code[1]) - 1
        fill = CONTRIB[lvl]
        flag_size = int(size * 0.62)
        fx = x + size / 2
        fy = y + size / 2
        return (
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" '
            f'fill="{fill}" stroke="#000" stroke-opacity="0.25" stroke-width="0.5"/>'
            f'<use href="#flag" x="{fx - flag_size/2}" y="{fy - flag_size/2}" '
            f'width="{flag_size}" height="{flag_size}"/>'
        )
    # --- revealed blank ---
    if code == "_":
        return (
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" '
            f'fill="{REVEAL_BG}" stroke="{REVEAL_BD}" stroke-width="1"/>'
        )
    # --- revealed mine (exploded) ---
    if code == "*":
        bomb_size = int(size * 0.7)
        cx = x + size / 2
        cy = y + size / 2
        return (
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" '
            f'fill="{MINE_BG}" stroke="{MINE_BD}" stroke-width="1.5"/>'
            f'<use href="#bomb" x="{cx - bomb_size/2}" y="{cy - bomb_size/2}" '
            f'width="{bomb_size}" height="{bomb_size}"/>'
        )
    # --- revealed number ---
    if code.isdigit():
        n = int(code)
        color = NUM_COLORS[n]
        fs = int(size * 0.56)
        cx = x + size / 2
        cy = y + size / 2 + fs * 0.35  # baseline adjust
        return (
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" '
            f'fill="{REVEAL_BG}" stroke="{REVEAL_BD}" stroke-width="1"/>'
            f'<text x="{cx}" y="{cy}" text-anchor="middle" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'font-weight="800" font-size="{fs}" fill="{color}">{n}</text>'
        )
    raise ValueError(f"Unknown cell code: {code}")


def board_svg(grid, x0: int, y0: int, cell: int = 50, gap: int = 4) -> str:
    parts = []
    for r, row in enumerate(grid):
        for c, code in enumerate(row):
            if code is None:
                continue
            x = x0 + c * (cell + gap)
            y = y0 + r * (cell + gap)
            parts.append(cell_svg(code, x, y, cell))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Grid layouts
# ---------------------------------------------------------------------------
# A plausible mid-game minesweeper state using varied contribution-cell shades.
# Designed so that flags + numbers cluster and feel like a real play-through.
SOCIAL_GRID = [
    ["h2","h3","h1","h2","h2","F1","h1","h3","h2","h4"],
    ["h1","h2","h2","1", "2", "h4","h1","h2","F2","h1"],
    ["h3","h2","1", "_", "1", "h2","h1","1", "2", "h3"],
    ["h2","h1","2", "_", "2", "h3","1", "_", "2", "h2"],
    ["h4","F3","1", "1", "1", "1", "F1","1", "_", "h1"],
    ["h1","2", "_", "_", "_", "_", "1", "1", "_", "h2"],
    ["h2","h1","h2","h3","h4","h1","h2","h2","h3","h2"],
    ["h3","h2","h1","h2","h2","h1","h3","*", "h1","h4"],
]

# Banner grid — wider, shorter. 18 cols × 4 rows.
BANNER_GRID = [
    ["h2","h3","h1","h2","F2","h3","h2","h1","h3","h4","h2","h1","h2","h3","h1","h2","h4","h1"],
    ["h1","h2","1", "2", "h3","h2","1", "2", "F1","h2","h1","h3","2", "F3","1", "h1","h2","h3"],
    ["h3","h2","1", "_", "1", "1", "_", "1", "2", "h4","h2","h1","1", "_", "1", "h2","h4","h1"],
    ["h2","h1","h3","h2","h4","h1","h2","*", "h2","h3","h1","h2","h3","h2","h1","F1","h2","h3"],
]


# ---------------------------------------------------------------------------
# Social preview (1280 x 640) — GitHub's standard
# ---------------------------------------------------------------------------
def build_social() -> str:
    W, H = 1280, 640
    cell = 50
    gap = 5
    cols, rows = 10, 8
    board_w = cols * cell + (cols - 1) * gap
    board_h = rows * cell + (rows - 1) * gap
    # Right panel: x=620..1200 (580 wide), y=80..560 (480 tall)
    bx = 620 + (580 - board_w) // 2
    by = 80 + (480 - board_h) // 2

    # Left content anchor
    lx = 80

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
{DEFS}
  <!-- background -->
  <rect width="{W}" height="{H}" fill="url(#bgGrad)"/>
  <rect width="{W}" height="{H}" fill="url(#dots)"/>
  <rect width="{W}" height="{H}" fill="url(#glow)"/>

  <!-- subtle corner accents -->
  <g stroke="{BORDER}" stroke-width="1" fill="none" opacity="0.55">
    <path d="M 24,24 L 24,64 M 24,24 L 64,24"/>
    <path d="M {W-24},24 L {W-24},64 M {W-24},24 L {W-64},24"/>
    <path d="M 24,{H-24} L 24,{H-64} M 24,{H-24} L 64,{H-24}"/>
    <path d="M {W-24},{H-24} L {W-24},{H-64} M {W-24},{H-24} L {W-64},{H-24}"/>
  </g>

  <!-- LEFT: title block -->
  <g transform="translate({lx}, 220)">
    <!-- terminal command hint -->
    <text font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="16">
      <tspan fill="{TEXT_LO}">~/projects</tspan><tspan dx="10" fill="#7ee787">❯</tspan><tspan dx="8" fill="{TEXT_MD}">gh repo clone</tspan><tspan dx="8" fill="#58a6ff" font-weight="600">github-minesweeper</tspan>
    </text>

    <!-- title -->
    <text y="100" font-family="ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
          font-weight="900" font-size="68" fill="{TEXT_HI}" letter-spacing="-2.5">Minesweeper</text>

    <!-- tagline -->
    <text y="144" font-family="ui-sans-serif, -apple-system, system-ui, sans-serif"
          font-size="20" fill="{TEXT_LO}">
      The classic game, now a GitHub repo.
    </text>
  </g>

  <!-- bottom-left: flag → green swatches → bomb -->
  <g transform="translate({lx}, {H-100})">
    <use href="#flag" x="-16" y="-18" width="52" height="64"/>
    <g transform="translate(50, 6)">
      <rect width="42" height="42" rx="7" fill="{CONTRIB[0]}"/>
      <rect x="50" width="42" height="42" rx="7" fill="{CONTRIB[1]}"/>
      <rect x="100" width="42" height="42" rx="7" fill="{CONTRIB[2]}"/>
      <rect x="150" width="42" height="42" rx="7" fill="{CONTRIB[3]}"/>
    </g>
    <use href="#bomb-light" x="256" y="-6" width="56" height="56"/>
  </g>

  <!-- bottom-right commit hash flourish, right-aligned to board -->
  <g transform="translate({bx + cols*(cell+gap) - gap}, {H-68})" font-family="ui-monospace, monospace" font-size="20"
     fill="{TEXT_LO}" text-anchor="end">
    <circle cx="-340" cy="-4" r="7" fill="none" stroke="#7ee787" stroke-width="2"/>
    <text x="-318" y="3" fill="{TEXT_MD}" text-anchor="start">main</text>
    <text x="-254" y="3" fill="{TEXT_LO}" text-anchor="start">·</text>
    <text x="-236" y="3" fill="#d2a8ff" text-anchor="start">a1b7c3f</text>
    <text x="0" y="3" fill="{TEXT_LO}">swept 31 cells</text>
  </g>

  <!-- RIGHT: minesweeper board -->
  <g filter="url(#cellShadow)">
    {board_svg(SOCIAL_GRID, bx, by, cell=cell, gap=gap)}
  </g>

  <!-- cursor indicator hovering at the edge of a hidden cell -->
  <g transform="translate({bx + 7*(cell+gap) + 38}, {by + 0*(cell+gap) + 28})">
    <path d="M 0,0 L 0,18 L 5,13 L 8,20 L 11,19 L 8,12 L 14,12 Z"
          fill="{TEXT_HI}" stroke="{BG_DARK}" stroke-width="1.4" stroke-linejoin="round"/>
  </g>
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# README banner (1280 x 320)
# ---------------------------------------------------------------------------
def build_banner() -> str:
    W, H = 1280, 320
    cell = 40
    gap = 4
    cols, rows = 10, 4
    board_w = cols * cell + (cols - 1) * gap   # 436
    board_h = rows * cell + (rows - 1) * gap   # 172

    # Right-side board, vertically centered.
    bx = W - board_w - 60
    by = (H - board_h) // 2

    # Tight 4-row layout for the banner grid
    banner_grid = [
        ["h2","h3","h1","h2","F2","h3","h2","h1","h3","h4"],
        ["h1","h2","1", "2", "h3","h2","1", "F1","h2","h1"],
        ["h3","h2","1", "_", "1", "1", "_", "1", "2", "h4"],
        ["h2","h1","h3","h2","h4","h1","h2","*", "h2","h3"],
    ]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
{DEFS}
  <rect width="{W}" height="{H}" fill="url(#bgGrad)"/>
  <rect width="{W}" height="{H}" fill="url(#dots)"/>

  <!-- corner accents -->
  <g stroke="{BORDER}" stroke-width="1" fill="none" opacity="0.5">
    <path d="M 20,20 L 20,52 M 20,20 L 52,20"/>
    <path d="M {W-20},20 L {W-20},52 M {W-20},20 L {W-52},20"/>
    <path d="M 20,{H-20} L 20,{H-52} M 20,{H-20} L 52,{H-20}"/>
    <path d="M {W-20},{H-20} L {W-20},{H-52} M {W-20},{H-20} L {W-52},{H-20}"/>
  </g>

  <!-- LEFT: title -->
  <g transform="translate(60, 136)">
    <text y="-82" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="14">
      <tspan fill="{TEXT_LO}">~/projects</tspan><tspan dx="10" fill="#7ee787">❯</tspan><tspan dx="7" fill="{TEXT_MD}">gh repo clone</tspan><tspan dx="7" fill="#58a6ff" font-weight="600">github-minesweeper</tspan>
    </text>
    <text font-family="ui-sans-serif, -apple-system, 'Segoe UI', sans-serif"
          font-weight="900" font-size="80" fill="{TEXT_HI}" letter-spacing="-3">Minesweeper</text>
    <text y="36" font-family="ui-sans-serif, system-ui, sans-serif"
          font-size="17" fill="{TEXT_LO}">
      The classic game, now a GitHub repo.
    </text>

    <!-- feature pills -->
    <g transform="translate(0, 64)" font-family="ui-monospace, monospace" font-size="12">
      <g>
        <rect width="130" height="28" rx="14" fill="{SURFACE}" stroke="{BORDER}"/>
        <circle cx="16" cy="14" r="3.5" fill="#58a6ff"/>
        <text x="28" y="18" fill="{TEXT_MD}">start a game</text>
      </g>
      <g transform="translate(140, 0)">
        <rect width="152" height="28" rx="14" fill="{SURFACE}" stroke="{BORDER}"/>
        <circle cx="16" cy="14" r="3.5" fill="#f85149"/>
        <text x="28" y="18" fill="{TEXT_MD}">avoid the bombs</text>
      </g>
      <g transform="translate(302, 0)">
        <rect width="152" height="28" rx="14" fill="{SURFACE}" stroke="{BORDER}"/>
        <circle cx="16" cy="14" r="3.5" fill="#7ee787"/>
        <text x="28" y="18" fill="{TEXT_MD}">sweep the board</text>
      </g>
    </g>

  </g>

  <!-- RIGHT: board -->
  <g filter="url(#cellShadow)">
    {board_svg(banner_grid, bx, by, cell=cell, gap=gap)}
  </g>

  <!-- cursor hovering over a cell -->
  <g transform="translate({bx + 6*(cell+gap) + 30}, {by + 0*(cell+gap) + 22})">
    <path d="M 0,0 L 0,16 L 4,12 L 7,18 L 10,17 L 7,11 L 12,11 Z"
          fill="{TEXT_HI}" stroke="{BG_DARK}" stroke-width="1.2" stroke-linejoin="round"/>
  </g>
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# Build + render
# ---------------------------------------------------------------------------
def write(name: str, svg: str):
    svg_path = OUT / f"{name}.svg"
    png_path = OUT / f"{name}.png"
    svg_path.write_text(svg)
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(png_path),
                     output_width=int(svg.split('width="')[1].split('"')[0]) * 2)  # 2x for crisp
    print(f"wrote {svg_path}  ({svg_path.stat().st_size:,} B)")
    print(f"wrote {png_path}  ({png_path.stat().st_size:,} B)")


if __name__ == "__main__":
    write("minesweeper-social-preview", build_social())
    write("minesweeper-banner", build_banner())
