"""Glow Grid enclosure: frame, grid, cover and desk cradle for a 16x16 WS2812B panel.

Usage:  python3 build.py [output_dir]      (default: ./out)
Needs:  pip install numpy trimesh manifold3d shapely

All sizes are millimetres and live in the 'shared dimensions' block and next to each part.
Nothing here has been test-printed yet; see the README's Enclosure section for what is unverified.
"""
import os, sys
import numpy as np, trimesh
from trimesh.creation import box, cylinder
from trimesh.boolean import union, difference, intersection
from shapely.geometry import Polygon, box as sbox
from shapely import affinity

OUT=(sys.argv[1] if len(sys.argv)>1 else 'out').rstrip('/')+'/'
os.makedirs(OUT,exist_ok=True)
def B(x0,x1,y0,y1,z0,z1):
    m=box(extents=[x1-x0,y1-y0,z1-z0]); m.apply_translation([(x0+x1)/2,(y0+y1)/2,(z0+z1)/2]); return m
def Cz(x,y,r,z0,z1,sec=64):
    m=cylinder(radius=r,height=z1-z0,sections=sec); m.apply_translation([x,y,(z0+z1)/2]); return m
def Cx(y,z,r,x0,x1,sec=64):
    m=cylinder(radius=r,height=x1-x0,sections=sec)
    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[0,1,0])); m.apply_translation([(x0+x1)/2,y,z]); return m
def hull(pts): return trimesh.convex.convex_hull(np.array(pts,float))
def clean(m):
    m.merge_vertices(); m.remove_unreferenced_vertices(); return m
def report(name,m):
    print(f'{name}: watertight={m.is_watertight} volume={m.volume/1000:.1f} cm3 size={np.round(m.extents,1)} tris={len(m.faces)}')

# ---------------- shared dimensions (mm) ----------------
WALL=2.0; OUTER=166.0; INNER=OUTER-2*WALL        # 162 pocket
HO=OUTER/2; HI=INNER/2                            # 83, 81
BACK=3.0                                          # back plate
ZL=23.0                                           # nominal back face of the panel when the cover holds the stack (20 mm of wiring space behind it)
LIP_DROP=2.0                                      # lip top sits this far behind ZL: a backstop, so the stack can't fall back past it
LIPZ=ZL-LIP_DROP                                  # 21.0
LIP_W=3.0                                         # how far the lip overlaps the panel edge
NOTCH_SIDE='left'; NOTCH_C=2.5; NOTCH_W=25.0      # one gap in the lip for the panel's wire tail (side, centre along the wall, width)
FING_T=1.6; FING_W=10.0; FING_PRELOAD=0.8         # printed spring fingers: thickness, width, how far they are compressed when the cover is on
FING_TIP=(ZL+FING_PRELOAD)                        # free height of the finger tip above the back plate
PANEL_T=1.6; GRID_H=8.0
H=ZL+PANEL_T+GRID_H                               # 32.6 frame rim height
GRID_OUT=161.0                                    # grid outer (walls on +/-80 centres, 1 mm thick)

def extrude_x(poly,x0,x1):
    m=trimesh.creation.extrude_polygon(poly,x1-x0)          # local x=u, y=v, z=extrusion
    R=np.array([[0,0,1,x0],[1,0,0,0],[0,1,0,0],[0,0,0,1]],float)  # print: x=extrusion, y=u, z=v (proper rotation)
    m.apply_transform(R); return m

# cradle back-post screw positions (shared by the frame holes and the cradle pilot holes)
POST_X=(-62.0,62.0); POST_SCREW_B=(14.0,34.0)      # x of the two posts, and screw heights b above the frame's bottom edge
# ---------------- 1. FRAME ----------------
frame=difference([B(-HO,HO,-HO,HO,0,H),B(-HI,HI,-HI,HI,BACK,H+1)],engine='manifold')   # shell: 4 walls + back plate, open front
cuts=[]   # holes and notches, cut after the inside features are added
# panel lip: continuous on all four walls, 45-degree underside, flat top at LIPZ (the notch for the wire tail is cut below)
pads=[]
def pad(axis,sign,a0,a1):
    prof=[(0,LIPZ-LIP_W),(LIP_W,LIPZ-1),(LIP_W,LIPZ),(0,LIPZ)]   # (inset from the wall, z)
    pts=[]
    for a in (a0,a1):
        for t,z in prof:
            if axis=='x': pts.append([a, sign*(HI-t), z])      # lip along x on the top/bottom wall
            else:         pts.append([sign*(HI-t), a, z])      # lip along y on the left/right wall
    return hull(pts)
for sg in (1,-1):
    pads.append(pad('x',sg,-HI,HI)); pads.append(pad('y',sg,-HI,HI))
# spring fingers: four 45-degree cantilevers on the back plate; their tips press the panel's back face forward against the cover
fingers=[]
def finger(sx,sy,out):
    # tip contact point (sx,sy); the arm runs back toward the wall (out=+1 -> larger |y|), rising 45 degrees
    run=FING_TIP-2.5-BACK; yb=sy+out*run
    from shapely.geometry import LineString, Point
    arm=LineString([(yb,BACK-0.1),(sy,FING_TIP-2.5)]).buffer(FING_T/2,cap_style=2)
    cap=Point(sy,FING_TIP-2.5).buffer(2.5,resolution=24)
    foot=sbox(min(yb,yb+out*5),BACK-0.1,max(yb,yb+out*5),BACK+4)
    poly=arm.union(cap).union(foot)
    return extrude_x(poly,sx-FING_W/2,sx+FING_W/2)
# C3 SuperMini holder: a SEPARATE small print that carries the board (component side down, header pins up toward the panel).
# It drops into brackets on the frame's back plate and is glued there; the board is taped or glued to it. The USB-C end faces the
# left wall so the plug reaches the board through the wall slot. Wires are soldered to the pin tips (no Dupont housings: they would hit the panel).
# MEASURED block: caliper the real board, edit, rerun. Values are guesses until then.
H_PCB, H_BOARD_L, H_BOARD_W = 1.2, 24.0, 18.0
H_COMP_H=3.4; H_FIRST_PIN=2.6; H_PIN_TIP=1.2; H_HDR=2.5; H_PIN_UP=6.0     # tallest part under the board, first pin from end, tips under the board, header plastic, pin above plastic
H_ROW=15.24
H_BASE=2.5; H_CLR=0.2; H_RIB=0.10; H_RAIL=1.6; H_STOP=3.0                 # holder base, board clearance, crush-rib squeeze per side, rail and end-stop thickness (v2, printed and fitted 2026-10-15: base 2.5 and stop 3.0 match c3_holder_test.py)
# v2 additions, same numbers as the printed test piece: a far-end cap that stops the board lifting when the USB cable is wiggled, and a notch for the u.FL antenna cable
UFL_X, UFL_Y = 18.0, -4.9          # u.FL socket: 18 mm from the USB end, 4.9 mm toward -y (USB end at the top, pins up). Same sign as the test piece, which fitted
CABLE_W = 3.5                      # notch through the far seat and stop, under the board only, for the 1.13 mm coax and the u.FL plug body
CAP_OVER, CAP_T, CAP_GAP = 1.5, 1.2, 0.4   # cap lip overhang over the board end, plate thickness, air above the PCB
PEG_D, PEG_L, PEG_FIT = 2.0, 3.0, 0.10     # pegs into the stop; hole is PEG_D + 2*PEG_FIT
PEGYS = (-5.5, 5.5)
H_UNDER=max(H_COMP_H,H_PIN_TIP)+1.5                                          # air under the board
H_ZS=H_BASE+H_UNDER; H_ZP=H_ZS+H_PCB                                         # board underside / PCB top, holder coords (z=0 is the holder's bottom)
H_LEDGE=H_FIRST_PIN-1.1; H_HW=H_BOARD_W/2+H_CLR; H_X1=H_BOARD_L+0.1; H_XEND=H_X1+H_CLR+H_STOP
def make_holder():
    p=[B(0,H_XEND,-H_HW-H_RAIL,H_HW+H_RAIL,0,H_BASE),
       B(H_X1+H_CLR,H_XEND,-H_HW-H_RAIL,H_HW+H_RAIL,0,H_ZP+0.8),          # end stop: takes the USB plug-in push
       B(H_X1-H_LEDGE,H_X1+H_CLR,-H_HW,H_HW,H_BASE,H_ZS)]                  # far-end seat
    for sg_ in (1,-1):
        y0,y1=(H_HW,H_HW+H_RAIL) if sg_==1 else (-H_HW-H_RAIL,-H_HW)
        p.append(B(0,H_X1+H_CLR,y0,y1,H_BASE,H_ZP+0.8))                     # side rails
        ya,yb=(H_BOARD_W/2-3.8,H_BOARD_W/2) if sg_==1 else (-H_BOARD_W/2,-H_BOARD_W/2+3.8)
        p.append(B(0.1,0.1+H_LEDGE,ya,yb,H_BASE,H_ZS))                      # USB-end seat pads
        for rx in (8.0,18.0):                                               # crush ribs at PCB level
            inn=H_HW-(H_CLR+H_RIB); ya2,yb2=(inn,H_HW) if sg_==1 else (-H_HW,-inn)
            p.append(B(rx,rx+2.0,ya2,yb2,H_ZS+0.1,H_ZP+0.5))
    h=clean(union(p,engine='manifold'))
    cuts_=[B(H_X1-H_LEDGE-0.1,H_XEND+0.1,UFL_Y-CABLE_W/2,UFL_Y+CABLE_W/2,H_BASE-0.01,H_ZS-0.05)]   # cable exit through the far seat and stop, under the board only
    for py in PEGYS:                                                                                # peg holes from the top of the stop
        hh=cylinder(radius=PEG_D/2+PEG_FIT,height=PEG_L+0.6,sections=32); hh.apply_translation([H_X1+H_CLR+H_STOP/2,py,H_CAPZ0-(PEG_L+0.6)/2+0.01]); cuts_.append(hh)
    return clean(difference([h]+cuts_,engine='manifold'))
H_CAPZ0=H_ZP+0.8                                                                                    # cap plate sits on top of the rails and stop
def make_cap():
    # separate print, plate face down, pegs up; presses nothing, only stops the far end of the board lifting
    cp=[B(H_X1-CAP_OVER,H_XEND,-H_HW-H_RAIL,H_HW+H_RAIL,H_CAPZ0,H_CAPZ0+CAP_T),                    # plate on the rails and stop
        B(H_X1-CAP_OVER,H_X1+H_CLR,-H_HW+0.1,H_HW-0.1,H_ZP+CAP_GAP,H_CAPZ0+0.01)]                  # lip down to 0.4 mm above the PCB
    for py in PEGYS:
        pg=cylinder(radius=PEG_D/2,height=PEG_L+0.01,sections=32); pg.apply_translation([H_X1+H_CLR+H_STOP/2,py,H_CAPZ0-PEG_L/2+0.005]); cp.append(pg)
    return clean(union(cp,engine='manifold'))
holder=make_holder(); report('c3_holder',holder); holder.export(OUT+'glow-grid_c3_holder_v2.stl')
cap=make_cap(); report('c3_holder_cap',cap); cap.export(OUT+'glow-grid_c3_holder_cap_v2.stl')
# placement: holder x=0 is 0.3 mm off the left wall's inner face, centred on y=cy; holder z=0 sits on the back plate
cy=-30.0; HX=-HI+0.3; HZ=BACK
def to_frame(m): m=m.copy(); m.apply_translation([HX,cy,HZ]); return m
# brackets on the back plate: two side walls and a far wall around the holder (clearance H_BC), glued; the left wall is the fourth side
H_BC=0.25; BR_H=5.0; BR_T=1.6
bx_end=HX+H_XEND+H_BC; byo=H_HW+H_RAIL+H_BC
hold=[B(-HI,bx_end+BR_T,cy+byo,cy+byo+BR_T,BACK-0.1,BACK+BR_H),
      B(-HI,bx_end+BR_T,cy-byo-BR_T,cy-byo,BACK-0.1,BACK+BR_H),
      B(bx_end,bx_end+BR_T,cy-byo-BR_T,cy+byo+BR_T,BACK-0.1,BACK+BR_H)]
for sx in (-48,48):
    fingers.append(finger(sx,50,+1)); fingers.append(finger(sx,-50,-1))
frame=union([frame]+pads+hold+fingers,engine='manifold')   # 'hold' = the C3 holder brackets
cuts.append(B(bx_end-0.1,bx_end+BR_T+0.1,cy+UFL_Y-CABLE_W/2,cy+UFL_Y+CABLE_W/2,BACK,BACK+BR_H+0.1))   # far-wall notch where the antenna cable leaves the holder (plate left intact)
# lip notch for the panel's wire tail
if NOTCH_SIDE in ('left','right'):
    sg={'left':-1,'right':1}[NOTCH_SIDE]
    cuts.append(B(min(sg*(HI-LIP_W-1),sg*(HI+0.01)),max(sg*(HI-LIP_W-1),sg*(HI+0.01)),NOTCH_C-NOTCH_W/2,NOTCH_C+NOTCH_W/2,LIPZ-LIP_W-1,LIPZ+0.5))
else:
    sg={'bottom':-1,'top':1}[NOTCH_SIDE]
    cuts.append(B(NOTCH_C-NOTCH_W/2,NOTCH_C+NOTCH_W/2,min(sg*(HI-LIP_W-1),sg*(HI+0.01)),max(sg*(HI-LIP_W-1),sg*(HI+0.01)),LIPZ-LIP_W-1,LIPZ+0.5))
# holes: jack and data lead in the BACK plate; USB-C slot in the left wall at the C3 port
cuts.append(Cz(45,25,6.15,-1,BACK+1))                              # 12 mm panel-mount DC jack (12.3 bore)
cuts.append(Cz(20,25,3.5,-1,BACK+1))                               # 7 mm data lead
cuts.append(B(-HO-1,-HI+0.01,cy-6.0,cy+6.0,HZ+H_BASE,HZ+H_ZP-0.2))     # USB-C plug slot 12 wide, from the holder's top face up to just under the PCB top
cuts.append(B(-HI-0.01,-HI+4.0,cy-8.0,cy+8.0,LIPZ-LIP_W-1,LIPZ+0.5))  # second, short lip notch so the USB-C plug clears the lip
for bxx in (-20,-45):
    cuts.append(Cz(bxx,25,6.15,-1,BACK+1))                         # two 12 mm panel-mount push buttons (next image, on/off)
cuts.append(B(-38,3,-72.5,-59.5,BACK-0.4,BACK+0.5))                # 0.4 mm recess marking the flat spot for the 40 x 12 mm stick-on antenna
frame=clean(difference([frame]+cuts,engine='manifold'))
report('frame',frame); frame.export(OUT+'glow-grid_frame_v5.stl')

# ---------------- 2. GRID (separate print, black) ----------------
bars=[]
for i in range(17):
    c=-80+10*i
    bars.append(B(c-0.5,c+0.5,-80.5,80.5,0,GRID_H)); bars.append(B(-80.5,80.5,c-0.5,c+0.5,0,GRID_H))
grid=clean(union(bars,engine='manifold'))
report('grid',grid); grid.export(OUT+'glow-grid_grid_16x16_v2.stl')

# ---------------- 3. COVER (white, thin) ----------------
CT=0.6; LIP_T=1.2; LIP_H=3.0; CL=0.15            # 0.15 mm clearance per side around the frame, bumps give the grip
LI=OUTER/2+CL; LO=LI+LIP_T
cover=[B(-LO,LO,-LO,LO,0,CT)]
ring=difference([B(-LO,LO,-LO,LO,CT-0.01,CT+LIP_H),B(-LI,LI,-LI,LI,CT-1,CT+LIP_H+1)],engine='manifold')
cover.append(ring)
for s in (1,-1):                                  # four small grip bumps, 0.25 mm proud, mid-side
    cover.append(B(-6,6,min(s*LI,s*LI-s*0.25),max(s*LI,s*LI-s*0.25),CT+0.8,CT+LIP_H))
    cover.append(B(min(s*LI,s*LI-s*0.25),max(s*LI,s*LI-s*0.25),-6,6,CT+0.8,CT+LIP_H))
cover=clean(union(cover,engine='manifold'))
report('cover',cover); cover.export(OUT+'glow-grid_cover_0.6mm_v2.stl')

# ---------------- 4. DESK CRADLE (tilts the frame back 12 degrees) ----------------
# The frame rests on a shoulder under its bottom edge and leans back against two tall back posts.
# Front hook: a low wall in front of the cover, only up to b=1.8 mm, i.e. over the cover's plain border (the frame wall), never over an LED row (grid starts at b=2.5).
# Back posts: a 0.6 mm tape recess in each face (for ~1 mm double-sided tape) and two M3 holes each, all the way through. The screws start at the BACK of the post, go forward and cut their own thread into the frame's plain 3 mm back plate (no holes in the frame, David's call 2026-10-13).
# Base: two rounded-rectangle feet joined by a curved, filleted bar (D-18, D-19), no desk screw holes (removed 2026-10-13; the cradle sits on the desk by weight).
TH=np.radians(12); c,s=np.cos(TH),np.sin(TH); D=H+0.4
BACK_POST_B=75.0                                  # posts reach 75 mm up the back plate (jack/button holes are at b=108)
BACK_POST_T=8.0                                   # post thickness behind the back plate (room for the screw pilot)
SHOULDER_A=29.0                                   # shoulder (b=0) stops here; beyond it the floor drops to clear the cover lip
COVER_DROP=-1.8                                   # cover lip hangs 1.35 below the frame's bottom edge, plus clearance
HOOK_A0=H+CT+0.4; HOOK_B=1.8                      # front hook wall: starts 0.4 mm in front of the cover face, rises to b=1.8
TAPE_DEPTH=0.6; TAPE_W=24.0; TAPE_B0,TAPE_B1=42.0,72.0
SCREW_HOLE_D=2.2; SCREW_HEAD_D=4.4; SCREW_HEAD_DEEP=3.0   # M3 through hole, head counterbore from the back face; M3x8 then reaches 2.8 mm into the frame's 3 mm back plate
pts_ab=[(-BACK_POST_T,-30),(D+4.3,-30),(D+4.3,HOOK_B),(HOOK_A0,HOOK_B),(HOOK_A0,COVER_DROP),(SHOULDER_A,COVER_DROP),(SHOULDER_A,0),(-0.2,0),(-0.2,BACK_POST_B),(-BACK_POST_T,BACK_POST_B)]
def ab2uv(a,b,v0=6.0): return (a*c-b*s, a*s+b*c+v0)
poly=Polygon([ab2uv(a,b) for a,b in pts_ab]).intersection(sbox(-200,0,200,200))
blocks=[]
for px in POST_X:
    x0=px-17
    blk=extrude_x(poly,x0,x0+34)
    rec=extrude_x(Polygon([ab2uv(a,b) for a,b in [(-0.2-TAPE_DEPTH,TAPE_B0),(-0.19,TAPE_B0),(-0.19,TAPE_B1),(-0.2-TAPE_DEPTH,TAPE_B1)]]),px-TAPE_W/2,px+TAPE_W/2)
    cutters=[rec]
    def a_cyl(r,a0,a1,pb):                        # cylinder along the a axis (tilted 12 deg), from a0 to a1, at height b=pb
        cy_=cylinder(radius=r,height=a1-a0,sections=40)
        cy_.apply_transform(trimesh.geometry.align_vectors([0,0,1],[0,c,s]))
        cy_.apply_translation([px+0.013,*ab2uv((a0+a1)/2,pb)]); return cy_
    for pb in POST_SCREW_B:                       # screw starts at the BACK of the post and goes forward into the frame's back plate
        cutters.append(a_cyl(SCREW_HOLE_D/2,-BACK_POST_T-0.5,0.5,pb))                       # through hole, all the way
        cutters.append(a_cyl(SCREW_HEAD_D/2,-BACK_POST_T-0.5,-BACK_POST_T+SCREW_HEAD_DEEP,pb))  # counterbore for the screw head
    blocks.append(clean(difference([blk]+cutters,engine='manifold')))
ub=poly.bounds
SLAB_U0,SLAB_U1=ub[0]-30,ub[2]+12
FOOT_HALF_W=25.0; FOOT_R=12.0                    # two rounded-rectangle feet (one under each post block)...
BAR_W=20.0; BAR_BOW=12.0; FILLET_R=10.0          # ...joined by a curved bar that bows toward the front, with rounded (filleted) junctions
from shapely.geometry import LineString
from shapely.ops import unary_union
def foot_poly(px):
    return sbox(px-FOOT_HALF_W+FOOT_R,SLAB_U0+FOOT_R,px+FOOT_HALF_W-FOOT_R,SLAB_U1-FOOT_R).buffer(FOOT_R,resolution=24)
u_mid=(SLAB_U0+SLAB_U1)/2
t_=np.linspace(0,1,60); x0_,x1_=POST_X[0],POST_X[1]                         # quadratic bezier: ends inside the feet, control point pulls the middle forward
U_END=40.0   # v14: connector sits in front of the frame (frame/cover cover u < 33), ends at the feet's front, middle bows further forward
bez=[((1-t)**2*x0_+2*(1-t)*t*0+t**2*x1_, (1-t)**2*U_END+2*(1-t)*t*(U_END+2*BAR_BOW)+t**2*U_END) for t in t_]
bar=LineString(bez).buffer(BAR_W/2,cap_style=1,resolution=24)
base=unary_union([foot_poly(px) for px in POST_X]+[bar])
base=base.buffer(FILLET_R,resolution=24).buffer(-FILLET_R,resolution=24)     # closing: rounds the inside corners where the bar meets the feet
assert base.geom_type=='Polygon', base.geom_type
slab_feet=[trimesh.creation.extrude_polygon(base,5.0)]                       # x,y = print x,u; z = 0..5
# --- v11: embossed pixel-art lettering "PIXEL ART" on the bar plate (5x7 pixel capitals, 1.4 mm pixels, 1.0 mm relief)
from shapely.geometry import box as _bx_
FONT={'P':["11110","10001","10001","11110","10000","10000","10000"],'I':["01110","00100","00100","00100","00100","00100","01110"],
      'X':["10001","10001","01010","00100","01010","10001","10001"],'E':["11111","10000","10000","11110","10000","10000","11111"],
      'L':["10000","10000","10000","10000","10000","10000","11111"],'A':["01110","10001","10001","11111","10001","10001","10001"],
      'R':["11110","10001","10001","11110","10100","10010","10001"],'T':["11111","00100","00100","00100","00100","00100","00100"]}
TEXT="PIXEL ART"; PXS=1.4; EMB_H=1.0; LETTER_GAP=1; SPACE_W=3; TEXT_U=float(np.interp(0,[p[0] for p in bez],[p[1] for p in bez]))*0+0.0   # text is centred on the bar centreline (u offset 0 at x=0 is handled by the warp)
cols=sum(5 if ch!=' ' else SPACE_W for ch in TEXT)+LETTER_GAP*(len(TEXT)-1-TEXT.count(' ')*0)
pix=[]; cx_=0
for ch in TEXT:
    if ch==' ': cx_+=SPACE_W; continue
    for r,row in enumerate(FONT[ch]):
        for c_,v in enumerate(row):
            if v=='1': pix.append((cx_+c_,r))
    cx_+=5+LETTER_GAP
W_=cx_-LETTER_GAP; x0_t=-W_*PXS/2; u_top=TEXT_U+7*PXS/2
_sq=[_bx_(x0_t+c_*PXS,u_top-(r+1)*PXS,x0_t+(c_+1)*PXS,u_top-r*PXS) for c_,r in pix]
_txt=unary_union([q.buffer(0.07,join_style=2) for q in _sq])
from shapely import affinity as _aff, segmentize as _seg, transform as _tr
_txt=_aff.rotate(_txt,180,origin=(0.0,TEXT_U))     # turned 180 degrees: reads left to right from the screen side
_bxs=np.array([p[0] for p in bez]); _bus=np.array([p[1] for p in bez]); _bdy=np.gradient(_bus,_bxs)
def _warp(pts):   # lay the flat text onto the bar's centreline: x follows the curve, offset from the baseline runs along the curve's normal
    out=np.empty_like(pts)
    for k,(x,u) in enumerate(pts):
        du=u-TEXT_U0; uc=np.interp(x,_bxs,_bus); sl=np.interp(x,_bxs,_bdy); n=np.hypot(1,sl)
        out[k]=(x-du*sl/n, uc+du/n)
    return out
TEXT_U0=TEXT_U
_txt=_tr(_seg(_txt,0.25),_warp)
_txt=_txt.buffer(0)
print('pixel text width mm:',round(W_*PXS,1),'height mm:',round(7*PXS,1))
_emb=[]
for pg in ([_txt] if _txt.geom_type=='Polygon' else list(_txt.geoms)):
    e=trimesh.creation.extrude_polygon(pg,EMB_H+0.1); e.apply_translation([0,0,5.0-0.1]); e.merge_vertices(); e.remove_unreferenced_vertices(); _emb.append(e)
slab_feet.extend(_emb)
cradle=clean(union(blocks+slab_feet,engine='manifold'))
report('cradle (two feet joined by a curved bar)',cradle); cradle.export(OUT+'glow-grid_desk_cradle_v14.stl')
print('base: feet',2*FOOT_HALF_W,'x',round(SLAB_U1-SLAB_U0,1),'mm r',FOOT_R,'; bar',BAR_W,'mm wide bowing',BAR_BOW,'mm forward; fillet r',FILLET_R)

# ---------------- checks ----------------
# frame placed in the cradle (frame coords: a=z, b=y+83)  -> print coords x=x, y=u, z=v
P=frame.copy(); V=P.vertices.copy()
a=V[:,2]; b=V[:,1]+HO
u=a*c-b*s; v=a*s+b*c+6.0
P.vertices=np.c_[V[:,0],u,v]
P.fix_normals()
inter=intersection([P,cradle],engine='manifold')
print('frame/cradle overlap volume (want 0):',round(inter.volume,2),'mm3')
# cover as assembled: plate face outward at a=H+CT, lip hangs back to a=H-3; flip z so it sits on the frame
Cv=cover.copy(); VC=Cv.vertices.copy(); aa=H+CT-VC[:,2]; bb=VC[:,1]+HO
Cv.vertices=np.c_[VC[:,0],aa*c-bb*s,aa*s+bb*c+6.0]; Cv.fix_normals()
ic=intersection([Cv,cradle],engine='manifold')
print('cover/cradle overlap volume (want 0):',round(ic.volume,2),'mm3')
# does anything of the cradle stand in front of the lit face? max b of cradle material in front of the plate face (a>H+CT)
Vc=cradle.vertices; ac=Vc[:,1]*c+(Vc[:,2]-6.0)*s; bc=-Vc[:,1]*s+(Vc[:,2]-6.0)*c
front=ac>H+CT-0.01
print('cradle material in front of cover face: max b =',round(bc[front].max(),2),'mm (want <= 1.8; grid starts at 2.5)')
# centre of mass of the standing frame (+ grid + cover; panel/electronics ignored) vs slab footprint
parts=[]
for m in (frame,grid,cover):
    Q=m.copy(); VV=Q.vertices.copy()
    if m is grid: VV=VV+[0,0,ZL+PANEL_T]
    if m is cover: VV=VV+[0,0,H]
    aa=VV[:,2]; bb=VV[:,1]+HO; Q.vertices=np.c_[VV[:,0],aa*c-bb*s,aa*s+bb*c+6.0]; parts.append(Q)
tot=sum(p.volume for p in parts); cg=sum(p.center_mass*p.volume for p in parts)/tot
print('assembly c.g. (x,u,v):',np.round(cg,1),' slab u range',round(ub[0]-30,1),'to',round(ub[2]+12,1))

# ---------------- fit check: dummy board seated in the holder, holder seated in the frame ----------------
x0=0.1; hb=[B(x0,x0+H_BOARD_L,-H_BOARD_W/2,H_BOARD_W/2,H_ZS,H_ZP), B(x0-0.8,x0+6.0,-4.5,4.5,H_ZS-3.2,H_ZS), B(x0+8,x0+20,-5,5,H_ZS-2.5,H_ZS)]
for sg_ in (1,-1):
    yy=sg_*H_ROW/2
    hb.append(B(x0+H_FIRST_PIN-1.27,x0+H_FIRST_PIN-1.27+8*2.54,yy-1.27,yy+1.27,H_ZP,H_ZP+H_HDR))
    for i_ in range(8):
        px=x0+H_FIRST_PIN+i_*2.54; hb.append(B(px-.3,px+.3,yy-.3,yy+.3,H_ZS-H_PIN_TIP,H_ZP+H_HDR+H_PIN_UP))
board=to_frame(union(hb,engine='manifold')); hf=to_frame(holder)
print('holder vs frame overlap (want 0): %.2f mm3'%intersection([hf,frame],engine='manifold').volume)
print('board vs frame overlap (want 0): %.2f mm3'%intersection([board,frame],engine='manifold').volume)
print('board vs holder overlap (crush ribs only, ~1): %.2f mm3'%intersection([board,hf],engine='manifold').volume)
print('board underside z=%.1f  PCB top z=%.1f  pin tips z=%.1f  lip underside z=%.1f  panel back z=%.1f  USB slot z=%.1f..%.1f'%(HZ+H_ZS,HZ+H_ZP,HZ+H_ZP+H_HDR+H_PIN_UP,LIPZ-LIP_W,ZL,HZ+H_BASE,HZ+H_ZP-0.2))
ovc=intersection([to_frame(cap),board],engine='manifold').volume; print('cap vs board overlap (want 0): %.2f mm3'%ovc)
print('cap vs holder overlap (want 0; the plate rests on the rails, face contact only): %.2f mm3'%intersection([to_frame(cap),hf],engine='manifold').volume)
print('cap vs frame overlap (want 0): %.2f mm3'%intersection([to_frame(cap),frame],engine='manifold').volume)

# ---------------- antenna cable route check ----------------
# The 40 x 12 mm stick-on antenna sits in the back-plate recess (x -38..3, y -72.5..-59.5). Its pigtail is assumed to leave the end nearest the holder (x=-38).
# Route: u.FL socket -> along the holder base through the cable notch (z = base + 0.4) -> through the bracket far-wall notch -> straight +x to CABLE_TURN_X,
# which keeps clear of the left spring finger (x -53..-43) -> down -y along the back plate to the antenna end. 1.13 mm coax, modelled as a 1.6 mm square envelope.
CABLE_TURN_X=-40.0; ANT_END=(-38.0,-60.0); CD=1.6
ufl_f=(HX+UFL_X, cy+UFL_Y)
route=[B(ufl_f[0]-1.0,ufl_f[0]+1.0,ufl_f[1]-1.0,ufl_f[1]+1.0,HZ+H_ZS-1.3,HZ+H_ZS),                                   # u.FL plug under the board
       B(ufl_f[0],HX+H_XEND+1.0,ufl_f[1]-CD/2,ufl_f[1]+CD/2,HZ+H_BASE+0.4,HZ+H_BASE+0.4+CD),                       # along the holder base
       B(HX+H_XEND,HX+H_XEND+4.0,ufl_f[1]-CD/2,ufl_f[1]+CD/2,HZ,HZ+H_BASE+0.4+CD),                                  # drops off the step to the plate (whole drop envelope)
       B(HX+H_XEND,CABLE_TURN_X+CD/2,ufl_f[1]-CD/2,ufl_f[1]+CD/2,HZ,HZ+CD),                                         # across the plate
       B(CABLE_TURN_X-CD/2,CABLE_TURN_X+CD/2,ANT_END[1],ufl_f[1]+CD/2,HZ,HZ+CD)]                                    # down to the antenna
cable=union(route,engine='manifold')
print('cable vs frame overlap (want 0): %.2f mm3'%intersection([cable,frame],engine='manifold').volume)
print('cable vs holder overlap (want 0): %.2f mm3'%intersection([cable,hf],engine='manifold').volume)
print('cable vs cap overlap (want 0): %.2f mm3'%intersection([cable,to_frame(cap)],engine='manifold').volume)
lenmm=(HX+H_XEND-ufl_f[0])+(CABLE_TURN_X-(HX+H_XEND))+abs(ufl_f[1]-ANT_END[1])+ (ANT_END[0]-CABLE_TURN_X)
print('cable run length about %.0f mm (u.FL to the antenna end); a 100 mm pigtail leaves about %.0f mm of slack'%(lenmm,100-lenmm))
