import math
import random

from models import Pokemon, Move, MoveResult, DamageClass, Type


class Battle:
    def is_crit(self, attacking_pokemon: Pokemon, move_used: Move) -> bool:
        threshold = (attacking_pokemon.base_stats.speed / 2)
        if move_used.high_crit_ratio:
            threshold *= 8
        threshold = min(threshold, 255)
        threshold = math.floor(threshold)
        rand_val = random.randint(0, 255)
        return rand_val < threshold

    def _calc_modifier(self, attacking_pokemon: Pokemon, defending_pokemon: Pokemon, move_used: Move) -> float:
        rand_modifier = random.uniform(0.85, 1.0)
        stab = 1.5 if move_used.type in attacking_pokemon.types else 1
        type_modifier = Type.dmg_modifier(move_used.type, defending_pokemon.types[0])
        if len(defending_pokemon.types) > 1:
            type_modifier *= Type.dmg_modifier(move_used.type, defending_pokemon.types[1])
        return rand_modifier * stab * type_modifier

    def calc_dmg(self, attacking_pokemon: Pokemon, defending_pokemon: Pokemon, move_used: Move) -> int:
        effective_lvl = attacking_pokemon.level * (2 if self.is_crit(attacking_pokemon, move_used) else 1)
        ad_ratio = attacking_pokemon.stats.attack // defending_pokemon.stats.defense \
            if move_used.damage_class == DamageClass.PHYSICAL \
            else attacking_pokemon.stats.special // defending_pokemon.stats.special
        modifier = self._calc_modifier(attacking_pokemon, defending_pokemon, move_used)
        return math.floor(((((2 * effective_lvl // 5) + 2) * move_used.power * ad_ratio // 50) + 2) * modifier)

    def use_move(self, attacking_pokemon: Pokemon, defending_pokemon: Pokemon,
                 move_used: Move) -> tuple[MoveResult, MoveResult]:
        dmg_dealt = min(1, self.calc_dmg(attacking_pokemon, defending_pokemon, move_used))
        drain_num = move_used.drain * dmg_dealt if move_used.drain else 0
        if drain_num < 0:
            recoil = drain_num
            self_heal = 0
        else:
            recoil = 0
            self_heal = drain_num
        return MoveResult(heal=self_heal, dmg=recoil), MoveResult(heal=0, dmg=dmg_dealt)
