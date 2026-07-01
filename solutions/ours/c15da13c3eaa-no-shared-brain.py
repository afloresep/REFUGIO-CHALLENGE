# Generated ablation: no-shared-brain
# Source baseline: solutions/public/c15da13c3eaa.py
# Hypothesis: Measure how much score remains when act() cannot retain cross-robot or cross-tick module-global planner state.
"""REFUGIO Warehouse Challenge - centralized cooperative MAPF."""
from __future__ import annotations
import heapq
import random
from collections import deque
import numpy as np
from warehouse_api import Action, CellType, Observation

GRID = 52
WALK_MIN = 1
WALK_MAX = 50
INF = 1 << 29
RNG_SEED = -1
JITTER = 0.0
_RNG = None

WINDOW = 35
NODE_CAP = 2500
WAIT_CAP = 30
FLOW_PENALTY = 0.1
BW, BH, MARGIN = 2, 2, 1
LO = 1 + MARGIN
PERIOD_X, PERIOD_Y = BW + 1, BH + 1
REMOVAL = "entry"  # spread | entry | central

# Tune the planner per starting scenario. The first robot's first target is a
# stable signature of the initial demand, so we pick the WINDOW/FLOW that this
# planner handles best for each known scenario; anything else falls back to a
# robust default. (Generalizes the "starting-scenario fast path" other entries use.)
SEED_CONFIGS = {
    (14, 42): (34, 0.1),
    (12, 33): (32, 0.06),
    (26, 47): (32, 0.06),
}
JITTER_CONFIGS = {
    (14, 42): (1, 0.05),
    (12, 33): (13, 0.05),
}
DEFAULT_CFG = (34, 0.10)     # robust fallback = 2x2/m1/entry single-config (922)
DEFAULT_JITTER = (-1, 0.0)

def _select_config(rid0_target):
    global WINDOW, FLOW_PENALTY, RNG_SEED, JITTER
    key = tuple(rid0_target) if rid0_target is not None else None
    WINDOW, FLOW_PENALTY = SEED_CONFIGS.get(key, DEFAULT_CFG)
    RNG_SEED, JITTER = JITTER_CONFIGS.get(key, DEFAULT_JITTER)

_DIRS = ((Action.UP,0,-1),(Action.DOWN,0,1),(Action.LEFT,-1,0),(Action.RIGHT,1,0))

def _node(x, y): return y * GRID + x

def _base_entry_cells():
    e=set()
    for x in range(3,50,2): e.add((x,1))
    for x in range(2,49,2): e.add((x,50))
    for y in range(2,49,2): e.add((1,y))
    for y in range(3,50,2): e.add((50,y))
    return e

def create_layout():
    return {'schema_version': 1, 'shelves': [[20, 2], [21, 2], [23, 2], [24, 2], [26, 2], [27, 2], [29, 2], [30, 2], [32, 2], [33, 2], [35, 2], [36, 2], [38, 2], [39, 2], [48, 2], [9, 3], [15, 3], [17, 3], [18, 3], [20, 3], [21, 3], [23, 3], [24, 3], [26, 3], [33, 3], [35, 3], [36, 3], [38, 3], [39, 3], [41, 3], [42, 3], [44, 3], [45, 3], [47, 3], [48, 3], [6, 4], [8, 4], [9, 4], [12, 4], [14, 4], [15, 4], [17, 4], [18, 4], [21, 4], [23, 4], [24, 4], [26, 4], [27, 4], [30, 4], [32, 4], [33, 4], [35, 4], [36, 4], [38, 4], [2, 5], [3, 5], [5, 5], [6, 5], [8, 5], [9, 5], [17, 5], [18, 5], [20, 5], [21, 5], [23, 5], [24, 5], [26, 5], [27, 5], [29, 5], [30, 5], [32, 5], [33, 5], [35, 5], [36, 5], [38, 5], [39, 5], [41, 5], [42, 5], [44, 5], [45, 5], [2, 7], [3, 7], [5, 7], [6, 7], [8, 7], [9, 7], [11, 7], [12, 7], [14, 7], [15, 7], [17, 7], [18, 7], [20, 7], [21, 7], [23, 7], [24, 7], [26, 7], [27, 7], [29, 7], [30, 7], [42, 7], [45, 7], [48, 7], [2, 8], [3, 8], [5, 8], [6, 8], [8, 8], [9, 8], [11, 8], [12, 8], [14, 8], [15, 8], [18, 8], [20, 8], [21, 8], [23, 8], [24, 8], [26, 8], [27, 8], [29, 8], [30, 8], [32, 8], [33, 8], [35, 8], [36, 8], [38, 8], [39, 8], [42, 8], [44, 8], [45, 8], [47, 8], [48, 8], [2, 9], [3, 9], [5, 9], [9, 9], [11, 9], [12, 9], [14, 9], [15, 9], [17, 9], [18, 9], [20, 9], [24, 9], [26, 9], [33, 9], [35, 9], [42, 9], [45, 9], [47, 9], [48, 9], [3, 10], [5, 10], [6, 10], [8, 10], [9, 10], [11, 10], [12, 10], [14, 10], [15, 10], [17, 10], [18, 10], [20, 10], [21, 10], [23, 10], [24, 10], [26, 10], [27, 10], [29, 10], [30, 10], [32, 10], [33, 10], [35, 10], [36, 10], [38, 10], [39, 10], [41, 10], [42, 10], [44, 10], [45, 10], [47, 10], [2, 12], [3, 12], [11, 12], [12, 12], [14, 12], [15, 12], [17, 12], [20, 12], [32, 12], [33, 12], [35, 12], [36, 12], [38, 12], [39, 12], [41, 12], [42, 12], [44, 12], [45, 12], [2, 13], [3, 13], [5, 13], [6, 13], [9, 13], [11, 13], [12, 13], [14, 13], [15, 13], [18, 13], [20, 13], [21, 13], [23, 13], [24, 13], [42, 13], [44, 13], [45, 13], [9, 14], [11, 14], [15, 14], [17, 14], [18, 14], [20, 14], [21, 14], [23, 14], [24, 14], [26, 14], [27, 14], [29, 14], [30, 14], [32, 14], [33, 14], [35, 14], [36, 14], [38, 14], [39, 14], [41, 14], [42, 14], [44, 14], [45, 14], [47, 14], [48, 14], [2, 15], [3, 15], [5, 15], [6, 15], [8, 15], [9, 15], [11, 15], [12, 15], [14, 15], [15, 15], [17, 15], [18, 15], [20, 15], [21, 15], [23, 15], [24, 15], [26, 15], [27, 15], [29, 15], [30, 15], [32, 15], [33, 15], [35, 15], [36, 15], [38, 15], [39, 15], [41, 15], [42, 15], [44, 15], [45, 15], [47, 15], [48, 15], [2, 17], [3, 17], [5, 17], [6, 17], [8, 17], [9, 17], [11, 17], [12, 17], [14, 17], [15, 17], [17, 17], [18, 17], [20, 17], [21, 17], [23, 17], [24, 17], [26, 17], [27, 17], [29, 17], [30, 17], [32, 17], [33, 17], [35, 17], [36, 17], [38, 17], [39, 17], [41, 17], [42, 17], [44, 17], [45, 17], [48, 17], [2, 18], [3, 18], [5, 18], [6, 18], [8, 18], [9, 18], [11, 18], [12, 18], [14, 18], [15, 18], [17, 18], [18, 18], [20, 18], [21, 18], [23, 18], [24, 18], [26, 18], [27, 18], [29, 18], [30, 18], [32, 18], [33, 18], [35, 18], [36, 18], [38, 18], [39, 18], [41, 18], [42, 18], [44, 18], [45, 18], [48, 18], [2, 19], [3, 19], [6, 19], [8, 19], [9, 19], [11, 19], [12, 19], [15, 19], [18, 19], [20, 19], [21, 19], [23, 19], [24, 19], [26, 19], [27, 19], [29, 19], [30, 19], [32, 19], [33, 19], [35, 19], [36, 19], [38, 19], [39, 19], [41, 19], [42, 19], [44, 19], [45, 19], [47, 19], [48, 19], [8, 20], [9, 20], [11, 20], [12, 20], [14, 20], [15, 20], [17, 20], [18, 20], [20, 20], [21, 20], [23, 20], [24, 20], [26, 20], [27, 20], [29, 20], [30, 20], [32, 20], [33, 20], [35, 20], [36, 20], [38, 20], [39, 20], [41, 20], [42, 20], [44, 20], [45, 20], [47, 20], [48, 20], [2, 22], [3, 22], [5, 22], [6, 22], [8, 22], [9, 22], [11, 22], [12, 22], [14, 22], [15, 22], [17, 22], [18, 22], [20, 22], [21, 22], [23, 22], [24, 22], [26, 22], [27, 22], [29, 22], [30, 22], [32, 22], [33, 22], [35, 22], [36, 22], [38, 22], [39, 22], [41, 22], [42, 22], [44, 22], [45, 22], [47, 22], [48, 22], [2, 23], [3, 23], [5, 23], [6, 23], [8, 23], [9, 23], [11, 23], [12, 23], [14, 23], [15, 23], [17, 23], [18, 23], [20, 23], [21, 23], [23, 23], [24, 23], [26, 23], [27, 23], [29, 23], [30, 23], [32, 23], [33, 23], [35, 23], [36, 23], [38, 23], [39, 23], [41, 23], [42, 23], [44, 23], [45, 23], [48, 23], [9, 24], [21, 24], [23, 24], [24, 24], [26, 24], [27, 24], [29, 24], [30, 24], [32, 24], [33, 24], [35, 24], [36, 24], [38, 24], [42, 24], [44, 24], [2, 25], [3, 25], [5, 25], [6, 25], [8, 25], [9, 25], [11, 25], [12, 25], [14, 25], [15, 25], [17, 25], [18, 25], [20, 25], [21, 25], [23, 25], [24, 25], [26, 25], [27, 25], [29, 25], [30, 25], [32, 25], [33, 25], [35, 25], [36, 25], [38, 25], [39, 25], [41, 25], [42, 25], [44, 25], [45, 25], [47, 25], [48, 25], [2, 27], [3, 27], [5, 27], [6, 27], [8, 27], [9, 27], [11, 27], [12, 27], [14, 27], [15, 27], [17, 27], [20, 27], [21, 27], [23, 27], [45, 27], [47, 27], [48, 27], [2, 28], [3, 28], [5, 28], [6, 28], [8, 28], [12, 28], [14, 28], [15, 28], [17, 28], [18, 28], [20, 28], [21, 28], [23, 28], [24, 28], [26, 28], [27, 28], [29, 28], [30, 28], [32, 28], [33, 28], [36, 28], [38, 28], [42, 28], [44, 28], [45, 28], [47, 28], [2, 29], [3, 29], [5, 29], [6, 29], [9, 29], [11, 29], [12, 29], [14, 29], [15, 29], [17, 29], [18, 29], [20, 29], [21, 29], [23, 29], [24, 29], [26, 29], [27, 29], [29, 29], [30, 29], [32, 29], [33, 29], [35, 29], [36, 29], [38, 29], [39, 29], [41, 29], [42, 29], [44, 29], [45, 29], [47, 29], [48, 29], [2, 30], [3, 30], [5, 30], [6, 30], [8, 30], [9, 30], [11, 30], [12, 30], [14, 30], [15, 30], [17, 30], [18, 30], [21, 30], [23, 30], [24, 30], [26, 30], [27, 30], [29, 30], [30, 30], [32, 30], [33, 30], [35, 30], [36, 30], [39, 30], [41, 30], [2, 32], [3, 32], [5, 32], [18, 32], [20, 32], [21, 32], [23, 32], [24, 32], [26, 32], [27, 32], [29, 32], [30, 32], [32, 32], [33, 32], [35, 32], [36, 32], [38, 32], [39, 32], [41, 32], [2, 33], [3, 33], [5, 33], [6, 33], [8, 33], [9, 33], [11, 33], [12, 33], [14, 33], [15, 33], [17, 33], [18, 33], [20, 33], [21, 33], [23, 33], [24, 33], [26, 33], [27, 33], [29, 33], [30, 33], [32, 33], [33, 33], [35, 33], [36, 33], [38, 33], [39, 33], [41, 33], [42, 33], [44, 33], [45, 33], [47, 33], [48, 33], [3, 34], [5, 34], [6, 34], [8, 34], [9, 34], [11, 34], [12, 34], [14, 34], [15, 34], [17, 34], [18, 34], [20, 34], [21, 34], [23, 34], [24, 34], [26, 34], [27, 34], [29, 34], [30, 34], [32, 34], [33, 34], [35, 34], [36, 34], [38, 34], [39, 34], [41, 34], [42, 34], [44, 34], [45, 34], [47, 34], [48, 34], [2, 35], [3, 35], [5, 35], [6, 35], [8, 35], [9, 35], [11, 35], [12, 35], [14, 35], [15, 35], [17, 35], [18, 35], [20, 35], [21, 35], [23, 35], [24, 35], [26, 35], [27, 35], [29, 35], [30, 35], [32, 35], [33, 35], [35, 35], [36, 35], [38, 35], [39, 35], [41, 35], [42, 35], [44, 35], [45, 35], [18, 37], [21, 37], [23, 37], [24, 37], [26, 37], [27, 37], [29, 37], [30, 37], [32, 37], [33, 37], [35, 37], [36, 37], [38, 37], [39, 37], [41, 37], [42, 37], [44, 37], [45, 37], [47, 37], [48, 37], [3, 38], [5, 38], [6, 38], [9, 38], [11, 38], [12, 38], [14, 38], [15, 38], [17, 38], [18, 38], [20, 38], [21, 38], [23, 38], [24, 38], [26, 38], [27, 38], [29, 38], [30, 38], [32, 38], [33, 38], [35, 38], [36, 38], [38, 38], [39, 38], [41, 38], [42, 38], [44, 38], [45, 38], [47, 38], [48, 38], [2, 39], [3, 39], [5, 39], [6, 39], [8, 39], [9, 39], [11, 39], [12, 39], [15, 39], [17, 39], [18, 39], [20, 39], [21, 39], [23, 39], [24, 39], [26, 39], [27, 39], [29, 39], [30, 39], [32, 39], [33, 39], [35, 39], [36, 39], [38, 39], [39, 39], [41, 39], [42, 39], [44, 39], [45, 39], [2, 40], [3, 40], [5, 40], [6, 40], [8, 40], [9, 40], [11, 40], [12, 40], [14, 40], [15, 40], [17, 40], [18, 40], [20, 40], [21, 40], [23, 40], [24, 40], [26, 40], [27, 40], [29, 40], [30, 40], [32, 40], [33, 40], [35, 40], [36, 40], [38, 40], [39, 40], [41, 40], [2, 42], [3, 42], [5, 42], [6, 42], [8, 42], [9, 42], [11, 42], [12, 42], [14, 42], [15, 42], [17, 42], [18, 42], [20, 42], [21, 42], [23, 42], [24, 42], [26, 42], [27, 42], [29, 42], [30, 42], [32, 42], [33, 42], [35, 42], [36, 42], [38, 42], [41, 42], [42, 42], [44, 42], [45, 42], [47, 42], [48, 42], [12, 43], [14, 43], [21, 43], [24, 43], [26, 43], [27, 43], [30, 43], [32, 43], [33, 43], [35, 43], [36, 43], [2, 44], [3, 44], [6, 44], [8, 44], [9, 44], [11, 44], [12, 44], [14, 44], [15, 44], [17, 44], [18, 44], [20, 44], [21, 44], [23, 44], [24, 44], [26, 44], [27, 44], [29, 44], [30, 44], [32, 44], [33, 44], [35, 44], [36, 44], [38, 44], [39, 44], [41, 44], [42, 44], [44, 44], [45, 44], [47, 44], [48, 44], [3, 45], [5, 45], [6, 45], [12, 45], [14, 45], [15, 45], [18, 45], [20, 45], [38, 45], [39, 45], [41, 45], [42, 45], [44, 45], [45, 45], [47, 45], [48, 45], [2, 47], [3, 47], [8, 47], [21, 47], [23, 47], [24, 47], [26, 47], [27, 47], [29, 47], [30, 47], [32, 47], [44, 47], [45, 47], [47, 47], [48, 47], [2, 48], [3, 48], [15, 48], [18, 48], [20, 48], [21, 48], [23, 48], [24, 48], [26, 48], [27, 48], [29, 48], [30, 48], [32, 48], [33, 48], [35, 48], [36, 48], [38, 48], [39, 48], [41, 48], [42, 48], [44, 48], [45, 48], [47, 48], [48, 48], [2, 49], [3, 49], [15, 49], [17, 49], [18, 49], [20, 49], [21, 49], [24, 49], [26, 49], [27, 49], [45, 49], [47, 49]]}

def _base_entry(bx, by):
    if bx==0: return (1,by)
    if bx==GRID-1: return (GRID-2,by)
    if by==0: return (bx,1)
    return (bx, GRID-2)

def _adjacent(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])==1

def _flow(x, y, nx, ny):
    """Period-aware soft one-way bias. Returns penalty for moving x,y -> nx,ny."""
    if x == nx and (x - LO) % PERIOD_X == BW:
        col_idx = (x - LO) // PERIOD_X
        if col_idx % 2 == 0 and ny > y: return FLOW_PENALTY
        if col_idx % 2 == 1 and ny < y: return FLOW_PENALTY
    if y == ny and (y - LO) % PERIOD_Y == BH:
        row_idx = (y - LO) // PERIOD_Y
        if row_idx % 2 == 0 and nx > x: return FLOW_PENALTY
        if row_idx % 2 == 1 and nx < x: return FLOW_PENALTY
    if y == 2 and nx > x: return FLOW_PENALTY
    if y == 49 and nx < x: return FLOW_PENALTY
    if x == 2 and ny > y: return FLOW_PENALTY
    if x == 49 and ny < y: return FLOW_PENALTY
    return 0.0

class _World:
    __slots__=("passable","nbrs","dist_cache","flow_costs")
    def __init__(self, grid):
        self.passable=np.zeros(GRID*GRID, dtype=bool)
        for y in range(WALK_MIN, WALK_MAX+1):
            row=grid[y]
            for x in range(WALK_MIN, WALK_MAX+1):
                if row[x]==CellType.EMPTY: self.passable[_node(x,y)]=True
        nbrs={}; flow_costs={}; passable=self.passable
        for y in range(WALK_MIN, WALK_MAX+1):
            for x in range(WALK_MIN, WALK_MAX+1):
                u=_node(x,y)
                if not passable[u]: continue
                lst=[]
                for action,dx,dy in _DIRS:
                    nx,ny=x+dx,y+dy
                    if WALK_MIN<=nx<=WALK_MAX and WALK_MIN<=ny<=WALK_MAX:
                        v=_node(nx,ny)
                        if passable[v]:
                            lst.append((action,v))
                            if FLOW_PENALTY>0:
                                p=_flow(x,y,nx,ny)
                                if p>0: flow_costs[(u,v)]=p
                nbrs[u]=tuple(lst)
        self.nbrs=nbrs; self.flow_costs=flow_costs; self.dist_cache={}
    def _bfs(self, sources):
        dist=np.full(GRID*GRID, INF, dtype=np.int32); dq=deque()
        for s in sources:
            if dist[s]!=0: dist[s]=0; dq.append(s)
        nbrs=self.nbrs
        while dq:
            u=dq.popleft(); du=dist[u]+1
            for _a,v in nbrs[u]:
                if dist[v]>du: dist[v]=du; dq.append(v)
        return dist
    def base_field(self, en):
        k=("B",en); f=self.dist_cache.get(k)
        if f is None: f=self._bfs([en]); self.dist_cache[k]=f
        return f
    def shelf_field(self, shelf):
        k=("S",shelf); f=self.dist_cache.get(k)
        if f is None:
            sx,sy=shelf; src=[]
            for _a,dx,dy in _DIRS:
                nx,ny=sx+dx,sy+dy
                if WALK_MIN<=nx<=WALK_MAX and WALK_MIN<=ny<=WALK_MAX:
                    m=_node(nx,ny)
                    if self.passable[m]: src.append(m)
            f=self._bfs(src); self.dist_cache[k]=f
        return f

class _Brain:
    __slots__=("world","cur_tick","pos","base","entry","target","carrying","wait_streak","moves","locked","occupied","need_greedy","next_claimed","plan_final","plan_start")
    def __init__(self):
        self.world=None; self.cur_tick=None
        self.pos={}; self.base={}; self.entry={}; self.target={}; self.carrying={}
        self.wait_streak={}; self.moves={}
        self.locked=frozenset(); self.occupied=frozenset(); self.need_greedy=frozenset()
        self.next_claimed=set(); self.plan_final={}; self.plan_start={}
    def reset_episode(self):
        self.cur_tick=None
        for d in (self.pos,self.base,self.entry,self.target,self.carrying,self.wait_streak,self.moves):
            d.clear()
        self.locked=frozenset(); self.occupied=frozenset(); self.need_greedy=frozenset()
        self.next_claimed=set(); self.plan_final={}; self.plan_start={}

# Ablation: do not keep a module-global _BRAIN.
# Each act() call builds a fresh local brain. Other robots are visible only
# as current positions from observation.all_robot_positions, with no remembered
# targets, carrying state, wait streaks, or future plan from previous calls.
def act(observation):
    try: return _act_memoryless(observation)
    except Exception: return Action.WAIT

def _act_memoryless(obs):
    brain=_Brain()
    global WINDOW, FLOW_PENALTY, RNG_SEED, JITTER, _RNG
    WINDOW, FLOW_PENALTY = DEFAULT_CFG
    RNG_SEED, JITTER = DEFAULT_JITTER
    _RNG = None
    brain.world = _World(obs.grid)
    brain.cur_tick = obs.tick
    try: _plan(brain,obs)
    except Exception: brain.moves={}
    return _action_for(brain,obs)

def _plan(brain, obs0):
    world=brain.world; positions=obs0.all_robot_positions
    r0=obs0.robot_id
    brain.pos[r0]=obs0.position; brain.base[r0]=obs0.base_position
    brain.entry[r0]=_node(*_base_entry(*obs0.base_position))
    brain.target[r0]=obs0.target_item_position; brain.carrying[r0]=obs0.carrying_item
    for rid,xy in positions.items(): brain.pos[rid]=(xy[0],xy[1])
    rids=sorted(positions)
    brain.occupied=frozenset(brain.pos[rid] for rid in rids)
    brain.locked=frozenset(t for rid in rids if brain.carrying.get(rid) and (t:=brain.target.get(rid)) is not None)
    stayers=[]; movers=[]; need_greedy=[]; goal_field={}
    for rid in rids:
        cur=brain.pos[rid]; node=_node(*cur); carrying=brain.carrying.get(rid,False)
        if carrying:
            entry=brain.entry.get(rid)
            if entry is None: stayers.append(rid); continue
            field=world.base_field(entry)
            if node==entry: stayers.append(rid); continue
        else:
            target=brain.target.get(rid)
            if target is None: stayers.append(rid); need_greedy.append(rid); continue
            field=world.shelf_field(target)
            if int(field[node])==0: stayers.append(rid); continue
        if int(field[node])>=INF: stayers.append(rid); continue
        goal_field[rid]=field; movers.append(rid)
    brain.need_greedy=frozenset(need_greedy)
    cell_res={}; edge_res={}
    for rid in stayers:
        n=_node(*brain.pos[rid])
        for t in range(WINDOW+1): cell_res[(t,n)]=rid
    def priority(rid):
        carrying=brain.carrying.get(rid,False); pos=brain.pos[rid]; node=_node(*pos)
        remaining=int(goal_field[rid][node]); boost=min(brain.wait_streak.get(rid,0),WAIT_CAP)
        dc=abs(pos[0]-25)+abs(pos[1]-25)
        j = _RNG.uniform(-JITTER, JITTER) if _RNG is not None else 0.0
        return (0 if carrying else 1, remaining + j, -boost, rid)
    movers.sort(key=priority)
    desired={rid:_node(*brain.pos[rid]) for rid in rids}
    for rid in movers:
        start=_node(*brain.pos[rid])
        path=_astar(world,start,goal_field[rid],cell_res,edge_res)
        if path is None or len(path)<2:
            desired[rid]=start
            for t in range(WINDOW+1): cell_res.setdefault((t,start),rid)
            continue
        desired[rid]=path[1]; last=len(path)-1
        for i in range(min(last,WINDOW)+1): cell_res[(i,path[i])]=rid
        for i in range(min(last,WINDOW)): edge_res[(i,path[i],path[i+1])]=rid
        for t in range(last+1,WINDOW+1): cell_res[(t,path[last])]=rid
    order=stayers+movers
    final=_resolve_first_moves(brain,desired,order)
    moves={}; start_nodes={}
    for rid in rids:
        u=_node(*brain.pos[rid]); v=final[rid]; start_nodes[rid]=u
        moves[rid]=_delta_action(u,v)
        brain.wait_streak[rid]=0 if v!=u else brain.wait_streak.get(rid,0)+1
    brain.moves=moves; brain.plan_final=dict(final); brain.plan_start=start_nodes
    brain.next_claimed=set(final.values())

def _astar(world, start, field, cell_res, edge_res):
    if int(field[start])>=INF: return None
    if int(field[start])==0: return [start]
    nbrs=world.nbrs; flow_costs=world.flow_costs
    open_heap=[(float(field[start]),0,start,0)]; came={}; gbest={(start,0):0.0}
    expansions=0; goal_state=None
    while open_heap:
        f,g,n,t=heapq.heappop(open_heap)
        if g>gbest.get((n,t),INF): continue
        if int(field[n])==0: goal_state=(n,t); break
        expansions+=1
        if expansions>NODE_CAP: break
        nt=t+1; within=nt<=WINDOW
        for action,m in nbrs[n]:
            if within and ((nt,m) in cell_res or (t,m,n) in edge_res): continue
            ng=g+1.0+flow_costs.get((n,m),0.0); key=(m,nt)
            if ng<gbest.get(key,INF):
                gbest[key]=ng; came[key]=(n,t); heapq.heappush(open_heap,(ng+float(field[m]),ng,m,nt))
        if not (within and (nt,n) in cell_res):
            ng=g+1.01; key=(n,nt)
            if ng<gbest.get(key,INF):
                gbest[key]=ng; came[key]=(n,t); heapq.heappush(open_heap,(ng+float(field[n]),ng,n,nt))
    if goal_state is None: return None
    path=[]; state=goal_state
    while state in came: path.append(state[0]); state=came[state]
    path.append(start); path.reverse(); return path

def _resolve_first_moves(brain, desired, order):
    cur={rid:_node(*brain.pos[rid]) for rid in desired}; final=dict(desired)
    by_cur={cur[rid]:rid for rid in desired}
    for rid in order:
        u,v=cur[rid],final[rid]
        if v==u: continue
        other=by_cur.get(v)
        if other is not None and other!=rid and final.get(other)==u:
            final[rid]=u; final[other]=cur[other]
    occ={}; blocked=set()
    for rid in order:
        v=final[rid]
        if v in occ: final[rid]=cur[rid]; blocked.add(rid)
        else:
            occ[v]=rid
            if v==cur[rid]: blocked.add(rid)
    world=brain.world
    for rid in order:
        if rid not in blocked or final[rid]!=cur[rid]: continue
        if desired[rid]==cur[rid]: continue
        u=cur[rid]
        for _,v in world.nbrs[u]:
            if v not in occ:
                swap=False; other_rid=by_cur.get(v)
                if other_rid is not None and final[other_rid]==u: swap=True
                if not swap: final[rid]=v; occ[v]=rid; break
    return final

def _delta_action(u, v):
    if u==v: return Action.WAIT
    dx=(v%GRID)-(u%GRID)
    if dx==1: return Action.RIGHT
    if dx==-1: return Action.LEFT
    return Action.DOWN if (v//GRID)-(u//GRID)==1 else Action.UP

def _action_for(brain, obs):
    rid=obs.robot_id; pos=obs.position; target=obs.target_item_position; carrying=obs.carrying_item
    brain.pos[rid]=pos; brain.base[rid]=obs.base_position
    entry_xy=_base_entry(*obs.base_position); brain.entry[rid]=_node(*entry_xy)
    brain.target[rid]=target; brain.carrying[rid]=carrying
    if carrying:
        if pos==entry_xy:
            brain.carrying[rid]=False; brain.target[rid]=None; return Action.DROP
    else:
        if _adjacent(pos,target) and target not in brain.locked:
            brain.carrying[rid]=True; return Action.PICKUP
    move=brain.moves.get(rid)
    if move is None or (move==Action.WAIT and rid in brain.need_greedy):
        move=_coordinated_step(brain,obs)
    return move

def _coordinated_step(brain, obs):
    world=brain.world; rid=obs.robot_id; x,y=obs.position; cnode=_node(x,y)
    if obs.carrying_item: field=world.base_field(_node(*_base_entry(*obs.base_position)))
    else:
        target=obs.target_item_position
        if target is None: return Action.WAIT
        field=world.shelf_field(target)
    claimed=brain.next_claimed; plan_final=brain.plan_final; plan_start=brain.plan_start
    best_action=Action.WAIT; best_node=cnode; best_key=(int(field[cnode]),y,x)
    for action,dx,dy in _DIRS:
        nx,ny=x+dx,y+dy
        if not (WALK_MIN<=nx<=WALK_MAX and WALK_MIN<=ny<=WALK_MAX): continue
        m=_node(nx,ny)
        if not world.passable[m]: continue
        if m!=cnode and m in claimed: continue
        swap=False
        for orid,fnode in plan_final.items():
            if orid!=rid and fnode==cnode and plan_start.get(orid)==m: swap=True; break
        if swap: continue
        key=(int(field[m]),ny,nx)
        if key<best_key: best_key=key; best_action=action; best_node=m
    if best_node!=cnode:
        claimed.discard(cnode); claimed.add(best_node)
        plan_final[rid]=best_node; plan_start[rid]=cnode
    return best_action
