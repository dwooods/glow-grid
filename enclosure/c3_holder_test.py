#!/usr/bin/env python3
"""C3 SuperMini holder test piece (pins up, component side down).
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
STOP  = 2.0
TAB_OVER, TAB_T, TAB_GAP, TAB_HALF = 1.1, 1.2, 0.4, 5.0
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
holder.merge_vertices(); holder.remove_unreferenced_vertices()
print('holder watertight:', holder.is_watertight, ' vol %.2f cm3' % (holder.volume/1000), ' size', np.round(holder.extents,1))
holder.export(OUT+'glow-grid_c3_holder_test.stl')

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
print('board/holder overlap mm3: %.1f (ribs only, from %.2f mm/side interference)' % (ov, RIB_INT))
print('board underside z=%.1f  PCB top z=%.1f  tab bottom z=%.1f  slot z=%.1f..%.1f  pin tops z=%.1f'%(ZS,ZP,ZP+TAB_GAP,BASE,SLOT_TOP,ZP+HDR_PLASTIC+6))
