#!/usr/bin/env python3

from __future__ import annotations

import abc
import functools
import itertools
import math
import operator

from typing import Any, Dict, Generator, Iterable, Iterator, List, Optional, Tuple

def min_cache(c: List[Tuple[Iterator[float], float]]) -> Optional[int]:
    mi, mv = None, None
    for i, (_, v) in enumerate(c):
        if v is None: continue
        if mv is None or v < mv:
            mv = v
            mi = i
    return mi

# merge monotonically increasing iterables
def merge(*iterables: Iterable[float]) -> Generator[float, None, None]:
    cache = [(p, q) for p, q in ((y, next(y, None)) for y in (iter(x) for x in iterables)) if q is not None]
    while (i := min_cache(cache)) is not None:
        it, v = cache[i]
        yield v
        nv = next(it, None)
        if nv is None:
            del cache[i]
        else:
            cache[i] = (it, nv)

def increasing(iterable: Iterable[float]) -> Generator[float, None, None]:
    last = None
    for value in iterable:
        if last is not None and value <= last:
            continue
        last = value
        yield value

def incmerge(*iterables: Iterable[float]) -> Generator[float, None, None]:
    return increasing(merge(*iterables))

class BuffSet():

    def __init__(self, injure_ratio: float = 1.0, perfect_dodge: bool = False, eva: float = 0.0, evasion_rate: float = 0.0):
        self.injure_ratio: float = injure_ratio
        self.perfect_dodge: bool = perfect_dodge
        self.eva: float = eva
        self.evasion_rate: float = evasion_rate

    def combine(self, buffset: BuffSet) -> BuffSet:
        return BuffSet(self.injure_ratio * buffset.injure_ratio, self.perfect_dodge or buffset.perfect_dodge, self.eva + buffset.eva, self.evasion_rate + buffset.evasion_rate)

    def bake_eva(self, eva: float, formation_bonus: float) -> float:
        return eva * (1.0 + self.eva + formation_bonus)

    def __eq__(self, other: Any) -> bool:
        if type(self) != type(other):
            return False
        return self.injure_ratio == other.injure_ratio and self.perfect_dodge == other.perfect_dodge and self.eva == other.eva and self.evasion_rate == other.evasion_rate

    def __hash__(self) -> int:
        return hash((self.injure_ratio, self.perfect_dodge, self.eva, self.evasion_rate))

    def __repr__(self) -> str:
        return f'BuffSet[injureratio: {self.injure_ratio}, perfect_dodge: {self.perfect_dodge}, eva: {self.eva}, evasion_rate: {self.evasion_rate}]'

class BuffTable(abc.ABC):

    def __init__(self, /, skill_info: str = ''):
        self.skill_info: str = skill_info

    @abc.abstractmethod
    def get_chunk_breakpoints(self, /) -> Iterable[float]:
        pass

    @abc.abstractmethod
    def get_statetable(self, /, timestamp: float) -> List[Tuple[float, BuffSet]]:
        pass

class BuffTableSimple(BuffTable):
    def __init__(self, /, buffset: Optional[BuffSet] = None, **kwargs):
        super().__init__(**kwargs)
        self.buffset: BuffSet = buffset if buffset is not None else BuffSet()
    def get_chunk_breakpoints(self, /) -> Iterable[float]:
        return [0.0]
    def get_statetable(self, /, timestamp: float) -> List[Tuple[float, BuffSet]]:
        return [(1.0, self.buffset)]

class BuffTableCompound(BuffTable):

    def __init__(self, /, chunk_maps: List[BuffTable], **kwargs):
        super().__init__(**kwargs)
        self.chunk_maps: List[BuffTable] = chunk_maps
        skill_table = [y for x in chunk_maps for y in x.skill_info.split('\n') if y != '']
        skill_table.sort()
        self.skill_info = '\n'.join(skill_table)

    def get_chunk_breakpoints(self, /) -> Iterable[float]:
        return incmerge([0.0], *[cmap.get_chunk_breakpoints() for cmap in self.chunk_maps])

    def get_statetable(self, /, timestamp: float) -> List[Tuple[float, BuffSet]]:
        def collapse_table(table):
            a, b = zip(*table)
            return (functools.reduce(operator.mul, a), functools.reduce(lambda x, y: x.combine(y), b))
        state_tables = itertools.product([(1.0, BuffSet())], *[cmap.get_statetable(timestamp) for cmap in self.chunk_maps])
        return [collapse_table(table) for table in state_tables]

class BuffTableRegular(BuffTable):
    def __init__(self, /, *, buffset: BuffSet, duration: float, proc_every: float, proc_rate: float, proc_first: Optional[float] = None, proc_first_rate: Optional[float] = None, **kwargs):
        super().__init__(**kwargs)
        self.buffset: BuffSet = buffset
        self.duration: float = duration
        self.proc_every: float = proc_every
        self.proc_rate: float = proc_rate
        self.proc_first: float = proc_first if proc_first is not None else proc_every
        self.proc_first_rate: float = proc_first_rate if proc_first_rate is not None else proc_rate

    def get_chunk_breakpoints(self) -> Iterable[float]:
        return incmerge([0.0], itertools.count(self.proc_first, self.proc_every), itertools.count(self.proc_first + self.duration, self.proc_every))

    def get_statetable(self, timestamp: float) -> List[Tuple[float, BuffSet]]:
        if timestamp < self.proc_first:
            return [(1.0, BuffSet())]
        rel_ts = (timestamp - self.proc_first) % self.proc_every
        if rel_ts < self.duration:
            pr = self.proc_rate if (timestamp - self.proc_first) // self.proc_every > 0 else self.proc_first_rate
            return [(pr, self.buffset), (1.0 - pr, BuffSet())]
        else:
            return [(1.0, BuffSet())]

class Stage():
    def __init__(self, atk_luck: float = 25.0, atk_hit: float = 75.0, hitrate_buff: float = 0.0, atk_level: int = 122, stage_length: float = 90, formation_bonus: float = 0.3):
        self.atk_luck: float = atk_luck
        self.atk_hit: float = atk_hit
        self.hitrate_buff: float = hitrate_buff
        self.atk_level: int = atk_level
        self.formation_bonus: float = formation_bonus
        self.stage_length: float = stage_length

class ExtraHeal():
    def __init__(self, heal_magnitude: float = 0.0, heal_every: float = 300.0, heal_rate: float = 1.0, heal_first: Optional[float] = None, heal_first_rate: Optional[float] = None, heal_info: str = ''):
        self.heal_magnitude: float = heal_magnitude
        self.heal_every: float = heal_every
        self.heal_rate: float = heal_rate
        self.heal_first: float = heal_first if heal_first is not None else heal_every
        self.heal_first_rate: float = heal_first_rate if heal_first_rate is not None else heal_rate
        self.heal_info = heal_info

    def get_healing(self, stage: Stage) -> float:
        heal_extra_count = math.floor((stage.stage_length - self.heal_first) / self.heal_every)
        return self.heal_magnitude * (self.heal_first_rate + heal_extra_count * self.heal_rate)


class Equip():
    def __init__(self, buff_table: Optional[BuffTable] = None, healing_list: Optional[List[ExtraHeal]] = None, extra_hp: float = 0, extra_eva: float = 0):
        self.buff_table: BuffTable = buff_table if buff_table is not None else empty_skill
        self.healing_list: List[ExtraHeal] = healing_list if healing_list is not None and len(healing_list) != 0 else [ExtraHeal()]
        self.extra_hp: float = extra_hp
        self.extra_eva: float = extra_eva

empty_skill = BuffTableSimple()

class ShipInfo():
    def __init__(self, *, hitpoints: float, def_luck: float, def_eva: float, def_level: int, skill_list: Optional[List[str]] = None, healing_list: Optional[List[str]] = None):
        self.skill_list: List[str] = skill_list if skill_list is not None else []
        self.buff_table: BuffTable = BuffTableCompound([skill_buffs[s] for s in self.skill_list]) if len(self.skill_list) > 0 else empty_skill
        self.hitpoints: float = hitpoints
        self.def_luck: float = def_luck
        self.def_eva: float = def_eva
        self.def_level: int = def_level
        self.healing_list: List[ExtraHeal] = [skill_heals[s] for s in healing_list] if healing_list is not None else []

    def hit_rate(self, buffset: BuffSet, stage: Stage, equip_list: List[Equip]) -> float:
        if buffset.perfect_dodge:
            return 0.0
        rate = 0.1 + stage.atk_hit / (2.0 + stage.atk_hit + buffset.bake_eva(sum((eq.extra_eva for eq in equip_list), self.def_eva), stage.formation_bonus)) + (stage.atk_luck - self.def_luck + stage.atk_level - self.def_level) / 1000.0 + stage.hitrate_buff - buffset.evasion_rate
        if rate < 0.1:
            return 0.1
        if rate > 1.0:
            return 1.0
        return rate

    def ehp_divisor(self, stage: Stage, equip_list: List[Equip]) -> float:
        buff_table = BuffTableCompound([equip.buff_table for equip in equip_list] + [self.buff_table])
        breakpoints = list(itertools.takewhile(lambda x: x < stage.stage_length, buff_table.get_chunk_breakpoints()))
        table_values = [sum(self.hit_rate(bs, stage, equip_list) * bs.injure_ratio * pr for pr, bs in buff_table.get_statetable(ts)) for ts in breakpoints]
        durations = [b - a for a, b in zip(breakpoints, breakpoints[1:] + [stage.stage_length])]
        return sum(w * dur / stage.stage_length for dur, w in zip(durations, table_values))

    def modified_hp(self, stage: Stage, equip_list: List[Equip]) -> float:
        hp = sum((eq.extra_hp for eq in equip_list), start=self.hitpoints)
        return hp * (1.0 + sum((heal.get_healing(stage) for eq in equip_list for heal in eq.healing_list)) + sum((heal.get_healing(stage) for heal in self.healing_list)))

    def ehp(self, stage: Stage, equip_list: Optional[List[Equip]] = None) -> float:
        if equip_list is None: equip_list = []
        return self.modified_hp(stage, equip_list) / self.ehp_divisor(stage, equip_list)

skill_buffs: Dict[str, BuffTable] = {
    'Abyssal Banquet': BuffTableSimple(buffset=BuffSet(injure_ratio=0.85),
        skill_info='If this ship is equipped with a Normal or AP main gun, decrease this ship’s damage taken by 15.0% and increase this ship’s critical rate by 12.0%.'),
    'All Out Assault - Takao Class II': BuffTableRegular(proc_every=300, proc_rate=0, proc_first=18.0, proc_first_rate=1.0, duration=300, buffset=BuffSet(evasion_rate=0.10),
        skill_info='Every 4 shots from the main gun, trigger All Out Assault - Takao Class II. The first time this ship fires its All Out Assault, increases this ship’s Evasion Rate by 10%, activating only once. [This calculation assumes it triggers 18s into the fight.]'),
    'An Shan Name Ship': BuffTableSimple(buffset=BuffSet(eva=0.10),
        skill_info='Increase Accuracy and FP by 25.0% and EVA by 10.0% for all An Shan-class destroyers.'),
    'Bilibili Mascot Girl - 22': BuffTableSimple(buffset=BuffSet(eva=0.35),
        skill_info='When sortied as main tank in the same fleet as 33, increase both 22’s and 33’s EVA by 35.0%.'),
    'Blazing Choreography': BuffTableSimple(buffset=BuffSet(eva=0.15),
        skill_info='At the start of the battle, if there is a CV, CVL, or Muse ship in the same fleet, increase this ship’s EVA by 15% and increase your Vanguard’s AA by 15%.'),
    'Death Raid': BuffTableSimple(skill_info='Death Raid is assumed to not activate.'),
    'Defense Order': BuffTableRegular(proc_every=20, proc_rate=0.25, duration=8, buffset=BuffSet(injure_ratio=0.85),
        skill_info='Every 20s, 25% chance to decrease the damage your entire fleet takes by 15% for 8s.'),
    'Demon Dance': BuffTableRegular(proc_every=20.0, proc_rate=70.0, duration=5.0, buffset=BuffSet(eva=0.30),
        skill_info='Every 20s, 70% chance to increase own Evasion by 30% for 5s and release a powerful barrage while launching fast torpedoes in a helical pattern.'),
    'Dual Nock': BuffTableSimple(BuffSet(injure_ratio=0.85),
        skill_info='If equipped with a Main Gun in own Secondary Weapon slot, increase AA Gun Efficiency by 15%. If equipped with an AA Gun in own Secondary Weapon slot, increase Main Gun Efficiency by 15%. If placed in the backmost position in the vanguard, decrease damage taken by self by 15%.'),
    'Emergency Maneuvers': BuffTableRegular(proc_every=20.0, proc_rate=0.30, duration=6.0, buffset=BuffSet(perfect_dodge=True),
        skill_info='Every 20s, 30% chance to evade all incoming attacks for 6s.'),
    'Engulfer of the Golden Vortex' : BuffTableSimple(buffset=BuffSet(eva=0.15),
        skill_info='When this ship’s torpedoes hit an enemy, decrease that enemy’s Speed by 60.0% for 5s. As long as this ship is not Out of Ammo, increase this ship’s EVA by 15.0%.'),
    'Giant Hunter': BuffTableSimple(buffset=BuffSet(eva=0.15),
        skill_info='Increase own EVA and TRP by 15.0%. Increase own damage against medium armor enemies by 25.0%. Slow enemy Heavy Cruisers by 30% for 5s after hitting them 4 times.'),
    'Hide and Seek': BuffTableCompound([
        BuffTableRegular(proc_every=20.0, proc_rate=1.0, proc_first=0.0, duration=5.0, buffset=BuffSet(evasion_rate=40.0)),
        BuffTableRegular(proc_every=20.0, proc_rate=1.0, proc_first=0.0, duration=2.0, buffset=BuffSet(perfect_dodge=True)),
        BuffTableSimple(skill_info='When this ship fires its Torpedoes: deploy a smokescreen, and a barrier onto this ship. This smokescreen increases Evasion Rate by 40.0% for all ships inside it and lasts 5s. The barrier lasts 5s and can absorb up to 6.0% of this ship’s max HP. If this barrier is destroyed before it expires, this ship evades all attacks for 2s.'),
        BuffTableSimple(skill_info='For the purpose of this calculation, she’s assumed to fire torps every 20 seconds, and the barrier is assumed to always pop. This will be updated if more emperical data arrives.'),
    ]),
    'Mercurial Memories': BuffTableRegular(proc_every=20, proc_rate=1.0, duration=10, buffset=BuffSet(perfect_dodge=True),
        skill_info='Increase this ship’s damage dealt to enemy CAs and BBs by 20%. When this ship takes damage, 15% chance to for her to evade all enemy attacks for 10s. (This skill has a 20s cooldown when activated and starts on cooldown.) [For this calculation, she is assumed to proc as soon as possible.]'),
    'Mizuho’s Intuition': BuffTableRegular(proc_every=20.0, proc_rate=1.0, duration=12.0, buffset=BuffSet(eva=0.25),
        skill_info='Every 20s, 100% chance to increase own Evasion by 25% and Accuracy by 50% for 12s. [Torp damage reduction is not considered for this calculation.]'),
    'Practical Teaching': BuffTableSimple(buffset=BuffSet(injure_ratio=0.92),
        skill_info='For 80s after battle starts, increase damage dealt by self by 15%, and reduce damage taken by self by 8% and by other Destroyers in the same fleet by 12%.'),
    'Shields': BuffTableSimple(skill_info='Rotating and/or stationary shields are not factored into this calculation.'),
    'Smokescreen': BuffTableRegular(proc_every=15.0, proc_rate=0.30, proc_first=0.0, proc_first_rate=1.0, duration=5.0, buffset=BuffSet(evasion_rate=40.0),
        skill_info='When the battle begins, and 30% chance every 15s after that, deploy a smokescreen that lasts for 5s. Allied ships inside the smokescreen gain 40% evasion rate.'),
    'Smokescreen: Light Cruisers': BuffTableRegular(proc_every=20.0, proc_rate=0.20, proc_first=10.0, proc_first_rate=1.0, duration=10.0, buffset=BuffSet(evasion_rate=35.0),
        skill_info='10s after battle starts and 20% chance every 20s after that: deploy a smokescreen that increases Evasion Rate by 35% and decreases damage taken from enemy aircraft by 35% for all your ships inside it. Smokescreen lasts for 10s, and does not stack with other smokescreens.'),
    'Vice Defense': BuffTableSimple(buffset=BuffSet(injure_ratio=0.96),
        skill_info='When taking damage, 8.0% chance to decrease said damage by 50%. [This is treated as a 4% flat-damage-reduction for this calculation.]'),
}

skill_heals: Dict[str, ExtraHeal] = {
    'Hide and Seek' : ExtraHeal(heal_magnitude=0.06, heal_every=20.0, heal_first=0.0),
}

ships: Dict[str, ShipInfo] = {
    '22': ShipInfo(hitpoints=1427, def_luck=22, def_eva=163, def_level=120, skill_list=['Bilibili Mascot Girl - 22']),
    '33': ShipInfo(hitpoints=1375, def_luck=33, def_eva=163, def_level=120),
    'Abukuma': ShipInfo(hitpoints=3131, def_luck=43, def_eva=105, def_level=120),
    'Acasta': ShipInfo(hitpoints=1535, def_luck=43, def_eva=244, def_level=120, skill_list=['Smokescreen', 'Death Raid']),
    'Achilles': ShipInfo(hitpoints=3214, def_luck=54, def_eva=97, def_level=120, skill_list=['Giant Hunter']),
    'Admiral Graf Spee': ShipInfo(hitpoints=4361, def_luck=36, def_eva=54, def_level=120),
    'Admiral Hipper': ShipInfo(hitpoints=4970, def_luck=66, def_eva=61, def_level=120, skill_list=['Shields', 'Vice Defense']),
    'Admiral Hipper µ': ShipInfo(hitpoints=4844, def_luck=66, def_eva=61, def_level=120, skill_list=['Shields']),
    'Agano': ShipInfo(hitpoints=3159, def_luck=21, def_eva=104, def_level=120),
    'Ägir': ShipInfo(hitpoints=7877, def_luck=0, def_eva=52, def_level=120, skill_list=['Abyssal Banquet', 'Engulfer of the Golden Vortex']),
    'Ajax': ShipInfo(hitpoints=3214, def_luck=74, def_eva=97, def_level=120, skill_list=['Giant Hunter']),
    'Akatsuki': ShipInfo(hitpoints=1747, def_luck=45, def_eva=194, def_level=120),
    'Algérie': ShipInfo(hitpoints=5021, def_luck=50, def_eva=66, def_level=120, skill_list=['Shields']),
    'Allen M. Sumner': ShipInfo(hitpoints=2526, def_luck=80, def_eva=179, def_level=120),
    'Amazon': ShipInfo(hitpoints=1535, def_luck=72, def_eva=231, def_level=120, skill_list=['Practical Teaching']),
    'Anchorage': ShipInfo(hitpoints=6256, def_luck=0, def_eva=80, def_level=120, skill_list=['Hide and Seek'], healing_list=['Hide and Seek']),
    'An Shan': ShipInfo(hitpoints=2277, def_luck=81, def_eva=165, def_level=120, skill_list=['An Shan Name Ship']),
    'Aoba': ShipInfo(hitpoints=3527, def_luck=52, def_eva=76, def_level=120),
    'Arashio': ShipInfo(hitpoints=1937, def_luck=32, def_eva=191, def_level=120),
    'Ardent': ShipInfo(hitpoints=1535, def_luck=35, def_eva=244, def_level=120),
    'Arethusa': ShipInfo(hitpoints=2830, def_luck=69, def_eva=100, def_level=120),
    'Ariake': ShipInfo(hitpoints=1938, def_luck=34, def_eva=212, def_level=120),
    'Asashio': ShipInfo(hitpoints=1937, def_luck=32, def_eva=191, def_level=120),
    'Ashigara': ShipInfo(hitpoints=4162, def_luck=60, def_eva=75, def_level=120),
    'Astoria': ShipInfo(hitpoints=3881, def_luck=15, def_eva=57, def_level=120),
    'Atago': ShipInfo(hitpoints=4295, def_luck=48, def_eva=79, def_level=120, skill_list=['All Out Assault - Takao Class II']),
    'Atlanta': ShipInfo(hitpoints=3517, def_luck=12, def_eva=95, def_level=120),
    'Aulick': ShipInfo(hitpoints=1998, def_luck=62, def_eva=158, def_level=120),
    'Aurora': ShipInfo(hitpoints=2914, def_luck=84, def_eva=100, def_level=120),
    'Avrora': ShipInfo(hitpoints=3372, def_luck=55, def_eva=79, def_level=120),
    'Ayanami': ShipInfo(hitpoints=1963, def_luck=36, def_eva=214, def_level=120, skill_list=['Demon Dance']),
    'Aylwin': ShipInfo(hitpoints=1679, def_luck=83, def_eva=162, def_level=120),
    'Azuma': ShipInfo(hitpoints=7541, def_luck=25, def_eva=50, def_level=120, skill_list=['Mizuho’s Intuition']),
    'Azusa Miura': ShipInfo(hitpoints=5237, def_luck=91, def_eva=66, def_level=120),
    'Bache': ShipInfo(hitpoints=2095, def_luck=78, def_eva=161, def_level=120),
    'Bailey': ShipInfo(hitpoints=2036, def_luck=70, def_eva=162, def_level=120),
    'Baltimore': ShipInfo(hitpoints=4591, def_luck=56, def_eva=57, def_level=120),
    'Baltimore µ': ShipInfo(hitpoints=4646, def_luck=56, def_eva=57, def_level=120, skill_list=['Blazing Choreography']),
    'Beagle': ShipInfo(hitpoints=1349, def_luck=71, def_eva=209, def_level=120),
    'Belfast': ShipInfo(hitpoints=3970, def_luck=88, def_eva=96, def_level=120, skill_list=['Smokescreen: Light Cruisers']),
    'Benson': ShipInfo(hitpoints=1826, def_luck=72, def_eva=163, def_level=120),
    'Biloxi': ShipInfo(hitpoints=4308, def_luck=68, def_eva=96, def_level=120),
    'Birmingham': ShipInfo(hitpoints=4189, def_luck=48, def_eva=94, def_level=120),
    'Black Heart': ShipInfo(hitpoints=4062, def_luck=83, def_eva=68, def_level=120),
    'Black Prince': ShipInfo(hitpoints=3608, def_luck=58, def_eva=98, def_level=120),
    'Blanc': ShipInfo(hitpoints=1800, def_luck=71, def_eva=175, def_level=120),
    'Boise': ShipInfo(hitpoints=3561, def_luck=70, def_eva=90, def_level=120),
    'Bremerton': ShipInfo(hitpoints=4828, def_luck=55, def_eva=57, def_level=120),
    'Brooklyn': ShipInfo(hitpoints=3470, def_luck=55, def_eva=90, def_level=120),
    'Bulldog': ShipInfo(hitpoints=1349, def_luck=65, def_eva=209, def_level=120),
    'Bush': ShipInfo(hitpoints=2054, def_luck=34, def_eva=160, def_level=120),
    'Carabiniere': ShipInfo(hitpoints=1788, def_luck=65, def_eva=214, def_level=120),
    'Cassin': ShipInfo(hitpoints=1900, def_luck=66, def_eva=187, def_level=120),
    'Chang Chun': ShipInfo(hitpoints=2277, def_luck=61, def_eva=165, def_level=120),
    'Chao Ho': ShipInfo(hitpoints=2538, def_luck=20, def_eva=70, def_level=120),
    'Chapayev': ShipInfo(hitpoints=4352, def_luck=68, def_eva=94, def_level=120),
    'Charles Ausburne': ShipInfo(hitpoints=2112, def_luck=82, def_eva=158, def_level=120),
    'Cheshire': ShipInfo(hitpoints=5141, def_luck=0, def_eva=76, def_level=120),
    'Chicago': ShipInfo(hitpoints=3393, def_luck=32, def_eva=53, def_level=120),
    'Chikuma': ShipInfo(hitpoints=4392, def_luck=42, def_eva=75, def_level=120),
    'Choukai': ShipInfo(hitpoints=4295, def_luck=50, def_eva=79, def_level=120, skill_list=['All Out Assault - Takao Class II']),
    'Clevelad': ShipInfo(hitpoints=3601, def_luck=71, def_eva=94, def_level=120),
    'Cleveland': ShipInfo(hitpoints=4307, def_luck=71, def_eva=92, def_level=120),
    'Cleveland µ': ShipInfo(hitpoints=3837, def_luck=71, def_eva=96, def_level=120),
    'Columbia': ShipInfo(hitpoints=4307, def_luck=70, def_eva=92, def_level=120),
    'Comet': ShipInfo(hitpoints=1524, def_luck=54, def_eva=245, def_level=120),
    'Concord': ShipInfo(hitpoints=3301, def_luck=67, def_eva=101, def_level=120),
    'Cooper': ShipInfo(hitpoints=2190, def_luck=22, def_eva=179, def_level=120),
    'Craven': ShipInfo(hitpoints=1774, def_luck=72, def_eva=163, def_level=120),
    'Crescent': ShipInfo(hitpoints=1524, def_luck=35, def_eva=240, def_level=120),
    'Curacoa': ShipInfo(hitpoints=3221, def_luck=24, def_eva=92, def_level=120),
    'Curlew': ShipInfo(hitpoints=3029, def_luck=45, def_eva=92, def_level=120),
    'Cygnet': ShipInfo(hitpoints=1524, def_luck=72, def_eva=255, def_level=120),
    'Denver': ShipInfo(hitpoints=4307, def_luck=69, def_eva=92, def_level=120),
    'Deutschland': ShipInfo(hitpoints=4018, def_luck=72, def_eva=53, def_level=120),
    'Dewey': ShipInfo(hitpoints=1647, def_luck=72, def_eva=162, def_level=120),
    'Dido': ShipInfo(hitpoints=3745, def_luck=85, def_eva=97, def_level=120),
    'Dido µ': ShipInfo(hitpoints=3921, def_luck=85, def_eva=97, def_level=120),
    'Dorsetshire': ShipInfo(hitpoints=4755, def_luck=33, def_eva=68, def_level=120),
    'Downes': ShipInfo(hitpoints=1900, def_luck=63, def_eva=187, def_level=120),
    'Drake': ShipInfo(hitpoints=5668, def_luck=0, def_eva=75, def_level=120),
    'Duca degli Abruzzi': ShipInfo(hitpoints=4360, def_luck=85, def_eva=96, def_level=120),
    'Echo': ShipInfo(hitpoints=1400, def_luck=65, def_eva=209, def_level=120),
    'Edinburgh': ShipInfo(hitpoints=4486, def_luck=37, def_eva=100, def_level=120),
    'Eldridge': ShipInfo(hitpoints=1720, def_luck=75, def_eva=211, def_level=120),
    'Elegant Kizuna AI': ShipInfo(hitpoints=5020, def_luck=66, def_eva=53, def_level=120),
    'Émile Bertin': ShipInfo(hitpoints=3425, def_luck=67, def_eva=117, def_level=120),
    'Eskimo': ShipInfo(hitpoints=1657, def_luck=72, def_eva=211, def_level=120),
    'Exeter': ShipInfo(hitpoints=3945, def_luck=49, def_eva=72, def_level=120),
    'Fiji': ShipInfo(hitpoints=3586, def_luck=11, def_eva=100, def_level=120),
    'Fletcher': ShipInfo(hitpoints=2077, def_luck=73, def_eva=160, def_level=120),
    'Foote': ShipInfo(hitpoints=1998, def_luck=67, def_eva=158, def_level=120),
    'Forbin': ShipInfo(hitpoints=1436, def_luck=69, def_eva=200, def_level=120),
    'Fortune': ShipInfo(hitpoints=1567, def_luck=68, def_eva=249, def_level=120),
    'Foxhound': ShipInfo(hitpoints=1538, def_luck=68, def_eva=249, def_level=120),
    'Fubuki': ShipInfo(hitpoints=1798, def_luck=34, def_eva=191, def_level=120),
    'Fumizuki': ShipInfo(hitpoints=1516, def_luck=27, def_eva=193, def_level=120),
    'Furutaka': ShipInfo(hitpoints=3719, def_luck=34, def_eva=75, def_level=120),
    'Fu Shun': ShipInfo(hitpoints=2277, def_luck=51, def_eva=165, def_level=120),
    'Galatea': ShipInfo(hitpoints=2830, def_luck=26, def_eva=100, def_level=120),
    'Glasgow': ShipInfo(hitpoints=3688, def_luck=81, def_eva=100, def_level=120),
    'Gloucester': ShipInfo(hitpoints=3789, def_luck=45, def_eva=101, def_level=120),
    'Glowworm': ShipInfo(hitpoints=1412, def_luck=36, def_eva=210, def_level=120),
    'Gremyashchy': ShipInfo(hitpoints=2165, def_luck=70, def_eva=165, def_level=120),
    'Grenville': ShipInfo(hitpoints=1518, def_luck=32, def_eva=210, def_level=120),
    'Gridley': ShipInfo(hitpoints=1810, def_luck=72, def_eva=163, def_level=120),
    'Gromky': ShipInfo(hitpoints=2277, def_luck=45, def_eva=175, def_level=120),
    'Grozny': ShipInfo(hitpoints=2496, def_luck=60, def_eva=166, def_level=120),
    'Halsey Powell': ShipInfo(hitpoints=2095, def_luck=55, def_eva=160, def_level=120),
    'Hamakaze': ShipInfo(hitpoints=2143, def_luck=58, def_eva=211, def_level=120),
    'Hammann': ShipInfo(hitpoints=2025, def_luck=47, def_eva=160, def_level=120),
    'Hanazuki': ShipInfo(hitpoints=2445, def_luck=65, def_eva=179, def_level=120),
    'Hardy': ShipInfo(hitpoints=1518, def_luck=40, def_eva=210, def_level=120),
    'Haruka Amami': ShipInfo(hitpoints=4019, def_luck=83, def_eva=96, def_level=120),
    'Harutsuki': ShipInfo(hitpoints=2445, def_luck=61, def_eva=179, def_level=120),
    'Hatakaze': ShipInfo(hitpoints=1561, def_luck=87, def_eva=193, def_level=120),
    'Hatsuharu': ShipInfo(hitpoints=1938, def_luck=45, def_eva=212, def_level=120),
    'Hatsushimo': ShipInfo(hitpoints=1938, def_luck=51, def_eva=212, def_level=120),
    'Hazelwood': ShipInfo(hitpoints=2054, def_luck=75, def_eva=160, def_level=120),
    'Helena': ShipInfo(hitpoints=3844, def_luck=33, def_eva=90, def_level=120),
    'Helena META': ShipInfo(hitpoints=4181, def_luck=33, def_eva=95, def_level=120),
    'Hermione': ShipInfo(hitpoints=3744, def_luck=58, def_eva=96, def_level=120),
    'Hibiki': ShipInfo(hitpoints=1798, def_luck=88, def_eva=194, def_level=120),
    'Hobby': ShipInfo(hitpoints=1826, def_luck=68, def_eva=163, def_level=120),
    'Honolulu': ShipInfo(hitpoints=3470, def_luck=50, def_eva=90, def_level=120),
    'Houston': ShipInfo(hitpoints=3445, def_luck=49, def_eva=53, def_level=120),
    'Hunter': ShipInfo(hitpoints=1370, def_luck=24, def_eva=210, def_level=120),
    'Ibuki': ShipInfo(hitpoints=4793, def_luck=0, def_eva=86, def_level=120),
    'Icarus': ShipInfo(hitpoints=1669, def_luck=70, def_eva=210, def_level=120),
    'Ikazuchi': ShipInfo(hitpoints=1747, def_luck=52, def_eva=194, def_level=120),
    'Inazuma': ShipInfo(hitpoints=1747, def_luck=57, def_eva=194, def_level=120),
    'Indianapolis': ShipInfo(hitpoints=4734, def_luck=23, def_eva=58, def_level=120),
    'Ingraham': ShipInfo(hitpoints=2400, def_luck=75, def_eva=179, def_level=120),
    'Isokaze': ShipInfo(hitpoints=2083, def_luck=18, def_eva=191, def_level=120),
    'Isuzu': ShipInfo(hitpoints=3454, def_luck=33, def_eva=100, def_level=120),
    'Jamaica': ShipInfo(hitpoints=3636, def_luck=67, def_eva=100, def_level=120),
    'Javelin': ShipInfo(hitpoints=1746, def_luck=65, def_eva=250, def_level=120),
    "Jeanne d'Arc": ShipInfo(hitpoints=3223, def_luck=83, def_eva=79, def_level=120),
    'Jenkins': ShipInfo(hitpoints=2080, def_luck=81, def_eva=161, def_level=120),
    'Jersey': ShipInfo(hitpoints=1536, def_luck=20, def_eva=210, def_level=120),
    'Jintsuu': ShipInfo(hitpoints=2855, def_luck=38, def_eva=108, def_level=120),
    'Juneau': ShipInfo(hitpoints=3517, def_luck=18, def_eva=95, def_level=120),
    'Juno': ShipInfo(hitpoints=1536, def_luck=40, def_eva=210, def_level=120),
    'Jupiter': ShipInfo(hitpoints=1536, def_luck=52, def_eva=210, def_level=120),
    'Kagerou': ShipInfo(hitpoints=2050, def_luck=25, def_eva=192, def_level=120),
    'Kako': ShipInfo(hitpoints=3719, def_luck=34, def_eva=75, def_level=120),
    'Kalk': ShipInfo(hitpoints=1826, def_luck=75, def_eva=163, def_level=120),
    'Kamikaze': ShipInfo(hitpoints=1726, def_luck=86, def_eva=193, def_level=120),
    'Karlsruhe': ShipInfo(hitpoints=3612, def_luck=39, def_eva=100, def_level=120),
    'Kasumi': ShipInfo(hitpoints=2164, def_luck=70, def_eva=226, def_level=120),
    'Kasumi (Venus Vacation)': ShipInfo(hitpoints=4846, def_luck=85, def_eva=94, def_level=120),
    'Kawakaze': ShipInfo(hitpoints=1830, def_luck=38, def_eva=190, def_level=120),
    'Kazagumo': ShipInfo(hitpoints=2238, def_luck=51, def_eva=191, def_level=120),
    'Kent': ShipInfo(hitpoints=3508, def_luck=71, def_eva=65, def_level=120),
    'Kimberly': ShipInfo(hitpoints=2054, def_luck=77, def_eva=160, def_level=120),
    'Kinu': ShipInfo(hitpoints=3126, def_luck=52, def_eva=105, def_level=120),
    'Kinugasa': ShipInfo(hitpoints=3527, def_luck=65, def_eva=76, def_level=120),
    'Kirov': ShipInfo(hitpoints=4075, def_luck=52, def_eva=110, def_level=120),
    'Kisaragi': ShipInfo(hitpoints=1652, def_luck=15, def_eva=193, def_level=120),
    'Kitakaze': ShipInfo(hitpoints=2641, def_luck=0, def_eva=197, def_level=120),
    'Kiyonami': ShipInfo(hitpoints=2055, def_luck=46, def_eva=191, def_level=120),
    'Kizuna AI': ShipInfo(hitpoints=1768, def_luck=66, def_eva=194, def_level=120),
    'Köln': ShipInfo(hitpoints=3612, def_luck=62, def_eva=100, def_level=120),
    'Königsberg': ShipInfo(hitpoints=3372, def_luck=42, def_eva=100, def_level=120),
    'Kumano': ShipInfo(hitpoints=4141, def_luck=10, def_eva=82, def_level=120),
    'Kuon': ShipInfo(hitpoints=4138, def_luck=90, def_eva=54, def_level=120),
    'Kuroshio': ShipInfo(hitpoints=2083, def_luck=34, def_eva=191, def_level=120),
    'Laffey': ShipInfo(hitpoints=2145, def_luck=18, def_eva=203, def_level=120),
    'La Galissonnière': ShipInfo(hitpoints=3484, def_luck=35, def_eva=114, def_level=120),
    'Leander': ShipInfo(hitpoints=3486, def_luck=44, def_eva=102, def_level=120),
    'Leipzig': ShipInfo(hitpoints=3734, def_luck=67, def_eva=102, def_level=120),
    'Le Malin': ShipInfo(hitpoints=2021, def_luck=51, def_eva=213, def_level=120),
    'Le Malin µ': ShipInfo(hitpoints=2021, def_luck=51, def_eva=213, def_level=120),
    'Le Mars': ShipInfo(hitpoints=1436, def_luck=24, def_eva=200, def_level=120),
    'Lena': ShipInfo(hitpoints=3246, def_luck=33, def_eva=91, def_level=120),
    'Le Téméraire': ShipInfo(hitpoints=1571, def_luck=41, def_eva=189, def_level=120),
    'Le Triomphant': ShipInfo(hitpoints=2021, def_luck=77, def_eva=213, def_level=120),
    'Libeccio': ShipInfo(hitpoints=1783, def_luck=42, def_eva=212, def_level=120),
    "Li'l Sandy": ShipInfo(hitpoints=3226, def_luck=85, def_eva=95, def_level=120),
    'Little Bel': ShipInfo(hitpoints=3231, def_luck=89, def_eva=96, def_level=120),
    'London': ShipInfo(hitpoints=3841, def_luck=62, def_eva=82, def_level=120),
    "L'Opiniâtre": ShipInfo(hitpoints=1772, def_luck=45, def_eva=178, def_level=120),
    'Maestrale': ShipInfo(hitpoints=1821, def_luck=56, def_eva=217, def_level=120),
    'Mainz': ShipInfo(hitpoints=5262, def_luck=0, def_eva=75, def_level=120),
    'Makinami': ShipInfo(hitpoints=2157, def_luck=40, def_eva=191, def_level=120),
    'Marblehead': ShipInfo(hitpoints=3301, def_luck=55, def_eva=101, def_level=120),
    'Marie Rose': ShipInfo(hitpoints=2042, def_luck=78, def_eva=192, def_level=120),
    'Matchless': ShipInfo(hitpoints=1683, def_luck=76, def_eva=210, def_level=120),
    'Matsukaze': ShipInfo(hitpoints=1726, def_luck=45, def_eva=190, def_level=120),
    'Maury': ShipInfo(hitpoints=1809, def_luck=69, def_eva=198, def_level=120),
    'Maya': ShipInfo(hitpoints=4295, def_luck=48, def_eva=79, def_level=120, skill_list=['All Out Assault - Takao Class II']),
    'McCall': ShipInfo(hitpoints=1724, def_luck=69, def_eva=162, def_level=120),
    'Memphis': ShipInfo(hitpoints=3301, def_luck=67, def_eva=101, def_level=120),
    'Michishio': ShipInfo(hitpoints=1964, def_luck=48, def_eva=191, def_level=120),
    'Mikazuki': ShipInfo(hitpoints=1487, def_luck=40, def_eva=193, def_level=120),
    'Mikuma': ShipInfo(hitpoints=4015, def_luck=13, def_eva=82, def_level=120),
    'Minazuki': ShipInfo(hitpoints=1487, def_luck=45, def_eva=193, def_level=120),
    'Minneapolis': ShipInfo(hitpoints=4152, def_luck=76, def_eva=57, def_level=120),
    'Minsk': ShipInfo(hitpoints=2612, def_luck=58, def_eva=177, def_level=120),
    'Misaki': ShipInfo(hitpoints=3883, def_luck=89, def_eva=92, def_level=120),
    'Mogami': ShipInfo(hitpoints=4623, def_luck=14, def_eva=80, def_level=120),
    'Monica': ShipInfo(hitpoints=3775, def_luck=88, def_eva=100, def_level=120),
    'Montpelier': ShipInfo(hitpoints=4361, def_luck=72, def_eva=92, def_level=120),
    'Morrison': ShipInfo(hitpoints=2115, def_luck=48, def_eva=160, def_level=120),
    'Mullany': ShipInfo(hitpoints=2115, def_luck=89, def_eva=160, def_level=120),
    'Murmansk': ShipInfo(hitpoints=3396, def_luck=65, def_eva=101, def_level=120),
    'Musketeer': ShipInfo(hitpoints=1683, def_luck=67, def_eva=210, def_level=120),
    'Mutsuki': ShipInfo(hitpoints=1652, def_luck=35, def_eva=193, def_level=120),
    'Myoukou': ShipInfo(hitpoints=5220, def_luck=62, def_eva=78, def_level=120),
    'Nachi': ShipInfo(hitpoints=5220, def_luck=58, def_eva=78, def_level=120),
    'Naganami': ShipInfo(hitpoints=2157, def_luck=55, def_eva=191, def_level=120),
    'Nagara': ShipInfo(hitpoints=2891, def_luck=36, def_eva=105, def_level=120),
    'Nagatsuki': ShipInfo(hitpoints=1516, def_luck=35, def_eva=193, def_level=120),
    'Naka': ShipInfo(hitpoints=2540, def_luck=53, def_eva=108, def_level=120),
    'Nakiri Ayame': ShipInfo(hitpoints=4168, def_luck=65, def_eva=50, def_level=120),
    'Natsuiro Matsuri': ShipInfo(hitpoints=1763, def_luck=87, def_eva=190, def_level=120),
    'Nekone': ShipInfo(hitpoints=1941, def_luck=52, def_eva=189, def_level=120),
    'Neptune': ShipInfo(hitpoints=4637, def_luck=0, def_eva=98, def_level=120),
    'Neptune (Neptunia)': ShipInfo(hitpoints=3430, def_luck=73, def_eva=100, def_level=120),
    'Newcastle': ShipInfo(hitpoints=3928, def_luck=78, def_eva=100, def_level=120),
    'Nicholas': ShipInfo(hitpoints=2280, def_luck=80, def_eva=160, def_level=120),
    'Nicoloso da Recco': ShipInfo(hitpoints=1850, def_luck=82, def_eva=209, def_level=120),
    'Niizuki': ShipInfo(hitpoints=2445, def_luck=32, def_eva=179, def_level=120),
    'Ning Hai': ShipInfo(hitpoints=2192, def_luck=51, def_eva=110, def_level=120),
    'Noire': ShipInfo(hitpoints=3828, def_luck=83, def_eva=65, def_level=120),
    'Norfolk': ShipInfo(hitpoints=4621, def_luck=69, def_eva=68, def_level=120),
    'Northampton': ShipInfo(hitpoints=3346, def_luck=27, def_eva=53, def_level=120),
    'Noshiro': ShipInfo(hitpoints=3278, def_luck=55, def_eva=104, def_level=120),
    'Nowaki': ShipInfo(hitpoints=2145, def_luck=72, def_eva=191, def_level=120),
    'Nürnberg': ShipInfo(hitpoints=3811, def_luck=80, def_eva=98, def_level=120),
    'Oite': ShipInfo(hitpoints=1561, def_luck=42, def_eva=193, def_level=120),
    'Omaha': ShipInfo(hitpoints=3237, def_luck=67, def_eva=101, def_level=120),
    'Ooshio': ShipInfo(hitpoints=1937, def_luck=40, def_eva=191, def_level=120),
    'Oyashio': ShipInfo(hitpoints=2083, def_luck=34, def_eva=191, def_level=120),
    'Pamiat Merkuria': ShipInfo(hitpoints=3300, def_luck=88, def_eva=87, def_level=120, skill_list=['Mercurial Memories']),
    'Penelope': ShipInfo(hitpoints=2914, def_luck=52, def_eva=100, def_level=120),
    'Pensacola': ShipInfo(hitpoints=3290, def_luck=75, def_eva=55, def_level=120),
    'Phoenix': ShipInfo(hitpoints=3470, def_luck=88, def_eva=90, def_level=120),
    'Ping Hai': ShipInfo(hitpoints=2160, def_luck=47, def_eva=107, def_level=120),
    'Pola': ShipInfo(hitpoints=4941, def_luck=75, def_eva=57, def_level=120),
    'Portland': ShipInfo(hitpoints=5355, def_luck=78, def_eva=78, def_level=120, skill_list=['Defense Order']),
    'Prinz Eugen': ShipInfo(hitpoints=6252, def_luck=78, def_eva=62, def_level=120),
    'Prinz Heinrich': ShipInfo(hitpoints=5946, def_luck=50, def_eva=66, def_level=120),
    'Prototype Bulin MKII': ShipInfo(hitpoints=232, def_luck=100, def_eva=116, def_level=120),
    'Purple Heart': ShipInfo(hitpoints=3695, def_luck=87, def_eva=102, def_level=120),
    'Quincy': ShipInfo(hitpoints=4015, def_luck=9, def_eva=57, def_level=120),
    'Radford': ShipInfo(hitpoints=2054, def_luck=80, def_eva=163, def_level=120),
    'Raleigh': ShipInfo(hitpoints=3237, def_luck=82, def_eva=101, def_level=120),
    'Reno': ShipInfo(hitpoints=3755, def_luck=52, def_eva=95, def_level=120),
    'Richmond': ShipInfo(hitpoints=3237, def_luck=69, def_eva=101, def_level=120),
    'Roon': ShipInfo(hitpoints=5920, def_luck=0, def_eva=78, def_level=120),
    'Roon µ': ShipInfo(hitpoints=6055, def_luck=0, def_eva=78, def_level=120),
    'Rurutie': ShipInfo(hitpoints=4106, def_luck=66, def_eva=88, def_level=120),
    'Saint Louis': ShipInfo(hitpoints=5363, def_luck=0, def_eva=80, def_level=120),
    'Salt Lake City': ShipInfo(hitpoints=3290, def_luck=71, def_eva=55, def_level=120),
    'San Diego': ShipInfo(hitpoints=3995, def_luck=85, def_eva=95, def_level=120),
    'San Francisco': ShipInfo(hitpoints=4831, def_luck=75, def_eva=68, def_level=120),
    'San Juan': ShipInfo(hitpoints=3517, def_luck=77, def_eva=95, def_level=120),
    'Seattle': ShipInfo(hitpoints=5257, def_luck=15, def_eva=97, def_level=120, skill_list=['Dual Nock']),
    'Sendai': ShipInfo(hitpoints=2780, def_luck=42, def_eva=108, def_level=120),
    'Sheffield': ShipInfo(hitpoints=3796, def_luck=78, def_eva=100, def_level=120),
    'Sheffield µ': ShipInfo(hitpoints=3559, def_luck=78, def_eva=100, def_level=120),
    'Shigure': ShipInfo(hitpoints=1928, def_luck=84, def_eva=210, def_level=120),
    'Shimakaze': ShipInfo(hitpoints=2362, def_luck=41, def_eva=232, def_level=120),
    'Shirakami Fubuki': ShipInfo(hitpoints=1830, def_luck=69, def_eva=191, def_level=120),
    'Shiranui': ShipInfo(hitpoints=1908, def_luck=25, def_eva=212, def_level=120),
    'Shiratsuyu': ShipInfo(hitpoints=1712, def_luck=41, def_eva=190, def_level=120),
    'Shirayuki': ShipInfo(hitpoints=1798, def_luck=41, def_eva=194, def_level=120),
    'Shropshire': ShipInfo(hitpoints=3461, def_luck=75, def_eva=67, def_level=120),
    'Sims': ShipInfo(hitpoints=2025, def_luck=45, def_eva=160, def_level=120),
    'Sirius': ShipInfo(hitpoints=3744, def_luck=70, def_eva=97, def_level=120),
    'Smalley': ShipInfo(hitpoints=2095, def_luck=65, def_eva=160, def_level=120),
    'Southampton': ShipInfo(hitpoints=3688, def_luck=32, def_eva=100, def_level=120),
    'Specialized Bulin Custom MKIII': ShipInfo(hitpoints=232, def_luck=100, def_eva=116, def_level=120),
    'Spence': ShipInfo(hitpoints=1998, def_luck=20, def_eva=158, def_level=120),
    'Stanly': ShipInfo(hitpoints=2095, def_luck=90, def_eva=160, def_level=120),
    'Stephen Potter': ShipInfo(hitpoints=2156, def_luck=70, def_eva=160, def_level=120),
    'St. Louis': ShipInfo(hitpoints=3604, def_luck=65, def_eva=90, def_level=120),
    'Stremitelny': ShipInfo(hitpoints=2468, def_luck=42, def_eva=175, def_level=120),
    'Suffolk': ShipInfo(hitpoints=3754, def_luck=72, def_eva=65, def_level=120),
    'Sussex': ShipInfo(hitpoints=3461, def_luck=68, def_eva=71, def_level=120),
    'Suzutsuki': ShipInfo(hitpoints=2538, def_luck=72, def_eva=179, def_level=120),
    'Suzuya': ShipInfo(hitpoints=4176, def_luck=15, def_eva=80, def_level=120),
    'Swiftsure': ShipInfo(hitpoints=3796, def_luck=44, def_eva=96, def_level=120),
    'Tai Yuan': ShipInfo(hitpoints=2277, def_luck=71, def_eva=165, def_level=120),
    'Takao': ShipInfo(hitpoints=4295, def_luck=65, def_eva=79, def_level=120, skill_list=['All Out Assault - Takao Class II']),
    'Tallinn': ShipInfo(hitpoints=5614, def_luck=80, def_eva=61, def_level=120),
    'Tanikaze': ShipInfo(hitpoints=2143, def_luck=52, def_eva=211, def_level=120),
    'Tartu': ShipInfo(hitpoints=1868, def_luck=45, def_eva=212, def_level=120),
    'Tashkent': ShipInfo(hitpoints=2648, def_luck=86, def_eva=179, def_level=120),
    'Tashkent µ': ShipInfo(hitpoints=2648, def_luck=86, def_eva=179, def_level=120),
    'Thatcher': ShipInfo(hitpoints=2037, def_luck=65, def_eva=158, def_level=120),
    'Trento': ShipInfo(hitpoints=3544, def_luck=42, def_eva=71, def_level=120),
    'Umikaze': ShipInfo(hitpoints=1681, def_luck=50, def_eva=190, def_level=120),
    'Universal Bulin': ShipInfo(hitpoints=232, def_luck=100, def_eva=116, def_level=120),
    'Urakaze': ShipInfo(hitpoints=2083, def_luck=27, def_eva=191, def_level=120),
    'Uranami': ShipInfo(hitpoints=1798, def_luck=75, def_eva=195, def_level=120),
    'Uzuki': ShipInfo(hitpoints=1487, def_luck=37, def_eva=193, def_level=120),
    'Vampire': ShipInfo(hitpoints=1314, def_luck=42, def_eva=195, def_level=120),
    'Vauquelin': ShipInfo(hitpoints=1868, def_luck=48, def_eva=212, def_level=120),
    'Vincennes': ShipInfo(hitpoints=4015, def_luck=12, def_eva=57, def_level=120),
    'Vincenzo Gioberti': ShipInfo(hitpoints=1846, def_luck=44, def_eva=212, def_level=120),
    'Wakaba': ShipInfo(hitpoints=1770, def_luck=36, def_eva=192, def_level=120),
    'White Heart': ShipInfo(hitpoints=1947, def_luck=73, def_eva=178, def_level=120),
    'Wichita': ShipInfo(hitpoints=3709, def_luck=70, def_eva=50, def_level=120),
    'Yamakaze': ShipInfo(hitpoints=1681, def_luck=35, def_eva=190, def_level=120),
    'Yat Sen': ShipInfo(hitpoints=1884, def_luck=64, def_eva=79, def_level=120),
    'Ying Swei': ShipInfo(hitpoints=2443, def_luck=20, def_eva=70, def_level=120),
    'Yoizuki': ShipInfo(hitpoints=2445, def_luck=61, def_eva=179, def_level=120),
    'York': ShipInfo(hitpoints=3916, def_luck=15, def_eva=92, def_level=120),
    'Yukikaze': ShipInfo(hitpoints=2226, def_luck=93, def_eva=192, def_level=120),
    'Yura': ShipInfo(hitpoints=2898, def_luck=40, def_eva=105, def_level=120),
    'Yuubari': ShipInfo(hitpoints=2342, def_luck=53, def_eva=105, def_level=120),
    'Yuudachi': ShipInfo(hitpoints=1828, def_luck=32, def_eva=190, def_level=120),
    'Yuugure': ShipInfo(hitpoints=1784, def_luck=32, def_eva=213, def_level=120),
    'Z1': ShipInfo(hitpoints=2218, def_luck=40, def_eva=153, def_level=120),
    'Z18': ShipInfo(hitpoints=2033, def_luck=38, def_eva=148, def_level=120),
    'Z19': ShipInfo(hitpoints=2033, def_luck=39, def_eva=148, def_level=120),
    'Z2': ShipInfo(hitpoints=2053, def_luck=44, def_eva=148, def_level=120),
    'Z20': ShipInfo(hitpoints=1993, def_luck=71, def_eva=148, def_level=120),
    'Z21': ShipInfo(hitpoints=1993, def_luck=42, def_eva=148, def_level=120),
    'Z23': ShipInfo(hitpoints=2290, def_luck=65, def_eva=162, def_level=120),
    'Z24': ShipInfo(hitpoints=2125, def_luck=56, def_eva=157, def_level=120),
    'Z25': ShipInfo(hitpoints=2116, def_luck=72, def_eva=156, def_level=120),
    'Z26': ShipInfo(hitpoints=2116, def_luck=43, def_eva=156, def_level=120),
    'Z28': ShipInfo(hitpoints=2123, def_luck=45, def_eva=156, def_level=120),
    'Z35': ShipInfo(hitpoints=2092, def_luck=35, def_eva=159, def_level=120),
    'Z36': ShipInfo(hitpoints=2092, def_luck=36, def_eva=159, def_level=120),
    'Z46': ShipInfo(hitpoints=2595, def_luck=63, def_eva=151, def_level=120),
    'Zara': ShipInfo(hitpoints=4941, def_luck=75, def_eva=57, def_level=120),
}

meta_boss = Stage(stage_length=80, formation_bonus=0.0, atk_hit=105, atk_luck=20)
taihou_boss = Stage(stage_length=90, formation_bonus=0.30, atk_hit=75, atk_luck=25)

rudder = Equip(extra_hp=60, extra_eva=40, buff_table=BuffTableRegular(proc_every=20.0, proc_rate=0.30, duration=2.0, buffset=BuffSet(perfect_dodge=True)))
beaver = Equip(extra_hp=75, extra_eva=35)
toolbox = Equip(extra_hp=500, extra_eva=0, healing_list=[ExtraHeal(heal_magnitude=0.01, heal_every=15.0)])
manjuu = Equip(extra_hp=550, extra_eva=0)

print(f'portkai rudder/beaver: {int(ships["Portland"].ehp(taihou_boss, [rudder, beaver]))}')
print(f'seattle rudder/box: {int(ships["Seattle"].ehp(taihou_boss, [rudder, toolbox]))}')
print(f'takao rudder/beaver: {int(ships["Takao"].ehp(taihou_boss, [rudder, beaver]))}')
print(f'pamiat rudder/box: {int(ships["Pamiat Merkuria"].ehp(taihou_boss, [rudder, toolbox]))}')
print(f'tashkent rudder/box: {int(ships["Tashkent"].ehp(taihou_boss, [rudder, toolbox]))}')
print(f'tashkent manjuu/box: {int(ships["Tashkent"].ehp(taihou_boss, [manjuu, toolbox]))}')
