import json
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from battle_strategies import BattleStrategy


class DamageClass(Enum):
    PHYSICAL = "PHYSICAL"
    SPECIAL = "SPECIAL"


class Ailment(Enum):
    BURN = "BURN"
    PARALYSIS = "PARALYSIS"
    TRAP = "TRAP"
    POISON = "POISON"
    CONFUSION = "CONFUSION"
    # For Tri Attack
    UNKNOWN = "UNKNOWN"

    @classmethod
    def get_tri_attack_ailment(cls) -> 'Ailment':
        """
        Tri Attack has an equal chance of causing paralyzing, burning, and freezing the opponent.
        So to help with that, this function randomly returns one of those ailments (except freeze
        because we don't support it).
        """
        rand_val = random.random()
        if rand_val < 1/3:
            return Ailment.PARALYSIS
        if rand_val < 2/3:
            return Ailment.BURN
        else:
            # Because we don't support freezing
            return Ailment.UNKNOWN


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

    ailment: Optional[Ailment] = None
    ailment_chance: float = 0

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

    @classmethod
    def attack_self(cls) -> 'Move':
        """For when a Pokemon is confused."""
        move_info = MoveInfo(
            api_id=-1, name='attack_self', type=Type.NORMAL, power=40, total_pp=10,
            damage_class=DamageClass.PHYSICAL, healing=0, drain=0, high_crit_ratio=False,
            hit_info=HitInfo(min_hits=1, max_hits=1), accuracy=None, priority=0
        )
        return Move(move_info, pp=move_info.total_pp)

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
    BURNED = 3
    PARALYZED = 4
    BOUND = 5
    POISONED = 6
    CONFUSED = 7
    BADLY_POISONED = 8


@dataclass
class Pokemon:
    species: PokemonSpecies
    # These are calculated without considering IV's and EV's
    stats: PokemonStats
    hp: int
    move_set: tuple[Move, Move, Move, Move]
    nickname: str
    level: int = 100
    # Damage multiplier that increments every turn a Pokemon is badly poisoned
    dmg_multiplier: int = 1
    # The number of turns left in the Pokemon's confusion status
    confusion_turns: int = 0
    # The number of turns left in the Pokemon's bound status
    bound_turns: int = 0

    statuses: set[PokemonStatus] = field(default_factory=set)

    @property
    def fainted(self) -> bool:
        return self.hp == 0

    def apply_health_effect(self, health_delta: int):
        self.hp = min(max(self.hp + health_delta, 0), self.stats.total_hp)

    def has_status(self, status: PokemonStatus) -> bool:
        return status in self.statuses

    def get_status_damage(self, opponent_fainted: bool = False):
        if self.has_status(PokemonStatus.BURNED):
            print(f"{self.nickname} is hurt by its burn!")
            return math.floor(self.stats.total_hp / 16)
        if self.has_status(PokemonStatus.POISONED) and not opponent_fainted:
            print(f"{self.nickname} is hurt by poison!")
            return math.floor(self.stats.total_hp / 16)
        if self.has_status(PokemonStatus.BADLY_POISONED):
            print(f"{self.nickname} is hurt by poison!")
            if self.dmg_multiplier == 1:
                dmg = max(math.floor(self.stats.total_hp / 16), 1)
                self.dmg_multiplier += 1
                return dmg
            else:
                dmg = self.dmg_multiplier * math.floor(self.stats.total_hp / 16)
                if self.dmg_multiplier < 15:
                    self.dmg_multiplier += 1
                    return dmg
        if self.has_status(PokemonStatus.BOUND):
            print(f"{self.nickname} is hurt by being bound!")
            return math.floor(self.stats.total_hp / 16)
        return 0


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
