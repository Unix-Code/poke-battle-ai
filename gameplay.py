import math
import random

from models import Pokemon, Move, DamageClass, Type, MoveInfo, PokemonSpecies, Trainer


class Battle:
    LENGTH_MODIFIER = 2  # Effectively: Damage is divided by this with the intention of lengthening battles

    def __init__(self, *trainers: Trainer):
        self.turn_count = 0
        self.trainers = trainers

    def is_crit(self, attacking_pokemon: PokemonSpecies, move_used: MoveInfo) -> bool:
        threshold = (attacking_pokemon.base_stats.speed / 2)
        if move_used.high_crit_ratio:
            threshold *= 8
        threshold = min(threshold, 255)
        threshold = math.floor(threshold)
        rand_val = random.randint(0, 255)
        return rand_val < threshold

    def is_hit(self, attacking_pokemon: Pokemon, defending_pokemon: Pokemon, move_used: MoveInfo):
        # TODO: Account for stage multipliers (stat changers)
        if move_used.accuracy is None:
            return True
        accuracy_val = math.floor(move_used.accuracy * 255)
        threshold = max(min(accuracy_val, 255), 1)
        # Yes this does actually implement the possible miss for a 100% accuracy move bug in Gen 1
        rand_val = random.randint(0, 255)
        return rand_val < threshold

    def _calc_modifier(self, attacking_pokemon: PokemonSpecies, defending_pokemon: PokemonSpecies,
                       move_used: MoveInfo) -> float:
        rand_modifier = random.uniform(0.85, 1.0)
        stab = 1.5 if move_used.type in attacking_pokemon.types else 1
        type_modifier = Type.dmg_modifier(move_used.type, defending_pokemon.types[0])
        if len(defending_pokemon.types) > 1:
            type_modifier *= Type.dmg_modifier(move_used.type, defending_pokemon.types[1])
        return rand_modifier * stab * type_modifier

    def calc_dmg(self, attacking_pokemon: Pokemon, defending_pokemon: Pokemon, move_used: MoveInfo, hit_num=0) -> int:
        # For ease of use, these calculations don't floor until the end
        effective_lvl = attacking_pokemon.level * (2 if self.is_crit(attacking_pokemon.species, move_used) and hit_num == 0 else 1)
        ad_ratio = attacking_pokemon.stats.attack / defending_pokemon.stats.defense \
            if move_used.damage_class == DamageClass.PHYSICAL \
            else attacking_pokemon.stats.special / defending_pokemon.stats.special
        modifier = self._calc_modifier(attacking_pokemon.species, defending_pokemon.species, move_used)
        return math.floor(((((2 * effective_lvl / 5) + 2) * move_used.power * ad_ratio / 50) + 2) * modifier)

    def use_move(self, attacking_pokemon: Pokemon, defending_pokemon: Pokemon,
                 move_to_use: Move):
        # Decrements pp or end up struggling
        move_used = move_to_use.use()

        if not self.is_hit(attacking_pokemon, defending_pokemon, move_to_use.info):
            print(f"{attacking_pokemon.nickname}'s move ({move_used.display_name}) missed!")
            return

        # Calculate damage of each hit (Gen 1: only 1st can crit and none are accuracy-dependent)
        hit_damages = []
        for ind in range(move_to_use.info.hit_count_info.num_hits()):
            raw_dmg = self.calc_dmg(attacking_pokemon, defending_pokemon, move_used.info)
            dmg_dealt = max(1, raw_dmg)
            hit_damages.append(dmg_dealt)
        total_dmg_dealt = sum(hit_damages) // self.LENGTH_MODIFIER

        attacker_health_delta = math.floor(move_used.info.drain * total_dmg_dealt) if move_used.info.drain else 0

        print(f"{attacking_pokemon.nickname} dealt {total_dmg_dealt} damage{' in total' if len(hit_damages) > 1 else ''}.")
        if attacker_health_delta != 0:
            attacker_action_text = f"healed itself for {attacker_health_delta}" \
                if attacker_health_delta > 0 else f"was hit with {attacker_health_delta} recoil damage"
            print(f"{attacking_pokemon.nickname} {attacker_action_text}")

        defender_health_delta = -total_dmg_dealt
        # Adjust health bars after using move
        attacking_pokemon.apply_health_effect(attacker_health_delta)
        defending_pokemon.apply_health_effect(defender_health_delta)

    def play_turn(self):
        self.turn_count += 1
        chosen_moves = [
            (0, self.trainers[0].pick_move(self.trainers[1].pokemon)),
            (1, self.trainers[1].pick_move(self.trainers[0].pokemon))
        ]
        for trainer_ind, move_to_use in sorted(chosen_moves, key=lambda x: x[1].info.priority, reverse=True):
            attacking_trainer = self.trainers[trainer_ind]
            defending_trainer = self.trainers[(trainer_ind + 1) % len(self.trainers)]
            print(f"{attacking_trainer.name}'s {attacking_trainer.pokemon.nickname} tried to use: {move_to_use.display_name}")
            self.use_move(attacking_trainer.pokemon, defending_trainer.pokemon, move_to_use)

    def run(self):
        self.turn_count = 0
        trainer_a, trainer_b = self.trainers
        print(f"{trainer_a.name} with {trainer_a.pokemon.nickname} ({trainer_a.pokemon.species.display_name})", "VS",
              f"{trainer_b.name} with {trainer_b.pokemon.nickname} ({trainer_b.pokemon.species.display_name})")
        while not trainer_a.cannot_continue and not trainer_b.cannot_continue:
            print(f"----- Turn {self.turn_count} -----")
            print(f"{trainer_a.pokemon.nickname}: {trainer_a.pokemon.hp}/{trainer_a.pokemon.stats.total_hp}")
            print(f"{trainer_b.pokemon.nickname}: {trainer_b.pokemon.hp}/{trainer_b.pokemon.stats.total_hp}\n")
            self.play_turn()
        print(f"\n----- Battle Finished in {self.turn_count} turns. -----")
        if trainer_a.cannot_continue:
            print("Trainer B Wins!")
        elif trainer_b.cannot_continue:
            print("Trainer A Wins!")
