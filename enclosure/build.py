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
H_BASE=2.0; H_CLR=0.2; H_RIB=0.10; H_RAIL=1.6; H_STOP=2.0                 # holder base, board clearance, crush-rib squeeze per side, rail and end-stop thickness
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
    return clean(union(p,engine='manifold'))
holder=make_holder(); report('c3_holder',holder); holder.export(OUT+'glow-grid_c3_holder_v1.stl')
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
report('frame',frame); frame.export(OUT+'glow-grid_frame_v3.stl')

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
TH=np.radians(12); c,s=np.cos(TH),np.sin(TH); D=H+0.4
pts_ab=[(-5,-30),(D+4.3,-30),(D+4.3,14),(D+0.3,14),(D+0.3,0),(-0.2,0),(-0.2,32),(-5,32)]
def ab2uv(a,b,v0=6.0): return (a*c-b*s, a*s+b*c+v0)
poly=Polygon([ab2uv(a,b) for a,b in pts_ab]).intersection(sbox(-200,0,200,200))
blocks=[extrude_x(poly,x0,x0+34) for x0 in (-79,45)]
ub=poly.bounds
slab=B(-95,95,ub[0]-30,ub[2]+12,0,5)
cradle=clean(union(blocks+[slab],engine='manifold'))
report('cradle',cradle); cradle.export(OUT+'glow-grid_desk_cradle_v2.stl')

# ---------------- checks ----------------
# frame placed in the cradle (frame coords: a=z, b=y+83)  -> print coords x=x, y=u, z=v
P=frame.copy(); V=P.vertices.copy()
a=V[:,2]; b=V[:,1]+HO
u=a*c-b*s; v=a*s+b*c+6.0
P.vertices=np.c_[V[:,0],u,v]
P.fix_normals()
inter=intersection([P,cradle],engine='manifold')
print('frame/cradle overlap volume (want 0):',round(inter.volume,2),'mm3')
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
