"""技能树与天赋系统 - 含8个bug"""
from dataclasses import dataclass, field
from typing import Optional

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
        self._snapshot = None

    def add_talent(self, t: Talent):
        self.talents[t.tid] = t

    def spend_point(self, tid: str) -> bool:
        if tid not in self.talents:
            return False
        t = self.talents[tid]
        if t.points >= t.max_points:
            return False
        if self.spent_points >= self.total_points:
            return False
        # bug1: 只检查直接前置，不递归
        for p in t.prereq:
            if p in self.talents and self.talents[p].points == 0:
                return False
        # bug2: 不检查互斥组
        # bug3: 不检查等级要求
        t.points += 1
        self.spent_points += 1
        return True

    def reset_tree(self):
        # bug4: 只清点数不返还
        for t in self.talents.values():
            t.points = 0
        # spent_points没重置

    def get_effect_value(self, effect_type: str) -> float:
        # bug5: 加法叠加无上限
        val = 0.0
        for t in self.talents.values():
            if t.points > 0 and effect_type in t.effect:
                val += t.effect[effect_type] * t.points
        return val

    def save_snapshot(self):
        # bug6: 模拟直接改真实树
        self._snapshot = {tid: t.points for tid, t in self.talents.items()}

    def restore_snapshot(self):
        if self._snapshot:
            for tid, pts in self._snapshot.items():
                if tid in self.talents:
                    self.talents[tid].points = pts

    def check_level_requirement(self, tid: str) -> bool:
        # bug7: 不检查等级
        return True

    def switch_spec(self, spec: str):
        # bug8: 切换方案不重算属性
        self.active_spec = spec
