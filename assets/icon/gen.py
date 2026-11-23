"""Full Fat icon v9 generator: main 128 master.
Run: python3 -I gen.py (from this folder). Writes ff-icon.svg.

Model: a square-based gable-top carton in true orthographic three-quarter view
(yaw THETA, camera elevation PHI). The dot print is one staggered lattice in the
carton's *unrolled* blank coordinates (u around the perimeter, v up the panel),
mapped onto the front, side+gable and front roof panel with each face's own
affine projection, then clipped to that face. So dots run across the vertical
corner and fold from the front onto the roof, like the printed blank.
"""
import math, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# palette
IND_R, IND, IND_S = "#3b31a8", "#2e248f", "#221a6f"   # roof, front, side
WHITE, RED = "#ffffff", "#d7193a"
SIDE_DOT = "#e6e7f1"

# ---------- camera ----------
THETA = math.atan(0.55)           # side shows at 55% of the front width (square base)
PHI = math.radians(7.0)           # camera elevation
cT, sT, cP, sP = math.cos(THETA), math.sin(THETA), math.cos(PHI), math.sin(PHI)
R1 = (cT, 0.0, sT)                         # screen x
R2 = (-sT * sP, cP, cT * sP)               # screen up
R3 = (sT * cP, sP, -cT * cP)               # toward camera

# ---------- carton (world units) ----------
W = D = 29.6           # square base (-9% vs v8); screen front ~25.9, side ~14.3
H = 68.5               # body height
RISE = 8.0            # gable rise to ridge
FINH = 7.0             # fin height
FIN_T = 0.6            # half fin thickness
L = math.hypot(RISE, D / 2)     # roof panel slope length
OX, OY = 0.0, 0.0      # set below after bbox

def dot3(a, b): return sum(x * y for x, y in zip(a, b))

def P(X, Y, Z):
    p = (X, Y, Z)
    return (OX + dot3(R1, p), OY - dot3(R2, p))

def f(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s

def poly(*pts):
    return "M" + " L".join(f"{f(x)} {f(y)}" for x, y in pts) + " Z"

def norm(v):
    m = math.sqrt(sum(c * c for c in v)); return tuple(c / m for c in v)

def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

# centre the carton in the tile: compute bbox with zero offset first
def _pts():
    return [P(0, 0, 0), P(W, 0, 0), P(W, 0, D), P(0, H + RISE + FINH, D / 2),
            P(W + 0.0, H + RISE + FINH, D / 2 + FIN_T)]
_b = _pts()
_minx = min(p[0] for p in _b); _maxx = max(p[0] for p in _b)
_miny = min(p[1] for p in _b); _maxy = max(p[1] for p in _b)
OX = 64 - (_minx + _maxx) / 2 - 0.5
OY = 64.5 - (_miny + _maxy) / 2

# ---------- face maps: unrolled (u, v) -> 3D ----------
def front3(u, v): return (u, v, 0.0)
def side3(u, v): return (W, v, u - W)
def roof3(u, v):
    s = v - H
    return (u, H + s * RISE / L, s * (D / 2) / L)

def affine(map3):
    """SVG matrix for a face: (u, v) unrolled -> screen."""
    o = P(*map3(0.0, 0.0)) if map3 is not roof3 else P(*map3(0.0, H))
    if map3 is roof3:
        pu = P(*map3(1.0, H)); pv = P(*map3(0.0, H + 1.0))
        # v origin at H: translate so that matrix takes raw v
        a, b = pu[0] - o[0], pu[1] - o[1]
        c, d = pv[0] - o[0], pv[1] - o[1]
        e, g = o[0] - c * H, o[1] - d * H
        return a, b, c, d, e, g
    pu = P(*map3(1.0, 0.0)); pv = P(*map3(0.0, 1.0))
    return pu[0] - o[0], pu[1] - o[1], pv[0] - o[0], pv[1] - o[1], o[0], o[1]

def mat(m): return "matrix(" + " ".join(f"{x:.4f}" for x in m) + ")"

# key points
F0, F1, F2, F3 = P(0, 0, 0), P(W, 0, 0), P(W, H, 0), P(0, H, 0)
S1, S2 = P(W, 0, D), P(W, H, D)
RL, RR = P(0, H + RISE, D / 2), P(W, H + RISE, D / 2)

front = poly(F0, F1, F2, F3)
side = poly(F1, S1, S2, RR, F2)            # side incl. gable triangle
roof = poly(F3, F2, RR, RL)
ZF = D / 2 - FIN_T                         # fin front plane
fin = poly(P(0, H + RISE - 0.6, ZF), P(W, H + RISE - 0.6, ZF), P(W, H + RISE + FINH, ZF),
           P(0, H + RISE + FINH, ZF))
fin_end = poly(P(W, H + RISE - 0.6, ZF), P(W, H + RISE, D / 2 + FIN_T),
               P(W, H + RISE + FINH, D / 2 + FIN_T), P(W, H + RISE + FINH, ZF))

# ---------- dot lattice (unrolled blank coordinates) ----------
import sys
SMALL = "--64" in sys.argv          # 64 px master: ~5 rows, dots ~10% larger
PITCH = W / 2.5        # 13: 2.5 pitches per panel -> half dots on every vertical edge
ROWQ = 13.4 if SMALL else 10.4      # row spacing
DOT_R = 3.7 if SMALL else 3.3
V0 = 7.0 if SMALL else 5.6

def lattice(umin, umax, vmin, vmax):
    out = []
    k0 = math.floor((vmin - V0) / ROWQ) - 1
    k1 = math.ceil((vmax - V0) / ROWQ) + 1
    for k in range(k0, k1 + 1):
        v = V0 + k * ROWQ
        off = 0.0 if k % 2 == 0 else PITCH / 2   # even rows sit ON the edges (u=0, W, 2W)
        j0 = math.floor((umin - off) / PITCH) - 1
        j1 = math.ceil((umax - off) / PITCH) + 1
        for j in range(j0, j1 + 1):
            u = off + j * PITCH
            if umin - DOT_R <= u <= umax + DOT_R and vmin - DOT_R <= v <= vmax + DOT_R:
                out.append((u, v))
    return out

def dots_svg(pts, fill):
    return "".join(f'<circle cx="{f(u)}" cy="{f(v)}" r="{DOT_R}"/>' for u, v in pts)

# label on the front plane (unrolled coords)
LAB_U, LAB_V, LAB_RW = W / 2, 31.0, (12.2 if SMALL else 11.3)    # world radius -> screen ~9.9 horizontal

# ---------- FF lettering: Inter Black "F", outline converted with fontTools ----------
# Inter Black (OFL), unitsPerEm 2048, cap height 1490, advance 1196, no F-F kern pair.
# Source path: M96 0V1490H1144V1164H500V828H1080V510H500V0Z
INTER_F = [(96, 0), (96, 1490), (1144, 1490), (1144, 1164), (500, 1164), (500, 828),
           (1080, 828), (1080, 510), (500, 510), (500, 0)]
INTER_ADV, INTER_CAP = 1196, 1490
TIGHTEN = 60            # font units (~0.5 world unit at this size): the pair looked loose

def FF_svg(m, cu, cv, cap_h):
    k = cap_h / INTER_CAP
    adv = INTER_ADV - TIGHTEN
    ink0, ink1 = 96, adv + 1144
    x_shift = -(ink0 + ink1) / 2 + 25          # centre the ink, nudge right (F is open right)
    out = []
    for i in range(2):
        out.append("M" + " L".join(f"{f(cu + (x + x_shift + i * adv) * k)} {f(cv - cap_h / 2 + y * k)}"
                                   for x, y in INTER_F) + " Z")
    return f'<path transform="{mat(m)}" d="{" ".join(out)}" fill="{RED}"/>'

# ---------- cap ----------
CAP_U, CAP_S = W * 0.50, L * 0.45      # centred across the front roof panel
CAP_R, CAP_H = 4.6, 3.3
ROOF_N = norm((0.0, D / 2, -RISE))

def ring(C, e1, e2, r, n=96):
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        out.append(P(*[C[j] + r * (math.cos(t) * e1[j] + math.sin(t) * e2[j]) for j in range(3)]))
    return out

def hull(pts):
    pts = sorted(set((round(x, 3), round(y, 3)) for x, y in pts))
    def cr(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]

def cap_svg():
    base = roof3(CAP_U, H + CAP_S)
    ax = ROOF_N
    e1 = (1.0, 0.0, 0.0)
    e2 = norm(cross(ax, e1))
    top = tuple(b + CAP_H * a for b, a in zip(base, ax))
    bot = ring(base, e1, e2, CAP_R)
    tp = ring(top, e1, e2, CAP_R)
    body = hull(bot + tp)
    xs = [p[0] for p in body]
    x0, x1 = min(xs), max(xs)
    # contact shadow: crisp ellipse on the roof plane, nudged right/down-slope (light from left)
    shc = roof3(CAP_U + 1.1, H + CAP_S - 0.5)
    sh = ring(shc, e1, norm(cross(ROOF_N, e1)), CAP_R + 0.7)
    inner = ring(tuple(t + 0.02 * a for t, a in zip(top, ax)), e1, e2, CAP_R * 0.76)
    rx = (max(p[0] for p in tp) - min(p[0] for p in tp)) / 2
    ry = (max(p[1] for p in tp) - min(p[1] for p in tp)) / 2
    print(f"cap top ellipse rx={rx:.2f} ry={ry:.2f}")
    s = [f'<linearGradient id="capside" gradientUnits="userSpaceOnUse" x1="{f(x0)}" y1="0" x2="{f(x1)}" y2="0">'
         '<stop offset="0" stop-color="#a7abc0"/><stop offset=".18" stop-color="#c3c6d6"/>'
         '<stop offset=".55" stop-color="#e4e6ee"/><stop offset="1" stop-color="#cfd2df"/></linearGradient>',
         f'<path d="{poly(*sh)}" fill="#0d0838" opacity=".3"/>',
         f'<path d="{poly(*body)}" fill="url(#capside)"/>',
         f'<path d="{poly(*tp)}" fill="#ffffff"/>',
         f'<path d="{poly(*inner)}" fill="none" stroke="#dfe1ea" stroke-width=".5"/>']
    return s[0], "".join(s[1:])

# ---------- tile ----------
def squircle(cx, cy, a, n=5.0, steps=192):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + a * math.copysign(abs(c) ** (2 / n), c),
                    cy + a * math.copysign(abs(s) ** (2 / n), s)))
    return poly(*pts)

def main_svg():
    tile = squircle(64, 63, 51.5)
    mF, mS, mR = affine(front3), affine(side3), affine(roof3)
    front_pts = []
    for u, v in lattice(0, W, 0, H):
        vis = math.hypot(u - LAB_U, v - LAB_V) + DOT_R - (LAB_RW + 1.5)
        if 0 < vis < 2.4:      # would leave a thin crescent beside the label ring
            continue
        front_pts.append((u, v))
    side_pts = lattice(W, 2 * W, 0, H + RISE)
    roof_pts = [(u, v) for u, v in lattice(0, W, H, H + L)
                if math.hypot(u - CAP_U, v - (H + CAP_S)) > CAP_R + DOT_R + 1.6]   # keep the cap clear
    lab_c = P(*front3(LAB_U, LAB_V))
    capgrad, cap = cap_svg()
    seam_y = H + RISE + FINH * 0.30
    sa, sb = P(0.3, seam_y, ZF), P(W, seam_y, ZF)
    ft_a, ft_b = P(0, H + RISE + FINH - .35, ZF), P(W, H + RISE + FINH - .35, ZF)
    foot = P(W / 2, 0, D / 2)
    side_top = RR[1]; side_bot = F1[1]
    hl_a, hl_b = P(0, H, 0), P(0, 0, 0)
    defs = f'''<defs>
<linearGradient id="tile" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#eceef2"/></linearGradient>
<linearGradient id="sideshade" gradientUnits="userSpaceOnUse" x1="0" y1="{f(side_top)}" x2="0" y2="{f(side_bot)}"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".1"/></linearGradient>
<linearGradient id="frontshade" gradientUnits="userSpaceOnUse" x1="0" y1="{f(F3[1])}" x2="0" y2="{f(F1[1])}"><stop offset="0" stop-color="#fff" stop-opacity=".035"/><stop offset="1" stop-color="#000" stop-opacity=".07"/></linearGradient>
{capgrad}
<linearGradient id="frontbulge" gradientUnits="userSpaceOnUse" x1="{f(F0[0])}" y1="0" x2="{f(F1[0])}" y2="0"><stop offset="0" stop-color="#000" stop-opacity=".06"/><stop offset=".55" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".07"/></linearGradient>
<linearGradient id="sidebulge" gradientUnits="userSpaceOnUse" x1="{f(F1[0])}" y1="0" x2="{f(S1[0])}" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".03"/><stop offset="1" stop-color="#000" stop-opacity=".16"/></linearGradient>
<filter id="finsh" x="-10%" y="-40%" width="120%" height="180%"><feGaussianBlur stdDeviation=".5"/></filter>
<filter id="tsh1" x="-20%" y="-20%" width="140%" height="150%"><feGaussianBlur stdDeviation="2.2"/></filter>
<filter id="tsh2" x="-10%" y="-10%" width="120%" height="125%"><feGaussianBlur stdDeviation=".55"/></filter>
<filter id="floor" x="-30%" y="-200%" width="160%" height="500%"><feGaussianBlur stdDeviation="1.3"/></filter>
<clipPath id="frontclip"><path d="{front}"/></clipPath>
<clipPath id="sideclip"><path d="{side}"/></clipPath>
<clipPath id="roofclip"><path d="{roof}"/></clipPath>
</defs>'''
    body = f'''
<path d="{tile}" fill="#0a1222" opacity=".22" transform="translate(0 2.2)" filter="url(#tsh1)"/>
<path d="{tile}" fill="#0a1222" opacity=".18" transform="translate(0 .5)" filter="url(#tsh2)"/>
<path d="{tile}" fill="url(#tile)"/>
<path d="{tile}" fill="none" stroke="#d3d7e0" stroke-width=".5" transform="translate(64 63) scale(.9951) translate(-64 -63)"/>
<ellipse cx="{f(foot[0] + 1.5)}" cy="{f(F1[1] - 2.0)}" rx="19" ry="3.4" fill="#141a3a" opacity=".3" filter="url(#floor)"/>
<path d="{side}" fill="{IND_S}"/>
<g clip-path="url(#sideclip)"><g transform="{mat(mS)}" fill="{SIDE_DOT}">{dots_svg(side_pts, SIDE_DOT)}</g><path d="{side}" fill="url(#sideshade)"/><path d="{side}" fill="url(#sidebulge)"/></g>
<path d="{roof}" fill="{IND_R}"/>
<g clip-path="url(#roofclip)"><g transform="{mat(mR)}" fill="{WHITE}">{dots_svg(roof_pts, WHITE)}</g></g>
<path d="{front}" fill="{IND}"/>
<g clip-path="url(#frontclip)"><g transform="{mat(mF)}" fill="{WHITE}">{dots_svg(front_pts, WHITE)}</g>
<circle transform="{mat(mF)}" cx="{f(LAB_U)}" cy="{f(LAB_V)}" r="{LAB_RW + 1.5}" fill="{IND}"/><path d="{front}" fill="url(#frontshade)"/><path d="{front}" fill="url(#frontbulge)"/>
<path d="M{f(hl_a[0] + .45)} {f(hl_a[1])} L{f(hl_b[0] + .45)} {f(hl_b[1])}" stroke="#ffffff" stroke-width=".9" opacity=".3"/></g>
<circle transform="{mat(mF)}" cx="{f(LAB_U)}" cy="{f(LAB_V)}" r="{LAB_RW}" fill="{WHITE}"/>
{FF_svg(mF, LAB_U, LAB_V, 0.40 * 2 * LAB_RW)}
<path d="M{f(F2[0] - .4)} {f(F2[1])} L{f(F1[0] - .4)} {f(F1[1])}" stroke="#fff" stroke-width=".8" opacity=".25"/>
<path d="{fin}" fill="#0a1222" opacity=".16" transform="translate(.3 -.2)" filter="url(#finsh)"/>
<path d="{fin}" fill="#ffffff"/>
<path d="{fin_end}" fill="#d9dbe6"/>
<path d="M{f(ft_a[0])} {f(ft_a[1])} L{f(ft_b[0])} {f(ft_b[1])}" stroke="#ffffff" stroke-width=".7"/>
<path d="M{f(sa[0])} {f(sa[1])} L{f(sb[0])} {f(sb[1])}" stroke="#b9bdcc" stroke-width=".5"/>
{cap}
'''
    print("ratio", f((_maxx-_minx)/(_maxy-_miny)), "front w", f(F1[0] - F0[0]), "side w", f(S1[0] - F1[0]),
          "front drop", f(F1[1] - F0[1]), "side rise", f(F1[1] - S1[1]),
          "bbox x", f(_minx + OX), f(_maxx + OX), "y", f(_miny + OY), f(_maxy + OY))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">{defs}{body}</svg>\n'

if __name__ == "__main__":
    open("ff-icon-64.svg" if SMALL else "ff-icon.svg", "w").write(main_svg())
    print("ok")
