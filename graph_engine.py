"""
Graph engine for the Student Community Detector.

Students are vertices. Two students are connected when the Jaccard similarity
of their interest sets reaches a threshold. Communities are the connected
components of that graph, found with either BFS or DFS (both give the same
partition; they differ in the order they visit students, which the web UI
animates). DFS is also used for Tarjan's algorithm to find bridge students
(articulation points) and bridge links.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass


@dataclass
class Student:
    id: int
    name: str
    department: str
    year: int
    interests: frozenset

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "department": self.department,
            "year": self.year,
            "interests": sorted(self.interests),
        }


def jaccard(a, b) -> float:
    """Jaccard similarity of two sets: |A & B| / |A | B|."""
    union = len(a | b)
    return len(a & b) / union if union else 0.0


class StudentGraph:
    def __init__(self, students, threshold: float = 0.25):
        self.students = {s.id: s for s in students}
        self.threshold = threshold
        self.adj = {sid: {} for sid in self.students}  # id -> {neighbour id: weight}
        self._build()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        ids = sorted(self.students)
        for i, a in enumerate(ids):
            ia = self.students[a].interests
            for b in ids[i + 1:]:
                w = jaccard(ia, self.students[b].interests)
                if w >= self.threshold and w > 0:
                    self.adj[a][b] = w
                    self.adj[b][a] = w

    def edges(self):
        for a in sorted(self.adj):
            for b, w in sorted(self.adj[a].items()):
                if a < b:
                    yield a, b, w

    @property
    def edge_count(self) -> int:
        return sum(len(n) for n in self.adj.values()) // 2

    # -------------------------------------------------------------- traversals
    def bfs(self, start: int) -> dict:
        """Breadth-first search. Visits students in rings of increasing hop distance."""
        visited = {start}
        queue = deque([start])
        parent = {start: None}
        level = {start: 0}
        order = []
        while queue:
            u = queue.popleft()
            order.append(u)
            for v in sorted(self.adj[u]):
                if v not in visited:
                    visited.add(v)
                    parent[v] = u
                    level[v] = level[u] + 1
                    queue.append(v)
        return self._trace(order, parent, level)

    def dfs(self, start: int) -> dict:
        """Depth-first search (iterative, so large graphs cannot hit the recursion limit)."""
        visited = set()
        stack = [(start, None, 0)]
        parent, depth, order = {}, {}, []
        while stack:
            u, p, d = stack.pop()
            if u in visited:
                continue
            visited.add(u)
            parent[u], depth[u] = p, d
            order.append(u)
            # reversed so the smallest id is explored first
            for v in sorted(self.adj[u], reverse=True):
                if v not in visited:
                    stack.append((v, u, d + 1))
        return self._trace(order, parent, depth)

    @staticmethod
    def _trace(order, parent, level) -> dict:
        steps = [{"node": n, "from": parent[n], "level": level[n]} for n in order]
        return {"order": order, "parent": parent, "level": level, "steps": steps}

    def traverse(self, start: int, algo: str = "bfs") -> dict:
        return self.dfs(start) if algo == "dfs" else self.bfs(start)

    # ------------------------------------------------------------- communities
    def components(self, method: str = "bfs") -> list:
        """Connected components, largest first. Each is a list of student ids."""
        seen, comps = set(), []
        for s in sorted(self.adj):
            if s in seen:
                continue
            comp = self.traverse(s, method)["order"]
            seen.update(comp)
            comps.append(sorted(comp))
        comps.sort(key=lambda c: (-len(c), c[0]))
        return comps

    def shortest_path(self, src: int, dst: int):
        """Fewest-hops path between two students using BFS, or None if unreachable."""
        if src == dst:
            return [src]
        parent = {src: None}
        queue = deque([src])
        while queue:
            u = queue.popleft()
            for v in sorted(self.adj[u]):
                if v in parent:
                    continue
                parent[v] = u
                if v == dst:
                    path = [v]
                    while parent[path[-1]] is not None:
                        path.append(parent[path[-1]])
                    return path[::-1]
                queue.append(v)
        return None

    def cut_points_and_bridges(self):
        """Tarjan's DFS low-link algorithm (iterative, so long chains cannot
        overflow the stack).

        Returns (articulation points, bridge edges). Removing an articulation
        point splits its community; removing a bridge edge does the same.
        """
        disc, low, children = {}, {}, {}
        clock = 0
        points, bridges = set(), []

        for root in sorted(self.adj):
            if root in disc:
                continue
            disc[root] = low[root] = clock
            clock += 1
            children[root] = 0
            stack = [(root, None, iter(sorted(self.adj[root])))]
            while stack:
                u, parent, neighbours = stack[-1]
                descended = False
                for v in neighbours:
                    if v == parent:
                        continue
                    if v in disc:
                        low[u] = min(low[u], disc[v])
                    else:
                        children[u] += 1
                        disc[v] = low[v] = clock
                        clock += 1
                        children[v] = 0
                        stack.append((v, u, iter(sorted(self.adj[v]))))
                        descended = True
                        break
                if descended:
                    continue
                stack.pop()
                if stack:
                    p, p_parent, _ = stack[-1]
                    low[p] = min(low[p], low[u])
                    if p_parent is not None and low[u] >= disc[p]:
                        points.add(p)
                    if low[u] > disc[p]:
                        bridges.append((min(p, u), max(p, u)))
                elif children[u] > 1:
                    points.add(u)
        return points, sorted(bridges)

    # ----------------------------------------------------------------- metrics
    def modularity(self, comps) -> float:
        """Newman modularity of a partition (unweighted). Higher = clearer communities."""
        m = self.edge_count
        if m == 0:
            return 0.0
        q = 0.0
        for comp in comps:
            members = set(comp)
            inner = sum(1 for u in comp for v in self.adj[u] if v in members and u < v)
            degree_sum = sum(len(self.adj[u]) for u in comp)
            q += inner / m - (degree_sum / (2 * m)) ** 2
        return q

    def clustering(self, u: int) -> float:
        nbrs = list(self.adj[u])
        k = len(nbrs)
        if k < 2:
            return 0.0
        links = sum(1 for i in range(k) for j in range(i + 1, k) if nbrs[j] in self.adj[nbrs[i]])
        return 2 * links / (k * (k - 1))

    def summarize(self, comp, cid: int) -> dict:
        members = set(comp)
        interests = Counter(i for u in comp for i in self.students[u].interests)
        depts = Counter(self.students[u].department for u in comp)
        weights = [w for a, b, w in self.edges() if a in members and b in members]
        n = len(comp)
        possible = n * (n - 1) / 2
        hub = max(comp, key=lambda u: (len(self.adj[u]), -u))
        top = interests.most_common(5)
        if n == 1:
            label = "Independent"
        else:
            label = " & ".join(name.title() for name, _ in top[:2])
        return {
            "id": cid,
            "label": label,
            "size": n,
            "members": comp,
            "top_interests": [{"name": k, "count": v} for k, v in top],
            "departments": [{"name": k, "count": v} for k, v in depts.most_common()],
            "avg_similarity": round(sum(weights) / len(weights), 3) if weights else 0.0,
            "density": round(len(weights) / possible, 3) if possible else 0.0,
            "hub": hub,
        }

    # ----------------------------------------------------------- recommendation
    def recommend(self, sid: int, limit: int = 6) -> list:
        """Suggest students to meet: not yet connected, ranked by shared interests
        and mutual connections. Hop distance comes from a BFS."""
        me = self.students[sid]
        level = self.bfs(sid)["level"]
        scored = []
        for v, other in self.students.items():
            if v == sid or v in self.adj[sid]:
                continue
            shared = sorted(me.interests & other.interests)
            if not shared:
                continue
            mutual = sorted(set(self.adj[sid]) & set(self.adj[v]))
            sim = jaccard(me.interests, other.interests)
            scored.append({
                "id": v,
                "name": other.name,
                "similarity": round(sim, 3),
                "shared": shared,
                "mutual": [self.students[m].name for m in mutual],
                "hops": level.get(v),
                "score": sim + 0.05 * len(mutual),
            })
        scored.sort(key=lambda r: (-r["score"], r["id"]))
        for r in scored:
            del r["score"]
        return scored[:limit]

    # ----------------------------------------------------------------- payload
    def analyze(self, method: str = "bfs") -> dict:
        comps = self.components(method)
        points, bridges = self.cut_points_and_bridges()
        community_of = {u: i for i, comp in enumerate(comps) for u in comp}
        n = len(self.students)
        m = self.edge_count
        bridge_set = set(bridges)

        nodes = []
        for sid in sorted(self.students):
            d = self.students[sid].to_dict()
            d.update({
                "community": community_of[sid],
                "degree": len(self.adj[sid]),
                "clustering": round(self.clustering(sid), 3),
                "is_bridge": sid in points,
            })
            nodes.append(d)

        edges = [
            {"source": a, "target": b, "weight": round(w, 3), "is_bridge": (a, b) in bridge_set}
            for a, b, w in self.edges()
        ]
        summaries = [self.summarize(c, i) for i, c in enumerate(comps)]
        sizes = [len(c) for c in comps]
        stats = {
            "students": n,
            "connections": m,
            "communities": sum(1 for s in sizes if s > 1),
            "independent": sum(1 for s in sizes if s == 1),
            "largest": max(sizes) if sizes else 0,
            "avg_degree": round(2 * m / n, 2) if n else 0,
            "density": round(m / (n * (n - 1) / 2), 3) if n > 1 else 0,
            "modularity": round(self.modularity(comps), 3),
            "bridge_students": len(points),
        }
        return {
            "threshold": self.threshold,
            "method": method,
            "nodes": nodes,
            "edges": edges,
            "communities": summaries,
            "stats": stats,
        }
