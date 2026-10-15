#!/usr/bin/env python3
"""C3 SuperMini holder test piece v2 (pins up, component side down): adds a far-end hold-down cap and a notch for the u.FL antenna cable.
Usage: python3 c3_holder_test.py [output_dir]
Edit the MEASURED block, rerun, reprint. Everything is in mm."""
import sys, numpy as np, trimesh
from trimesh.creation import box
from trimesh.boolean import union, difference, intersection
OUT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'

# ---- MEASURED (guesses until you caliper the board) ----
BOARD_L, BOARD_W, PCB = 24.0, 18.0, 1.2
COMP_H     = 3.4     # tallest part on the component side (USB-C shell / button)
FIRST_PIN  = 2.6     # short end of board to first pin-hole centre
PIN_TIP    = 1.2     # pin tips poking out of the component side
HDR_PLASTIC = 2.5    # black header body height above the PCB (pin side)
# ---- design ----
CLR   = 0.2          # board-to-wall clearance
RIB_INT = 0.10       # crush-rib interference per side
BASE  = 2.5; WALL = 2.0
UNDER = max(COMP_H, PIN_TIP) + 1.5      # air under the board
ZS    = BASE + UNDER                    # board underside height
ZP    = ZS + PCB                        # PCB top
LEDGE = FIRST_PIN - 1.1                 # end-support width, stays clear of pin tips
HW    = BOARD_W/2 + CLR                 # pocket half-width
RAIL  = 1.6
X1    = BOARD_L + 0.1                   # far end of the board (USB end at x=0.1)
STOP  = 3.0                      # thicker than v1: the cap pegs go into it
TAB_OVER, TAB_T, TAB_GAP, TAB_HALF = 1.1, 1.2, 0.4, 5.0
# v2 (2026-10-15, David: wiggling the USB cable pulled the board out at the far end; the u.FL cable was pinched under the far end)
UFL_X, UFL_Y = 18.0, -4.9        # u.FL socket, measured from David's photo: about 18 mm from the USB end, 4.9 mm off centre (toward -y with the USB end at the top and pins up). CHECK on your board.
CABLE_W = 3.5                    # notch through the far seat and stop, under the board only, for the 1.13 mm coax and the u.FL plug body
CAP_OVER, CAP_T, CAP_GAP = 1.5, 1.2, 0.4   # cap lip overhang over the board end (header plastic ends 2.3 mm short of the end), plate thickness, air above the PCB
PEG_D, PEG_L, PEG_FIT = 2.0, 3.0, 0.10     # pegs into the stop; hole is PEG_D + 2*PEG_FIT
SLOT_HALF, SLOT_TOP = 6.0, ZP - 0.2

def B(x0,x1,y0,y1,z0,z1):
    m = box(extents=[x1-x0,y1-y0,z1-z0]); m.apply_translation([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]); return m
def U(*p): return union(list(p), engine='manifold')

XEND = X1 + CLR + STOP
parts = [B(-WALL, XEND, -HW-RAIL, HW+RAIL, 0, BASE),                      # base
         B(-WALL, 0, -HW-RAIL, HW+RAIL, 0, ZP+TAB_GAP+TAB_T+1.5),         # USB wall
         B(X1+CLR, XEND, -HW-RAIL, HW+RAIL, 0, ZP+0.8),                   # far stop
         B(X1-LEDGE, X1+CLR, -HW, HW, BASE, ZS)]                          # far-end seat
for s in (1,-1):
    y0,y1 = (HW, HW+RAIL) if s==1 else (-HW-RAIL, -HW)
    parts.append(B(0, X1+CLR, y0, y1, BASE, ZP+0.8))                      # side rails
    ya,yb = (BOARD_W/2-3.8, BOARD_W/2) if s==1 else (-BOARD_W/2, -BOARD_W/2+3.8)
    parts.append(B(0.1, 0.1+LEDGE, ya, yb, BASE, ZS))                     # USB-end seat pads
    for rx in (8.0, 18.0):                                                # crush ribs (PCB level only)
        inner = HW - (CLR + RIB_INT)                                      # reaches into the PCB edge
        ya2,yb2 = (inner, HW) if s==1 else (-HW, -inner)
        parts.append(B(rx, rx+2.0, ya2, yb2, ZS+0.1, ZP-0.1+0.6))
parts.append(B(0, TAB_OVER+0.1, -TAB_HALF, TAB_HALF, ZP+TAB_GAP, ZP+TAB_GAP+TAB_T))  # hold-down tab
holder = U(*parts)
holder = difference([holder, B(-WALL-1, 0.01, -SLOT_HALF, SLOT_HALF, BASE-0.01, SLOT_TOP)], engine='manifold')  # USB slot
PEGX = X1 + CLR + STOP/2; PEGYS = (-5.5, 5.5); CAPZ0 = ZP + 0.8
cuts = [B(X1-LEDGE-0.1, XEND+0.1, UFL_Y-CABLE_W/2, UFL_Y+CABLE_W/2, BASE-0.01, ZS-0.05)]   # cable exit, under the board only
for py in PEGYS:                                                         # peg holes from the top of the stop
    h = trimesh.creation.cylinder(radius=PEG_D/2+PEG_FIT, height=PEG_L+0.6, sections=32); h.apply_translation([PEGX, py, CAPZ0-(PEG_L+0.6)/2+0.01]); cuts.append(h)
holder = difference([holder]+cuts, engine='manifold')
holder.merge_vertices(); holder.remove_unreferenced_vertices()
print('holder watertight:', holder.is_watertight, ' vol %.2f cm3' % (holder.volume/1000), ' size', np.round(holder.extents,1))
holder.export(OUT+'glow-grid_c3_holder_test.stl')

# ---- far-end cap: separate print, plate face down, pegs up; presses nothing, just stops the far end lifting ----
cap_parts = [B(X1-CAP_OVER, XEND, -HW-RAIL, HW+RAIL, CAPZ0, CAPZ0+CAP_T),                       # plate on the rails and stop
             B(X1-CAP_OVER, X1+CLR, -HW+0.1, HW-0.1, ZP+CAP_GAP, CAPZ0+0.01)]                    # lip down to 0.4 mm above the PCB
for py in PEGYS:
    p = trimesh.creation.cylinder(radius=PEG_D/2, height=PEG_L+0.01, sections=32); p.apply_translation([PEGX, py, CAPZ0-PEG_L/2+0.005]); cap_parts.append(p)
cap = U(*cap_parts)
cap = difference([cap, B(X1-CAP_OVER-1, X1-CAP_OVER+0.01, -HW-RAIL-1, HW+RAIL+1, CAPZ0, CAPZ0+CAP_T)], engine='manifold') if False else cap
cap.merge_vertices(); cap.remove_unreferenced_vertices()
print('cap watertight:', cap.is_watertight, ' vol %.2f cm3' % (cap.volume/1000), ' size', np.round(cap.extents,1))
cap.export(OUT+'glow-grid_c3_holder_cap.stl')

# ---- fit check with a dummy board ----
x0=0.1; yc=lambda s: s*7.62
dummy=[B(x0,x0+BOARD_L,-BOARD_W/2,BOARD_W/2,ZS,ZP),
       B(x0-0.8,x0+6.0,-4.5,4.5,ZS-3.2,ZS)]                              # USB-C shell
dummy.append(B(x0+8,x0+20,-5,5,ZS-2.5,ZS))                              # chip
for s in (1,-1):
    dummy.append(B(x0+FIRST_PIN-1.27,x0+FIRST_PIN-1.27+8*2.54,yc(s)-1.27,yc(s)+1.27,ZP,ZP+HDR_PLASTIC))
    for i in range(8):
        px=x0+FIRST_PIN+i*2.54
        dummy.append(B(px-.3,px+.3,yc(s)-.3,yc(s)+.3,ZS-PIN_TIP,ZP+HDR_PLASTIC+6))
board=U(*dummy); board.export(OUT+'dummy_c3_board.stl')
ov=intersection([holder,board],engine='manifold').volume
ovc=intersection([cap,board],engine='manifold').volume
print('board/cap overlap mm3: %.2f (must be 0)' % ovc)
# cap seated: pegs vs holes, plate vs holder
ovh=intersection([cap,holder],engine='manifold').volume
print('cap/holder overlap mm3: %.2f (pegs in holes: 0 expected; the plate rests on the rails, so only face contact)' % ovh)
# the u.FL plug and a 1.13 mm cable lying on the base through the notch: must not touch the holder
ufl=U(B(UFL_X-1.0,UFL_X+1.0,UFL_Y-1.0,UFL_Y+1.0,ZS-1.3,ZS), B(UFL_X,XEND+25,UFL_Y-0.57,UFL_Y+0.57,BASE+0.4,BASE+0.4+1.13))
print('cable/holder overlap mm3: %.2f (0 = cable passes the notch freely)' % intersection([ufl,holder],engine='manifold').volume)
print('board/holder overlap mm3: %.1f (ribs only, from %.2f mm/side interference)' % (ov, RIB_INT))
print('board underside z=%.1f  PCB top z=%.1f  tab bottom z=%.1f  slot z=%.1f..%.1f  pin tops z=%.1f'%(ZS,ZP,ZP+TAB_GAP,BASE,SLOT_TOP,ZP+HDR_PLASTIC+6))
