import math
import random
from typing import Optional

from models import (
    Pokemon, Move, DamageClass, Type, MoveInfo, PokemonSpecies, Trainer, PokemonStatus, Ailment
)

ATTACK_SELF = "attack_self"


class Battle:
    LENGTH_MODIFIER = 2  # Effectively: Damage is divided by this with the intention of lengthening battles

    def __init__(self, *trainers: Trainer):
        self.turn_count: int = 0
        self.trainers: tuple[Trainer, ...] = trainers
        self.move_queue: list[Optional[Move]] = [None, None]

    def _calc_move_order_sort(self, chosen_move: tuple[int, Move]) -> tuple[int, int, int]:
        trainer_ind, move = chosen_move
        poke_speed = self.trainers[trainer_ind].pokemon.stats.speed
        return move.info.priority, poke_speed, random.randint(0, 1000)  # random move order if all other things equal

    def is_crit(self, attacking_pokemon: PokemonSpecies, move_used: MoveInfo) -> bool:
        if move_used.name == ATTACK_SELF:
            return False

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

        if defending_pokemon.has_status(PokemonStatus.INVULNERABLE):
            return False

        accuracy_val = math.floor(move_used.accuracy * 255)
        threshold = max(min(accuracy_val, 255), 1)
        # Yes this does actually implement the possible miss for a 100% accuracy move bug in Gen 1
        rand_val = random.randint(0, 255)
        return rand_val < threshold

    def _calc_modifier(self, attacking_pokemon: PokemonSpecies, defending_pokemon: PokemonSpecies,
                       move_used: MoveInfo) -> float:
        rand_modifier = random.uniform(0.85, 1.0)
        if move_used.name == ATTACK_SELF:
            return rand_modifier

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

    def apply_move_rules(self, attacking_pokemon: Pokemon, move_used: Move, trainer_ind: int) -> bool:
        if move_used.info.hit_info.has_invulnerable_phase:
            if not attacking_pokemon.has_status(PokemonStatus.INVULNERABLE):
                print(f"{attacking_pokemon.nickname} gains invulnerability for the turn")
                attacking_pokemon.statuses.add(PokemonStatus.INVULNERABLE)
            else:
                # Remove the status here since we can assume that each move that makes
                # a pokemon invulnerable only does so for 1 turn.
                attacking_pokemon.statuses.remove(PokemonStatus.INVULNERABLE)

        if move_used.info.hit_info.requires_charge:
            if not attacking_pokemon.has_status(PokemonStatus.CHARGING):
                print(f"{attacking_pokemon.nickname} charges up {move_used.display_name}")
                attacking_pokemon.statuses.add(PokemonStatus.CHARGING)
                self.move_queue[trainer_ind] = move_used
                return True
            else:
                # Reset whether the move is charged
                attacking_pokemon.statuses.remove(PokemonStatus.CHARGING)

        if move_used.info.hit_info.has_recharge:
            # This logically happens at the end of using a move, but can be done here as well
            attacking_pokemon.statuses.add(PokemonStatus.RECHARGING)

        if move_used.info.hit_info.self_destructing:
            # Self Destruction occurs on hit or miss
            print(f"{attacking_pokemon.nickname} self-destructed")
            attacking_pokemon.hp = 0

        return False

    def apply_ailment(self, move_used: Move, defending_pokemon: Pokemon):
        ailment = move_used.info.ailment
        if (
            any(status.non_volatile for status in defending_pokemon.statuses)
            and ailment.non_volatile
        ):
            # A Pokémon cannot gain a non-volatile status if it's already afflicted by another one.
            return

        if ailment == Ailment.UNKNOWN:
            # Tri Attack was used
            # We don't support freeze, so return if it (i.e. unknown) is selected randomly
            ailment = random.choice([Ailment.UNKNOWN, Ailment.BURN, Ailment.PARALYSIS])
            if ailment == Ailment.UNKNOWN:
                return
        # Fire-type Pokemon cannot be burned by a Fire-type move
        if ailment == Ailment.BURN and (
            Type.FIRE not in defending_pokemon.species.types or move_used.info.type != Type.FIRE
        ):
            print(f"{defending_pokemon.nickname} is burned by the attack!")
            defending_pokemon.statuses.add(PokemonStatus.BURNED)
            # TODO: Halve its Attack
        # Ground-type Pokemon cannot be paralyzed by an Electric-type move
        elif ailment == Ailment.PARALYSIS and (
            Type.GROUND not in defending_pokemon.species.types
            or move_used.info.type != Type.ELECTRIC
        ):
            print(f"{defending_pokemon.nickname} is paralyzed by the attack!")
            defending_pokemon.statuses.add(PokemonStatus.PARALYZED)
            # TODO: Decrease Speed by 75%
        # Poison-type Pokemon cannot be poisoned
        elif ailment == Ailment.POISON and Type.POISON not in defending_pokemon.species.types:
            if move_used.info.api_id == 92:
                # The "Toxic" move was used
                print(f"{defending_pokemon.nickname} is badly poisoned by the attack!")
                defending_pokemon.statuses.add(PokemonStatus.BADLY_POISONED)
            else:
                print(f"{defending_pokemon.nickname} is poisoned by the attack!")
                defending_pokemon.statuses.add(PokemonStatus.POISONED)
        elif ailment == Ailment.CONFUSION:
            print(f"{defending_pokemon.nickname} is confused by the attack!")
            defending_pokemon.statuses.add(PokemonStatus.CONFUSED)
            defending_pokemon.confusion_turns = random.randint(1, 5)
        # Pokemon can only be bound by one binding move at a time
        elif ailment == Ailment.TRAP and PokemonStatus.BOUND not in defending_pokemon.statuses:
            print(f"{defending_pokemon.nickname} is trapped by the attack!")
            defending_pokemon.statuses.add(PokemonStatus.BOUND)
            defending_pokemon.bound_turns = random.choices(
                [2, 3, 4, 5], [0.375, 0.375, 0.125, 0.125]
            )[0]

    def use_move(self, attacking_pokemon: Pokemon, defending_pokemon: Pokemon,
                 move_to_use: Move, trainer_ind: int):
        # Decrements pp or end up struggling
        move_used = move_to_use.use()

        if attacking_pokemon.has_status(PokemonStatus.PARALYZED) and random.random() < 0.25:
            print(f"{attacking_pokemon.nickname} is fully paralyzed! It can't move!")
            return

        if attacking_pokemon.has_status(PokemonStatus.CONFUSED):
            attacking_pokemon.confusion_turns -= 1
            if attacking_pokemon.confusion_turns == 0:
                print(f"{attacking_pokemon.nickname} snapped out of its confusion!")
                attacking_pokemon.statuses.remove(PokemonStatus.CONFUSED)
            elif random.random() < 0.5:
                # The Pokemon will attack itself
                # These variables are changed so the damage can still be calculated the same way
                move_to_use = Move.attack_self()
                defending_pokemon = attacking_pokemon

        if attacking_pokemon.has_status(PokemonStatus.BOUND):
            if attacking_pokemon.bound_turns == 0:
                print(f"{attacking_pokemon.nickname} broke free! It is no longer trapped!")
                attacking_pokemon.statuses.remove(PokemonStatus.BOUND)
            else:
                print(f"{attacking_pokemon.nickname} is trapped! It can't move!")
                attacking_pokemon.apply_health_effect(-attacking_pokemon.get_status_damage())
                attacking_pokemon.bound_turns -= 1
                return

        skip_move = self.apply_move_rules(attacking_pokemon, move_used, trainer_ind)
        if skip_move:
            return

        if not self.is_hit(attacking_pokemon, defending_pokemon, move_to_use.info):
            print(f"{attacking_pokemon.nickname}'s move ({move_used.display_name}) missed!")
            return

        # Calculate damage of each hit (Gen 1: only 1st can crit and none are accuracy-dependent)
        hit_damages = []
        for ind in range(move_to_use.info.hit_info.num_hits()):
            raw_dmg = self.calc_dmg(attacking_pokemon, defending_pokemon, move_used.info)
            dmg_dealt = max(1, raw_dmg)
            hit_damages.append(dmg_dealt)
        total_dmg_dealt = sum(hit_damages) // self.LENGTH_MODIFIER

        attacker_health_delta = math.floor(move_used.info.drain * total_dmg_dealt)
        recoil = attacker_health_delta < 0
        # Apply damage from status ailments
        attacker_health_delta -= attacking_pokemon.get_status_damage(
            total_dmg_dealt > defending_pokemon.hp
        )

        if move_used.info.name == ATTACK_SELF:
            print(f"{attacking_pokemon.nickname} is confused! It hurt itself in its confusion!")
            attacking_pokemon.apply_health_effect(attacker_health_delta)
            return

        print(f"{attacking_pokemon.nickname} dealt {total_dmg_dealt} damage{' in total' if len(hit_damages) > 1 else ''}.")
        if attacker_health_delta > 0:
            print(f"{attacking_pokemon.nickname} healed itself for {attacker_health_delta}")
        elif attacker_health_delta < 0 and recoil:
            print(f"{attacking_pokemon.nickname} was hit with {attacker_health_delta} recoil damage")

        if move_used.info.ailment:
            if random.random() < move_used.info.ailment_chance:
                self.apply_ailment(move_used, defending_pokemon)

        defender_health_delta = -total_dmg_dealt
        # Adjust health bars after using move
        attacking_pokemon.apply_health_effect(attacker_health_delta)
        defending_pokemon.apply_health_effect(defender_health_delta)

    def choose_moves(self) -> list[tuple[int, Move]]:
        chosen_moves = []

        for trainer_ind, trainer in enumerate(self.trainers):
            if trainer.pokemon.has_status(PokemonStatus.CHARGING):
                chosen_move = self.move_queue[trainer_ind]
                self.move_queue[trainer_ind] = None
            elif trainer.pokemon.has_status(PokemonStatus.RECHARGING):
                chosen_move = None
                print(f"{trainer.name}'s {trainer.pokemon.nickname} must recharge")
                trainer.pokemon.statuses.remove(PokemonStatus.RECHARGING)
            else:
                chosen_move = trainer.pick_move(self.trainers[(trainer_ind + 1) % len(self.trainers)].pokemon)
            if chosen_move is not None:
                chosen_moves.append((trainer_ind, chosen_move))
        return chosen_moves

    def play_turn(self):
        self.turn_count += 1
        chosen_moves = self.choose_moves()
        for trainer_ind, move_to_use in sorted(chosen_moves, key=self._calc_move_order_sort, reverse=True):
            attacking_trainer = self.trainers[trainer_ind]
            defending_trainer = self.trainers[(trainer_ind + 1) % len(self.trainers)]
            if attacking_trainer.cannot_continue or defending_trainer.cannot_continue:
                # If a pokemon faints in the middle of a turn, end the match
                break
            print(f"{attacking_trainer.name}'s {attacking_trainer.pokemon.nickname} tried to use: {move_to_use.display_name}")
            self.use_move(attacking_trainer.pokemon, defending_trainer.pokemon, move_to_use, trainer_ind)

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
