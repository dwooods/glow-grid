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
ZL=23.0                                           # panel rests on ledge top here (20 mm of wiring space behind it)
PANEL_T=1.6; GRID_H=8.0
H=ZL+PANEL_T+GRID_H                               # 32.6 frame rim height
GRID_OUT=161.0                                    # grid outer (walls on +/-80 centres, 1 mm thick)

# ---------------- 1. FRAME ----------------
frame=B(-HO,HO,-HO,HO,0,H)
cuts=[B(-HI,HI,-HI,HI,BACK,H+1)]
# panel ledge: four corner L-pads, 45-degree underside, 3 mm flat top
pads=[]
def pad(axis,sign,a0,a1):
    # inset t from the wall, z; extruded along the wall from a0 to a1
    prof=[(0,ZL-4),(3,ZL-1),(3,ZL),(0,ZL)]
    pts=[]
    for a in (a0,a1):
        for t,z in prof:
            if axis=='x': pts.append([a, sign*(HI-t), z])      # pad along x on top/bottom wall
            else:         pts.append([sign*(HI-t), a, z])      # pad along y on left/right wall
    return hull(pts)
for sg in (1,-1):
    for (a0,a1) in ((-HI,-HI+30),(HI-30,HI)):
        pads.append(pad('x',sg,a0,a1)); pads.append(pad('y',sg,a0,a1))
# C3 SuperMini holder: board 22.5 x 18, USB-C end flush to the left wall
C3L,C3W=22.5,18.0; cy=-30.0; bx0=-HI+0.3; bx1=bx0+C3L
hold=[]
for (sx,sy) in ((bx0+1.5,cy-C3W/2+1.5),(bx0+1.5,cy+C3W/2-1.5),(bx1-1.5,cy-C3W/2+1.5),(bx1-1.5,cy+C3W/2-1.5)):
    hold.append(B(sx-2,sx+2,sy-2,sy+2,BACK,BACK+3))              # 3 mm standoffs under the corners
for s in (1,-1):                                                   # side rails with small snap lips
    y0=cy+s*(C3W/2+0.3); y1=y0+s*1.2
    hold.append(B(bx0-0.3,bx1+0.6,min(y0,y1),max(y0,y1),BACK,BACK+8))
    for lx in (bx0+3,bx1-9):                                       # lips over the board top (board top at BACK+3+1.6)
        ya=y0; yb=y0-s*0.7
        hold.append(hull([[lx,ya,BACK+5.0],[lx+6,ya,BACK+5.0],[lx,yb,BACK+5.0],[lx+6,yb,BACK+5.0],
                          [lx,ya,BACK+6.0],[lx+6,ya,BACK+6.0],[lx,yb,BACK+6.0],[lx+6,yb,BACK+6.0],
                          [lx,ya,BACK+4.2],[lx+6,ya,BACK+4.2]]))
hold.append(B(bx1+0.4,bx1+1.6,cy-C3W/2-0.3,cy+C3W/2+0.3,BACK,BACK+8))   # end stop
frame=union([frame]+pads+hold,engine='manifold')
# holes: jack and data lead in the BACK plate; USB-C slot in the left wall at the C3 port
cuts.append(Cz(45,25,6.15,-1,BACK+1))                              # 12 mm panel-mount DC jack (12.3 bore)
cuts.append(Cz(20,25,3.5,-1,BACK+1))                               # 7 mm data lead
cuts.append(B(-HO-1,-HI+1.5,cy-5.2,cy+5.2,BACK+3.9,BACK+8.3))      # USB-C slot 10.4 x 4.4 (bottom edge clears the standoffs)
frame=clean(difference([frame]+cuts,engine='manifold'))
report('frame',frame); frame.export(OUT+'glow-grid_frame_v2.stl')

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
def extrude_x(poly,x0,x1):
    m=trimesh.creation.extrude_polygon(poly,x1-x0)          # local x=u, y=v, z=extrusion
    R=np.array([[0,0,1,x0],[1,0,0,0],[0,1,0,0],[0,0,0,1]],float)  # print: x=extrusion, y=u, z=v (proper rotation)
    m.apply_transform(R); return m
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
