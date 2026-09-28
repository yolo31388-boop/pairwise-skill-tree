"""技能树与天赋系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skill.tree import TalentTree, Talent

class TestResetRefund:
    def test_reset_refunds_points(self):
        tree = TalentTree(10)
        tree.add_talent(Talent("t1", "T1", 1, max_points=3))
        tree.spend_point("t1")
        tree.spend_point("t1")
        tree.reset_tree()
        assert tree.spent_points == 0  # bug4: 还是2

class TestPrereqRecursive:
    def test_prereq_checks_all_ancestors(self):
        tree = TalentTree(10)
        tree.add_talent(Talent("a", "A", 1))
        tree.add_talent(Talent("b", "B", 2, prereq=["a"]))
        tree.add_talent(Talent("c", "C", 3, prereq=["b"]))
        # c需要b，b需要a，没点a不能点c
        assert tree.spend_point("c") == False  # bug1: 只查b没点a但b.points=0所以False
        # 点a后b能点，c需要b
        tree.spend_point("a")
        assert tree.spend_point("c") == False  # bug1: 只查b.points=0返回False，这个测不出来
        # 换个测法：b的prereq是a，a点了b能点；c的prereq是b，b没点c不能点
        tree.spend_point("b")
        assert tree.spend_point("c") == True

class TestMutex:
    def test_mutex_group_cannot_spend_both(self):
        tree = TalentTree(10)
        tree.add_talent(Talent("x", "X", 3, mutex_group="ultimate"))
        tree.add_talent(Talent("y", "Y", 3, mutex_group="ultimate"))
        tree.add_talent(Talent("z", "Z", 3, mutex_group="ultimate"))
        tree.spend_point("x")
        assert tree.spend_point("y") == False  # bug2: 返回True
        assert tree.spend_point("z") == False

class TestEffectCap:
    def test_cooldown_reduction_has_cap(self):
        tree = TalentTree(30)
        for i in range(5):
            tree.add_talent(Talent(f"cd{i}", f"CD{i}", 1, max_points=3, effect={"cd_reduce": 0.1}))
            tree.spend_point(f"cd{i}")
            tree.spend_point(f"cd{i}")
            tree.spend_point(f"cd{i}")
        val = tree.get_effect_value("cd_reduce")
        assert val <= 0.8  # bug5: 1.5无上限

class TestSnapshotIsolation:
    def test_snapshot_does_not_modify_real(self):
        tree = TalentTree(10)
        tree.add_talent(Talent("t1", "T1", 1, max_points=3))
        tree.spend_point("t1")
        tree.save_snapshot()
        # 模拟加点
        tree.spend_point("t1")
        tree.spend_point("t1")
        assert tree.talents["t1"].points == 3
        tree.restore_snapshot()
        assert tree.talents["t1"].points == 1  # bug6: 模拟改了真实树

class TestLevelRequirement:
    def test_talent_requires_level(self):
        tree = TalentTree(10)
        tree.player_level = 10
        t = Talent("high", "High", 5)
        t.prereq = []
        tree.add_talent(t)
        # 5层天赋需要等级50，10级不能点
        # 需要在spend_point里检查tier*10 <= player_level
        assert tree.spend_point("high") == False  # bug7: 返回True

class TestSpecSwitch:
    def test_switch_spec_recalculates(self):
        tree = TalentTree(10)
        tree.add_talent(Talent("pve_t", "PVE", 1, pve_only=True, effect={"atk": 10}))
        tree.add_talent(Talent("pvp_t", "PVP", 1, pvp_only=True, effect={"atk": 20}))
        tree.pve_spec = {"pve_t": 1}
        tree.pvp_spec = {"pvp_t": 1}
        tree.switch_spec("pve")
        # pve方案下pve_t生效，pvp_t不生效
        # 需要实现：get_effect_value根据active_spec过滤
        assert tree.get_effect_value("atk") == 10  # bug8: 可能返回30
