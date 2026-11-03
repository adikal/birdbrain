"""Diagnostic (E-016): for picks in learned wall-owner lives, where the toy truly was
against where the duck believed it, and whether the owner liked it there. Truth is read
for evaluation only. Usage: scripts/owner_pick_probe.py (expects data/lifetimes/Cwall)."""
import math
import shutil
import tempfile
from pathlib import Path

from birdbrain.relations import wall_distance, where
from birdbrain.run import PlayroomSession

rows=[]
for life in (4,5,6,7):
    mem=Path(tempfile.mkdtemp())/'m'; shutil.copytree(f'data/lifetimes/Cwall/life-{life}', mem)
    s=PlayroomSession(9000+life, owner="wall", memory_dir=mem, episode=11, lifetime=life)
    seen=None
    while s.t<300:
        s.step()
        a=s.mind._action
        if a and a['skill']=='pick' and a['t0']!=seen:
            seen=a['t0']; x=a['args']['x']; kb=s.mind.kb; p=kb.position(x)
            room=s.owner_room()
            true=min(room.toys, key=lambda n: math.dist(room.toys[n],(p.x,p.y)))
            tp=room.toys[true]; b=s.bounds
            twall=min(tp[0]-b[0], b[2]-tp[0], tp[1]-b[1], b[3]-tp[1])
            liked=s.owner._likes(room,true,s.owner._start,0.2)
            rows.append((life, round(twall,3), round(wall_distance(kb,s.t,x),3), round(p.sigma,3), where(kb,s.t,x), liked, round(math.dist(tp,(p.x,p.y)),3)))
    s.close()
liked=[r for r in rows if r[5]]
print('picks',len(rows),'of liked toys',len(liked))
for r in liked: print(f'  true wall {r[1]:.2f} believed wall {r[2]:.2f} sigma {r[3]:.3f} desc {r[4]} err {r[6]:.2f}')
