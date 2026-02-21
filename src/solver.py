from __future__ import annotations

from typing import List, Optional, Sequence, Set, Tuple


def solve_sat(
    num_vars: int,
    clauses_as_sets: Sequence[Set[int]],
    active_vars: Optional[Set[int]] = None,
) -> Tuple[bool, List[int]]:
    """
    Returns (is_sat, assignment) where assignment is a list length num_vars+1 with values in {-1,0,1}.
    clauses_as_sets: list of clauses, each clause is a set of ints (literals)
    active_vars: vars that appear in the CNF (recommended). If None, inferred from clauses.
    """
    clauses: List[List[int]] = []
    vars_seen: Set[int] = set()

    # Preprocess: remove tautological clauses, ignore 0s, keep unique literals
    for cset in clauses_as_sets:
        if not cset:
            return False, [0] * (num_vars + 1)

        # tautology: (x OR ~x OR ...) always satisfied
        if any((-lit) in cset for lit in cset):
            continue

        lits = [lit for lit in cset if lit != 0]
        if not lits:
            return False, [0] * (num_vars + 1)

        clauses.append(lits)
        for lit in lits:
            vars_seen.add(abs(lit))

    if active_vars is None:
        active = sorted(vars_seen)
    else:
        active = sorted(set(active_vars) & vars_seen)

    if not clauses:
        return True, [0] * (num_vars + 1)

    solver = _DPLLSolver(num_vars=num_vars, clauses=clauses, active_vars=active)
    sat = solver.solve()
    return sat, solver.assignment


class _DPLLSolver:
    """
    DPLL with two-watched-literals propagation.
    No clause learning; good enough to solve toys and many medium instances.
    """

    def __init__(self, num_vars: int, clauses: List[List[int]], active_vars: List[int]) -> None:
        self.n = num_vars
        self.clauses = clauses
        self.active_vars = active_vars

        # assignment[var] in {-1,0,1} = {False, Unassigned, True}
        self.assignment: List[int] = [0] * (self.n + 1)

        # trail-based propagation
        self.trail: List[int] = []
        self.trail_lim: List[int] = []
        self.qhead: int = 0

        # simple branching heuristic: occurrence counts (computed once)
        self.pos_count = [0] * (self.n + 1)
        self.neg_count = [0] * (self.n + 1)
        for cl in self.clauses:
            for lit in cl:
                v = abs(lit)
                if lit > 0:
                    self.pos_count[v] += 1
                else:
                    self.neg_count[v] += 1

        # watched literals
        self.watches: List[Tuple[int, int]] = []  # per clause: (idx1, idx2) in clause list
        self.watchlist: List[List[int]] = [[] for _ in range(2 * self.n + 1)]  # lit -> [clause_ids]
        self._init_watches()

    def _lit_idx(self, lit: int) -> int:
        # lit in [-n, n], lit != 0
        return lit + self.n

    def _lit_value(self, lit: int) -> int:
        v = abs(lit)
        av = self.assignment[v]
        if av == 0:
            return 0
        if (av == 1 and lit > 0) or (av == -1 and lit < 0):
            return 1
        return -1

    def _assign(self, lit: int) -> bool:
        v = abs(lit)
        val = 1 if lit > 0 else -1
        cur = self.assignment[v]
        if cur != 0:
            return cur == val
        self.assignment[v] = val
        self.trail.append(lit)
        return True

    def _unassign_to(self, trail_sz: int) -> None:
        for i in range(len(self.trail) - 1, trail_sz - 1, -1):
            lit = self.trail[i]
            self.assignment[abs(lit)] = 0
        del self.trail[trail_sz:]
        self.qhead = min(self.qhead, trail_sz)

    def _new_decision_level(self) -> None:
        self.trail_lim.append(len(self.trail))

    def _backtrack(self) -> None:
        if not self.trail_lim:
            self._unassign_to(0)
            return
        lvl_start = self.trail_lim.pop()
        self._unassign_to(lvl_start)

    def _init_watches(self) -> None:
        for cid, cl in enumerate(self.clauses):
            if len(cl) == 1:
                self.watches.append((0, 0))
                self.watchlist[self._lit_idx(cl[0])].append(cid)
            else:
                self.watches.append((0, 1))
                self.watchlist[self._lit_idx(cl[0])].append(cid)
                self.watchlist[self._lit_idx(cl[1])].append(cid)

    def _propagate(self) -> bool:
        # returns True if conflict
        while self.qhead < len(self.trail):
            lit = self.trail[self.qhead]
            self.qhead += 1
            false_lit = -lit

            wl = self.watchlist[self._lit_idx(false_lit)]
            i = 0
            while i < len(wl):
                cid = wl[i]
                cl = self.clauses[cid]
                w1, w2 = self.watches[cid]

                if cl[w1] == false_lit:
                    fpos, opos = w1, w2
                elif cl[w2] == false_lit:
                    fpos, opos = w2, w1
                else:
                    # stale entry (should be rare); skip
                    i += 1
                    continue

                other_lit = cl[opos]
                if self._lit_value(other_lit) == 1:
                    i += 1
                    continue

                # try to find a replacement watch that is not FALSE
                found = False
                for k, cand in enumerate(cl):
                    if k == opos or k == fpos:
                        continue
                    if self._lit_value(cand) != -1:
                        # move watch from false_lit to cand
                        if fpos == w1:
                            self.watches[cid] = (k, opos)
                        else:
                            self.watches[cid] = (opos, k)

                        # swap-pop remove cid from this watchlist and add to new one
                        wl[i] = wl[-1]
                        wl.pop()
                        self.watchlist[self._lit_idx(cand)].append(cid)
                        found = True
                        break

                if found:
                    continue

                # no replacement: unit or conflict
                if self._lit_value(other_lit) == -1:
                    return True  # conflict

                # unit: force other_lit to True
                if not self._assign(other_lit):
                    return True
                i += 1

        return False

    def _pick_branch_var(self) -> Optional[int]:
        best_v = None
        best_score = -1
        for v in self.active_vars:
            if self.assignment[v] != 0:
                continue
            score = self.pos_count[v] + self.neg_count[v]
            if score > best_score:
                best_score = score
                best_v = v
        return best_v

    def solve(self) -> bool:
        # enqueue unit clauses
        for cl in self.clauses:
            if len(cl) == 0:
                return False
            if len(cl) == 1:
                if not self._assign(cl[0]):
                    return False

        if self._propagate():
            return False
        return self._search()

    def _search(self) -> bool:
        if self._propagate():
            return False

        v = self._pick_branch_var()
        if v is None:
            return True  # all relevant vars assigned without conflict

        self._new_decision_level()
        lvl_start = self.trail_lim[-1]

        prefer_pos = self.pos_count[v] >= self.neg_count[v]
        branch_lits = (v if prefer_pos else -v, -v if prefer_pos else v)

        for blit in branch_lits:
            if self._assign(blit):
                if self._search():
                    return True
            self._unassign_to(lvl_start)

        self._backtrack()
        return False
