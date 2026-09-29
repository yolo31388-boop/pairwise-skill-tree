"""技能树与天赋系统"""
from dataclasses import dataclass, field

# 减益/减免类效果的下限保护（最多减免80%）
REDUCTION_CAP = 0.8
REDUCTION_KEYWORDS = ("reduce", "reduction", "cd")


def _is_reduction_effect(effect_type: str) -> bool:
    name = effect_type.lower()
    return any(k in name for k in REDUCTION_KEYWORDS)


@dataclass
class Talent:
    tid: str
    name: str
    tier: int
    max_points: int = 1
    points: int = 0
    prereq: list = field(default_factory=list)
    mutex_group: str = ""  # 同组互斥
    effect: dict = field(default_factory=dict)
    pve_only: bool = False
    pvp_only: bool = False


class TalentTree:
    def __init__(self, total_points: int = 50):
        self.talents: dict[str, Talent] = {}
        self.total_points = total_points
        self.spent_points = 0
        self.pve_spec: dict[str, int] = {}
        self.pvp_spec: dict[str, int] = {}
        self.active_spec = "pve"
        self.player_level = 60
        self.reset_history: list[dict] = []
        self._snapshot = None

    def add_talent(self, t: Talent):
        self.talents[t.tid] = t

    # ---- 内部校验 ----

    def _required_level(self, t: Talent) -> int:
        return t.tier * 10

    def _meets_level(self, t: Talent) -> bool:
        return self.player_level >= self._required_level(t)

    def _prereqs_satisfied(self, t: Talent) -> bool:
        """递归检查所有祖先前置都已加点。"""
        visited = set()
        stack = list(t.prereq)
        while stack:
            pid = stack.pop()
            if pid in visited:
                continue
            visited.add(pid)
            p = self.talents.get(pid)
            if p is None:
                continue
            if p.points == 0:
                return False
            stack.extend(p.prereq)
        return True

    def _mutex_conflict(self, t: Talent) -> bool:
        if not t.mutex_group:
            return False
        for other in self.talents.values():
            if (other.tid != t.tid and other.mutex_group == t.mutex_group
                    and other.points > 0):
                return True
        return False

    def _current_spec(self) -> dict:
        return self.pve_spec if self.active_spec == "pve" else self.pvp_spec

    def _sync_spec(self):
        """把当前天赋分配写回当前方案。"""
        spec = self._current_spec()
        spec.clear()
        for tid, t in self.talents.items():
            if t.points > 0:
                spec[tid] = t.points

    # ---- 加点 / 洗点 ----

    def spend_point(self, tid: str) -> bool:
        if tid not in self.talents:
            return False
        t = self.talents[tid]
        if t.points >= t.max_points:
            return False
        if self.spent_points >= self.total_points:
            return False
        if not self._meets_level(t):
            return False
        if not self._prereqs_satisfied(t):
            return False
        if self._mutex_conflict(t):
            return False
        t.points += 1
        self.spent_points += 1
        self._sync_spec()
        return True

    def reset_tree(self):
        """洗点：全额返还并记录历史。"""
        refunded = self.spent_points
        for t in self.talents.values():
            t.points = 0
        self.spent_points = 0
        self._sync_spec()
        self.reset_history.append({
            "spec": self.active_spec,
            "refunded": refunded,
        })

    # ---- 属性计算（纯函数，无状态依赖） ----

    def get_effect_value(self, effect_type: str) -> float:
        val = 0.0
        for t in self.talents.values():
            if t.points <= 0 or effect_type not in t.effect:
                continue
            if t.pve_only and self.active_spec != "pve":
                continue
            if t.pvp_only and self.active_spec != "pvp":
                continue
            if not self._meets_level(t):
                continue  # 降级后不满足条件的天赋自动失效
            val += t.effect[effect_type] * t.points
        if _is_reduction_effect(effect_type):
            val = min(val, REDUCTION_CAP)
        return val

    # ---- 模拟（快照隔离） ----

    def save_snapshot(self):
        self._snapshot = (
            {tid: t.points for tid, t in self.talents.items()},
            self.spent_points,
            dict(self._current_spec()),
        )

    def restore_snapshot(self):
        if not self._snapshot:
            return
        points_map, spent, spec = self._snapshot
        for tid, pts in points_map.items():
            if tid in self.talents:
                self.talents[tid].points = pts
        self.spent_points = spent
        current = self._current_spec()
        current.clear()
        current.update(spec)
        self._snapshot = None

    # ---- 等级 ----

    def check_level_requirement(self, tid: str) -> bool:
        t = self.talents.get(tid)
        return t is not None and self._meets_level(t)

    def set_player_level(self, level: int):
        """调整等级；降级时不满足条件的天赋自动失效并返还点数。"""
        self.player_level = level
        changed = False
        for t in self.talents.values():
            if t.points > 0 and not self._meets_level(t):
                self.spent_points -= t.points
                t.points = 0
                changed = True
        if changed:
            self._sync_spec()

    # ---- 方案切换 ----

    def switch_spec(self, spec: str):
        if spec not in ("pve", "pvp"):
            return
        if spec != self.active_spec:
            self._sync_spec()  # 保存旧方案
        self.active_spec = spec
        # 完整重算：清空后按新方案加载
        for t in self.talents.values():
            t.points = 0
        self.spent_points = 0
        for tid, pts in self._current_spec().items():
            t = self.talents.get(tid)
            if t is None:
                continue
            pts = min(pts, t.max_points)
            t.points = pts
            self.spent_points += pts
