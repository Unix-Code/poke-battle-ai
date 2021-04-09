import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
        with open("./dmg_map.json", "r") as f:
            data = json.load(f)
        dmg_map = {Type(k.upper()): [Type(x.upper()) for x in v] for k, v in data.items()}
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
class HitCountInfo:
    min_hits: int
    max_hits: int

    @property
    def definite_hit_count(self) -> Optional[int]:
        return self.min_hits if self.min_hits == self.max_hits else None

    @classmethod
    def as_standard(cls):
        return cls(min_hits=1, max_hits=1)


@dataclass(frozen=True)
class Move:
    # ID for pokeapi.co
    api_id: int
    name: str

    type: Type
    power: int
    pp: int
    damage_class: DamageClass

    # Percent
    healing: float
    drain: float  # includes recoil dmg

    high_crit_ratio: bool

    hit_count_info: HitCountInfo

    # Null accuracy means this move doesn't factor in accuracy checks
    accuracy: Optional[int] = None


@dataclass(frozen=True)
class Sprite:
    front: str
    back: str


@dataclass(frozen=True)
class PokemonStats:
    hp: int
    attack: int
    defense: int
    special: int
    speed: int


@dataclass(frozen=True)
class Pokemon:
    # ID for pokeapi.co
    api_id: int
    name: str
    sprite: Sprite
    types: list[Type]
    base_stats: PokemonStats

    # These are calculated without considering IV's and EV's
    stats: PokemonStats

    learn_set: set[Move]
    level: int = 100


@dataclass(frozen=True)
class MoveResult:
    heal: int = 0
    dmg: int = 0
    # TODO: Status?
