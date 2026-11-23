"""Full Fat icon v9: hand-hinted 32 px and 16 px masters (64 px master comes from gen.py --64).
Run: python3 -I gen_small.py (from this folder). Writes ff-icon-32.svg, ff-icon-16.svg.
Vertical edges sit on whole pixels; the dot print reuses the main master's unrolled
lattice, mapped through each snapped face, and is then curated by hand.
"""
import math, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

IND_R, IND, IND_S = "#3b31a8", "#2e248f", "#221a6f"
RED = "#d7193a"

def f(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s

def poly(*pts):
    return "M" + " L".join(f"{f(x)} {f(y)}" for x, y in pts) + " Z"

def squircle(cx, cy, a, n=5.0, steps=128):
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + a * math.copysign(abs(c) ** (2 / n), c),
                    cy + a * math.copysign(abs(s) ** (2 / n), s)))
    return poly(*pts)

def face_map(o, pu, pv):
    """affine from unit square (u in 0..1 along, v in 0..1 up) given 3 snapped corners"""
    return lambda u, v: (o[0] + u * (pu[0] - o[0]) + v * (pv[0] - o[0]),
                         o[1] + u * (pu[1] - o[1]) + v * (pv[1] - o[1]))

def ell(m, u, v, ru, rv, fill, n=24):
    pts = [m(u + ru * math.cos(2 * math.pi * i / n), v + rv * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return f'<path d="{poly(*pts)}" fill="{fill}"/>'

def wrap(size, defs, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
            f'<defs><linearGradient id="tile" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/>'
            f'<stop offset="1" stop-color="#eaecf0"/></linearGradient>{defs}</defs>{body}</svg>\n')

# ---------------- 32 px ----------------
def m32():
    t = squircle(16, 15.5, 13.5)
    tin = squircle(16, 15.5, 13.25)
    # carton 11 x 23 px: front x 10..17, side 17..21 (4/7 of the front), body 2.6:1
    FL_B, FC_B, SR_B = (10, 27), (17, 28), (21, 27)
    FL_T, FC_T, SR_T = (10, 9), (17, 10), (21, 9)
    RL, RR = (12, 7), (19, 7.3)
    front = poly(FL_B, FC_B, FC_T, FL_T)
    side = poly(FC_B, SR_B, SR_T, RR, FC_T)
    roof = poly(FL_T, FC_T, RR, RL)
    fin = poly((12, 7.2), (19, 7.5), (19, 5), (12, 5))            # white body
    fin_edge = "M12 5 H19 V6 H12 Z"                               # 1 px #8f95b0 top edge
    fin_end = poly((19, 7.5), (19.6, 7.3), (19.6, 5), (19, 5))
    LC, LR = (13.5, 18.5), 3.0                                      # label; moat +0.5
    # whole dots on .5-px centres, fully inside their face (lattice pitch 4, rows ~4.3)
    front_dots = [(11.5, 12.5), (15.5, 12.5), (13.5, 24.5)]
    side_dots = [(19.5, 13.5), (18.5, 18.5), (19.5, 23.5)]
    dot = lambda pts, fill: "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="1.2" fill="{fill}"/>' for x, y in pts)
    F = "M12 16 H15.5 V17 H14 V18 H15 V19 H14 V21 H12 Z"           # 2 px stem, 1 px bars
    cap_c = (14.5, 8.6)                 # centred on the front roof panel
    body = f"""<path d="{t}" fill="#0a1222" opacity=".25" transform="translate(0 .8)" filter="url(#ts)"/>
<path d="{t}" fill="url(#tile)"/>
<path d="{tin}" fill="none" stroke="#d3d7e0" stroke-width=".5"/>
<ellipse cx="15.6" cy="27.5" rx="5.6" ry="1" fill="#141a3a" opacity=".28" filter="url(#fl)"/>
<path d="{side}" fill="{IND_S}"/>
<path d="{roof}" fill="{IND_R}"/>
<path d="{front}" fill="{IND}"/>
{dot(front_dots, "#fff")}{dot(side_dots, "#e6e7f1")}
<path d="{side}" fill="url(#sb)"/>
<path d="M16.6 10 V28" stroke="#fff" stroke-width=".8" opacity=".25"/>
<circle cx="{LC[0]}" cy="{LC[1]}" r="{LR}" fill="#fff"/>
<path d="{F}" fill="{RED}"/>
<path d="{fin}" fill="#fff"/>
<path d="{fin_edge}" fill="#8f95b0"/>
<path d="{fin_end}" fill="#8f95b0"/>
<ellipse cx="{f(cap_c[0] + .3)}" cy="{f(cap_c[1] + .2)}" rx="1.8" ry=".8" fill="#0d0838" opacity=".3"/>
<path d="M{f(cap_c[0]-1.6)} {f(cap_c[1])} V{f(cap_c[1]-.9)} H{f(cap_c[0]+1.6)} V{f(cap_c[1])} A1.6 .7 0 0 1 {f(cap_c[0]-1.6)} {f(cap_c[1])} Z" fill="url(#cs32)"/>
<ellipse cx="{f(cap_c[0])}" cy="{f(cap_c[1]-.9)}" rx="1.6" ry=".7" fill="#fff"/>"""
    defs = (f'<linearGradient id="cs32" gradientUnits="userSpaceOnUse" x1="{f(cap_c[0]-1.6)}" y1="0" x2="{f(cap_c[0]+1.6)}" y2="0">'
            '<stop offset="0" stop-color="#a7abc0"/><stop offset=".55" stop-color="#e2e4ec"/><stop offset="1" stop-color="#cfd2df"/></linearGradient>'
            '<linearGradient id="sb" gradientUnits="userSpaceOnUse" x1="17" y1="0" x2="21" y2="0"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".16"/></linearGradient>'
            '<filter id="ts" x="-10%" y="-10%" width="120%" height="130%"><feGaussianBlur stdDeviation=".6"/></filter>'
            '<filter id="fl" x="-20%" y="-100%" width="140%" height="300%"><feGaussianBlur stdDeviation=".5"/></filter>')
    return wrap(32, defs, body)

# ---------------- 16 px ----------------
def m16():
    t = squircle(8, 7.75, 6.9)
    tin = squircle(8, 7.75, 6.65)
    # near-front view: front 5 px, side 2 px; roof panel band + side gable triangle
    front = poly((4, 14), (9, 14), (9, 6), (4, 6))
    side = poly((9, 14), (11, 13.5), (11, 6), (10, 4), (9, 6))
    roof = poly((4, 6), (9, 6), (10, 4), (5, 4))
    body = f"""<path d="{t}" fill="#0a1222" opacity=".28" transform="translate(0 .6)"/>
<path d="{t}" fill="url(#tile)"/>
<path d="{tin}" fill="none" stroke="#d3d7e0" stroke-width=".5"/>
<path d="M5 14.4 H11" stroke="#141a3a" stroke-width=".6" opacity=".22"/>
<path d="{side}" fill="{IND_S}"/>
<path d="{roof}" fill="{IND_R}"/>
<path d="{front}" fill="{IND}"/>
<rect x="10" y="8" width="1" height="1" fill="#e6e7f1"/>
<rect x="10" y="11" width="1" height="1" fill="#e6e7f1"/>
<rect x="5" y="2" width="5" height="1" fill="#8f95b0"/>
<rect x="5" y="3" width="4" height="1" fill="#fff"/>
<rect x="9" y="3" width="1" height="1" fill="#8f95b0"/>
<circle cx="6.5" cy="11" r="2.6" fill="#fff"/>
<path d="M5 9 H8 V10 H6 V11 H8 V12 H6 V13 H5 Z" fill="{RED}"/>"""
    return wrap(16, "", body)

if __name__ == "__main__":
    open("ff-icon-32.svg", "w").write(m32())
    open("ff-icon-16.svg", "w").write(m16())
    print("ok")
