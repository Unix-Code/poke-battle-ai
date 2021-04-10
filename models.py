import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from battle_strategies import BattleStrategy


class DamageClass(Enum):
    PHYSICAL = "PHYSICAL"
    SPECIAL = "SPECIAL"


class Type(Enum):
    NORMAL = "NORMAL"
    FIGHTING = "FIGHTING"
    FLYING = "FLYING"
    POISON = "POISON"
    GROUND = "GROUND"
    ROCK = "ROCK"
    BUG = "BUG"
    GHOST = "GHOST"
    FIRE = "FIRE"
    WATER = "WATER"
    GRASS = "GRASS"
    ELECTRIC = "ELECTRIC"
    PSYCHIC = "PSYCHIC"
    ICE = "ICE"
    DRAGON = "DRAGON"

    @classmethod
    def dmg_modifier(cls, attacking_type: 'Type', defending_type: 'Type') -> float:
        with open("./data/dmg_map.json", "r") as f:
            data = json.load(f)
        dmg_map = {Type(k.upper()): {m: [Type(t.upper()) for t in t_list]
                                     for m, t_list in v.items()}
                   for k, v in data.items()}
        type_dmg_map = dmg_map[attacking_type]
        if defending_type in type_dmg_map["double_damage_to"]:
            return 2
        elif defending_type in type_dmg_map["half_damage_to"]:
            return 0.5
        elif defending_type in type_dmg_map["no_damage_to"]:
            return 0
        else:
            return 1


@dataclass(frozen=True)
class HitInfo:
    min_hits: int
    max_hits: int
    has_invulnerable_phase: bool = False
    requires_charge: bool = False
    has_recharge: bool = False
    self_destructing: bool = False

    @property
    def definite_hit_count(self) -> Optional[int]:
        return self.min_hits if self.min_hits == self.max_hits else None

    def num_hits(self) -> int:
        if self.definite_hit_count is not None:
            return self.definite_hit_count

        num_hits = random.choices(range(self.min_hits, self.max_hits + 1),
                                  [0.375, 0.375, 0.125, 0.125], k=1)
        return num_hits[0]


@dataclass(frozen=True)
class MoveInfo:
    # ID for pokeapi.co
    api_id: int
    name: str

    type: Type
    power: int
    total_pp: int
    damage_class: DamageClass
    priority: int

    # Percent
    healing: float
    drain: float  # includes recoil dmg

    high_crit_ratio: bool

    hit_info: HitInfo

    # Null accuracy means this move doesn't factor in accuracy checks
    accuracy: Optional[float]

    @property
    def display_name(self) -> str:
        return self.name.replace("-", " ").capitalize()


@dataclass
class Move:
    info: MoveInfo
    pp: int

    @classmethod
    def struggle(cls) -> 'Move':
        move_info = MoveInfo(api_id=165, name='struggle',
                             type=Type.NORMAL, power=50, total_pp=10, damage_class=DamageClass.PHYSICAL, healing=0,
                             drain=-0.5, high_crit_ratio=False, hit_info=HitInfo(min_hits=1, max_hits=1),
                             accuracy=1.0, priority=0)
        return Move(move_info, pp=move_info.total_pp)  # This pp will never decrement

    def use(self) -> 'Move':
        if self.pp == 0:
            return self.struggle()
        else:
            self.pp -= 1
            return self

    @property
    def display_name(self) -> str:
        return self.info.display_name


@dataclass(frozen=True)
class Sprite:
    front: str
    back: str


@dataclass(frozen=True)
class PokemonStats:
    total_hp: int
    attack: int
    defense: int
    special: int
    speed: int


@dataclass(frozen=True)
class PokemonSpecies:
    # ID for pokeapi.co
    api_id: int
    name: str
    sprite: Sprite
    types: list[Type]
    base_stats: PokemonStats
    learn_set: set[MoveInfo]

    @property
    def display_name(self) -> str:
        return self.name.replace("-", " ").capitalize()


class PokemonStatus(Enum):
    CHARGING = 0  # (ie Solarbeam or Razor Wind)
    RECHARGING = 1  # (ie after Hyper Beam)
    INVULNERABLE = 2  # (ie first turn of Fly or Dig)
    # TODO: Add Burned, Poisoned, Frozen, Asleep, Confused, etc


@dataclass
class Pokemon:
    species: PokemonSpecies
    # These are calculated without considering IV's and EV's
    stats: PokemonStats
    hp: int
    move_set: tuple[Move, Move, Move, Move]
    nickname: str
    level: int = 100

    statuses: set[PokemonStatus] = field(default_factory=set)

    @property
    def fainted(self) -> bool:
        return self.hp == 0

    def apply_health_effect(self, health_delta: int):
        self.hp = min(max(self.hp + health_delta, 0), self.stats.total_hp)

    def has_status(self, status: PokemonStatus) -> bool:
        return status in self.statuses


@dataclass(frozen=True)
class Trainer:
    name: str
    pokemon: Pokemon
    battle_strategy: 'BattleStrategy'

    @property
    def cannot_continue(self) -> bool:
        return self.pokemon.fainted

    def visit_poke_center(self):
        self.pokemon.hp = self.pokemon.stats.total_hp
        for move in self.pokemon.move_set:
            move.pp = move.info.total_pp

    def pick_move(self, opposing_pokemon: Pokemon) -> Move:
        return self.battle_strategy.pick_move(self.pokemon, opposing_pokemon)
