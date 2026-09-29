"""技能树与天赋系统"""
from dataclasses import dataclass, field

# 效果叠加上限（减益/减CD类有下限保护，防止叠到100%无冷却）
EFFECT_CAPS = {
    "cd_reduce": 0.8,       # 冷却缩减最多80%
    "damage_reduce": 0.7,   # 减伤最多70%
    "slow": 0.6,            # 减速最多60%
}


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
        self.reset_history: list[dict] = []  # 洗点历史
        self._snapshot = None

    def add_talent(self, t: Talent):
        self.talents[t.tid] = t

    def _level_required(self, t: Talent) -> int:
        return t.tier * 10

    def _prereqs_satisfied(self, tid: str, visited=None) -> bool:
        """递归检查所有祖先前置是否都已加点"""
        if visited is None:
            visited = set()
        if tid in visited:
            return True
        visited.add(tid)
        t = self.talents.get(tid)
        if t is None:
            return False
        for p in t.prereq:
            pre = self.talents.get(p)
            if pre is None or pre.points == 0:
                return False
            if not self._prereqs_satisfied(p, visited):
                return False
        return True

    def _mutex_conflict(self, t: Talent) -> bool:
        """同层互斥组校验：同组已有加点则冲突"""
        if not t.mutex_group:
            return False
        for other in self.talents.values():
            if (other.tid != t.tid and other.mutex_group == t.mutex_group
                    and other.points > 0):
                return True
        return False

    def spend_point(self, tid: str) -> bool:
        if tid not in self.talents:
            return False
        t = self.talents[tid]
        if t.points >= t.max_points:
            return False
        if self.spent_points >= self.total_points:
            return False
        # 等级要求：按加点时等级校验
        if self.player_level < self._level_required(t):
            return False
        # 方案限定校验
        if t.pve_only and self.active_spec != "pve":
            return False
        if t.pvp_only and self.active_spec != "pvp":
            return False
        # 递归前置检查
        if not self._prereqs_satisfied(tid):
            return False
        # 互斥组检查
        if self._mutex_conflict(t):
            return False
        t.points += 1
        self.spent_points += 1
        return True

    def reset_tree(self):
        """洗点：全额返还点数并记录历史"""
        refunded = self.spent_points
        for t in self.talents.values():
            t.points = 0
        self.spent_points = 0
        self.pve_spec = {}
        self.pvp_spec = {}
        self.reset_history.append({"refunded": refunded})

    def _active_allocation(self) -> dict:
        """当前生效方案的加点分配；方案为空时回退到天赋自身点数"""
        spec = self.pve_spec if self.active_spec == "pve" else self.pvp_spec
        if spec:
            return spec
        return {tid: t.points for tid, t in self.talents.items() if t.points > 0}

    def get_effect_value(self, effect_type: str) -> float:
        """纯函数式属性计算：只依赖当前方案分配，与加点顺序无关"""
        val = 0.0
        allocation = self._active_allocation()
        for tid, pts in allocation.items():
            t = self.talents.get(tid)
            if t is None or pts <= 0 or effect_type not in t.effect:
                continue
            # 方案限定过滤：PVE方案下PVP专属不生效，反之亦然
            if t.pve_only and self.active_spec != "pve":
                continue
            if t.pvp_only and self.active_spec != "pvp":
                continue
            val += t.effect[effect_type] * pts
        # 减益/减CD类效果下限保护
        cap = EFFECT_CAPS.get(effect_type)
        if cap is not None:
            val = min(val, cap)
        return val

    def save_snapshot(self):
        """模拟加点前保存快照（含已花点数），与真实树隔离"""
        self._snapshot = {
            "points": {tid: t.points for tid, t in self.talents.items()},
            "spent_points": self.spent_points,
        }

    def restore_snapshot(self):
        """取消模拟：完整恢复快照，属性可回滚"""
        if self._snapshot:
            for tid, pts in self._snapshot["points"].items():
                if tid in self.talents:
                    self.talents[tid].points = pts
            self.spent_points = self._snapshot["spent_points"]
            self._snapshot = None

    def check_level_requirement(self, tid: str) -> bool:
        t = self.talents.get(tid)
        if t is None:
            return False
        return self.player_level >= self._level_required(t)

    def set_player_level(self, level: int):
        """降级时自动失效不满足等级条件的天赋并返还点数"""
        self.player_level = level
        for t in self.talents.values():
            if t.points > 0 and not self.check_level_requirement(t.tid):
                self.spent_points -= t.points
                t.points = 0

    def switch_spec(self, spec: str):
        """切换PVE/PVP方案：方案独立存储，切换后属性按新方案完整重算"""
        if spec not in ("pve", "pvp"):
            return
        if spec != self.active_spec:
            # 切换前把当前真实点数存回旧方案，保证旧方案效果被完整移除
            old_spec = self.pve_spec if self.active_spec == "pve" else self.pvp_spec
            old_spec.clear()
            old_spec.update({tid: t.points for tid, t in self.talents.items()
                             if t.points > 0})
        self.active_spec = spec
        # 应用新方案加点
        new_spec = self.pve_spec if spec == "pve" else self.pvp_spec
        for t in self.talents.values():
            t.points = 0
        self.spent_points = 0
        for tid, pts in new_spec.items():
            t = self.talents.get(tid)
            if t is not None:
                t.points = min(pts, t.max_points)
                self.spent_points += t.points
