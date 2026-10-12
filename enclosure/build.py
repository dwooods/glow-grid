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
# C3 SuperMini holder. Board 24 x 18 x 1.2 mm with 8-pin headers along both long edges (rows 15.24 apart) whose
# plastic (HDR tall) and tails (TAIL long) hang BELOW the board. The headers drop into two channels, the tails into
# slots below them, so the board lies flat on a platform. Wires are soldered to the pin pads on top. USB-C end faces the left wall.
C3L,C3W=24.0,18.0; cy=-30.0; bx0=-HI+1.0; bx1=bx0+C3L
ROW=15.24; HDR=2.5; TAIL=7.0; PCB=1.2
ZCH=BACK+0.8+TAIL+0.2                 # channel floor (header plastic rests here)
ZTOP=ZCH+HDR                          # platform the board's underside rests on
ZB=ZTOP+PCB                           # top face of the board
blk=B(bx0,bx1,cy-C3W/2,cy+C3W/2,BACK-0.1,ZTOP)
for sgn in (1,-1):
    yy=cy+sgn*ROW/2
    blk=difference([blk,B(bx0-1,bx1+1,yy-1.5,yy+1.5,ZCH,ZTOP+1),B(bx0-1,bx1+1,yy-0.9,yy+0.9,BACK+0.8,ZCH+0.1)],engine='manifold')
hold=[blk]
for s_ in (1,-1):                      # side walls that keep the board from sliding sideways
    y0=cy+s_*(C3W/2+0.25); y1=y0+s_*1.2
    hold.append(B(bx0-0.3,bx1+0.6,min(y0,y1),max(y0,y1),BACK-0.1,ZB+0.5))
hold.append(B(bx1+0.35,bx1+1.55,cy-C3W/2-0.25,cy+C3W/2+0.25,BACK-0.1,ZB+0.5))     # end stop
hold.append(B(bx1-0.8,bx1+1.55,cy-3.0,cy+3.0,ZB+0.5-0.01,ZB+1.5))                 # snap hook over the far end of the board (press the board down to seat it)
for sx in (-48,48):
    fingers.append(finger(sx,50,+1)); fingers.append(finger(sx,-50,-1))
frame=union([frame]+pads+hold+fingers,engine='manifold')
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
cuts.append(B(-HO-1,-HI+1.5,cy-5.2,cy+5.2,ZB-0.3,ZB+3.9))          # USB-C slot 10.4 x 4.2 in the left wall, at the connector's height
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

# ---------------- fit check: a 24 x 18 board with its headers, USB-C plug and wire clearance placed in the holder ----------------
brd=[B(bx0,bx1,cy-C3W/2,cy+C3W/2,ZTOP,ZB),                                     # PCB
     B(bx0-1.3,bx0+9.0,cy-4.5,cy+4.5,ZB,ZB+3.2)]                              # USB-C shell (sticks out 1.3 mm past the edge)
for sgn in (1,-1):
    yy=cy+sgn*ROW/2
    brd.append(B(bx0+1.9,bx0+1.9+20.32,yy-1.27,yy+1.27,ZCH,ZTOP))             # header plastic
    brd.append(B(bx0+1.9,bx0+1.9+20.32,yy-0.5,yy+0.5,ZCH-TAIL,ZCH))           # pin tails (shown as one bar)
brd=union(brd,engine='manifold')
print('C3 board vs frame overlap (want ~0):',round(intersection([brd,frame],engine='manifold').volume,2),'mm3')
print('board top z=%.1f, lip underside z=%.1f, panel back z=%.1f; spring-finger tip top z=%.1f'%(ZB,LIPZ-LIP_W,ZL,FING_TIP))
