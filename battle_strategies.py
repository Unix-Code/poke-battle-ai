import copy
import itertools
import math
import random
from abc import ABC, abstractmethod
from collections import defaultdict

from gameplay import Battle
from generator import PokemonGenerator
from models import Move, Pokemon, Trainer, Type, DamageClass


class BattleStrategy(ABC):
    @abstractmethod
    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon) -> Move:
        raise NotImplementedError()


class FullyRandomStrategy(BattleStrategy):
    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon) -> Move:
        return random.choice(curr_pokemon.move_set)


class InteractiveBattleStrategy(BattleStrategy):
    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon) -> Move:
        print("Please select a move:")
        for move_ind, move in enumerate(curr_pokemon.move_set):
            print(f"{move_ind + 1}. {move.display_name}")
        print()
        print("> ", end="")
        chosen_ind = int(input()) - 1
        return curr_pokemon.move_set[chosen_ind]


class BaseQLearningStrategy(BattleStrategy, ABC):
    def __init__(self, gamma: float, alpha: float, epsilon: float, softmax: bool):
        self.gamma = gamma
        self.alpha = alpha
        self.epsilon = epsilon
        self.episodes_trained = 0
        self.training = False
        self._move = None
        self.softmax = softmax  # Whether to use softmax or epsilon-greedy exploration

    def _health_buckets(self, pokemon: Pokemon, num_buckets: int = 4) -> int:
        return num_buckets - math.ceil(num_buckets * (pokemon.hp / pokemon.stats.total_hp))

    def _power_buckets(self, move: Move, num_buckets: int = 3) -> int:
        return num_buckets - math.ceil(num_buckets * (move.info.power / 250))

    def _poke_type_indices(self, pokemon: Pokemon) -> tuple[int, int]:
        all_types = list(Type)
        poke_types = pokemon.species.types
        first_type_ind = all_types.index(poke_types[0])
        if len(poke_types) == 1:
            return first_type_ind, 0
        second_type_ind = all_types.index(poke_types[1]) + 1
        return first_type_ind, second_type_ind

    @abstractmethod
    def _get_q_value(self, state: tuple[Pokemon, Pokemon], move: Move) -> float:
        raise NotImplementedError()

    def _choose_move_from_policy(self, state: tuple[Pokemon, Pokemon], epsilon: bool = False) -> Move:
        if not self.softmax:
            # Epsilon Greedy
            if epsilon and random.random() >= self.epsilon:
                # Explore - only if training
                return random.choice(state[0].move_set)
            # Exploit
            max_q_val = max(self._get_q_value(state, move) for move in state[0].move_set)
            best_moves = [move for move in state[0].move_set if self._get_q_value(state, move) == max_q_val]
            return random.choice(best_moves)
        else:
            if not epsilon:
                # Exploit
                max_q_val = max(self._get_q_value(state, move) for move in state[0].move_set)
                best_moves = [move for move in state[0].move_set if self._get_q_value(state, move) == max_q_val]
                return random.choice(best_moves)
            # Softmax Exploration
            temperature = 1  # TODO: Change this
            raw_probabilities = [math.e ** (self._get_q_value(state, move) / temperature) for move in state[0].move_set]
            probabilities = [(prob / sum(raw_probabilities)) for prob in raw_probabilities]
            chosen_move = random.choices(state[0].move_set, weights=probabilities, k=1)[0]
            return chosen_move

    def _transition(self, battle: Battle) -> tuple[float, tuple[Pokemon, Pokemon]]:
        initial_self_hp = battle.trainers[0].pokemon.hp
        initial_opponent_hp = battle.trainers[1].pokemon.hp

        # Simulate one round of the battle
        battle.play_turn()

        own_pokemon = copy.deepcopy(battle.trainers[0].pokemon)
        opponent_pokemon = copy.deepcopy(battle.trainers[1].pokemon)

        self_hp = own_pokemon.hp
        opponent_hp = opponent_pokemon.hp

        # TODO: Improve reward calculation
        # reward = (-2 * (opponent_hp - initial_opponent_hp) / initial_opponent_hp) + ((self_hp - initial_self_hp) / initial_self_hp)
        #
        # type_mod_weight = math.prod(Type.dmg_modifier(at, dt)
        #                             for at, dt in itertools.product(own_pokemon.species.types,
        #                                                             opponent_pokemon.species.types))
        # type_mod = ((1 / type_mod_weight) if type_mod_weight > 0 else 20)
        # reward *= 100
        # if reward > 0:
        #     reward *= type_mod
        # else:
        #     reward /= type_mod

        if own_pokemon.fainted:
            reward = -10
        elif opponent_pokemon.fainted:
            reward = 10
        else:
            reward = 0

        return reward, (own_pokemon, opponent_pokemon)

    def _new_battle(self, pokemon_generator: PokemonGenerator) -> Battle:
        pokemon_a, pokemon_b = pokemon_generator.generate(2)
        battle = Battle(Trainer("self", pokemon_a, self),
                        Trainer("sparring partner", pokemon_b, FullyRandomStrategy()),
                        training_mode=True)
        return battle

    @abstractmethod
    def _update(self, reward, action: Move, state: tuple[Pokemon, Pokemon], next_state: tuple[Pokemon, Pokemon]):
        raise NotImplementedError()

    def train(self, pokemon_generator: PokemonGenerator, num_episodes: int):
        self.training = True

        for _ in range(num_episodes):
            battle = self._new_battle(pokemon_generator)

            state = copy.deepcopy(battle.trainers[0].pokemon), copy.deepcopy(battle.trainers[1].pokemon)
            while not battle.finished:
                self._move = self._choose_move_from_policy(state, epsilon=True)
                current_action = copy.deepcopy(self._move)
                # Use Battle here instead of state + action for simplicity
                reward, next_state = self._transition(battle)
                self._update(reward, current_action, state, next_state)
                state = next_state

            self.episodes_trained += 1
        self.training = False

    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon) -> Move:
        if self.training and self._move is not None:
            # If we're training and have already selected a move based on the policy,
            # make sure to pick it when prompted by simulated Battle
            return self._move
        return self._choose_move_from_policy((curr_pokemon, opposing_pokemon))


class QLearningStrategy(BaseQLearningStrategy):
    def __init__(self, gamma: float, alpha: float, epsilon: float, softmax: bool = False):
        super().__init__(gamma, alpha, epsilon, softmax)
        self._q_values = defaultdict(lambda: 0.0)

    def _extract_state(self, state: tuple[Pokemon, Pokemon]) -> tuple[int, int, int, int, int, int, int, int]:
        # This is already somewhat approximated but not fully with features
        pokemon_a, pokemon_b = state
        type_a1, type_a2 = self._poke_type_indices(pokemon_a)
        type_b1, type_b2 = self._poke_type_indices(pokemon_b)
        return (
            self._health_buckets(pokemon_a),
            self._health_buckets(pokemon_b),
            int(pokemon_a.stats.attack > pokemon_a.stats.special),
            int(pokemon_b.stats.defense > pokemon_b.stats.special),
            type_a1,
            type_a2,
            type_b1,
            type_b2
        )

    def _extract_action(self, move: Move) -> tuple[int, int]:
        return (
            list(Type).index(move.info.type),
            self._power_buckets(move)
        )

    def _get_q_value(self, state: tuple[Pokemon, Pokemon], move: Move) -> float:
        if state[0].fainted:
            # Losing terminal state
            return 0
        extracted_state = self._extract_state(state)
        extracted_action = self._extract_action(move)
        return self._q_values[(extracted_state, extracted_action)]

    def _update(self, reward, action: Move, state: tuple[Pokemon, Pokemon], next_state: tuple[Pokemon, Pokemon]):
        next_action = self._choose_move_from_policy(next_state, epsilon=False)
        q_val = self._get_q_value(state, action)
        td_error = (
                reward
                + (self.gamma * self._get_q_value(next_state, next_action))
                - q_val
        )
        self._q_values[(self._extract_state(state), self._extract_action(action))] = q_val + self.alpha * td_error


class ApproxQLearningStrategy(BaseQLearningStrategy):
    def __init__(self, gamma: float, alpha: float, epsilon: float, softmax: bool = False):
        super().__init__(gamma, alpha, epsilon, softmax)
        # Initialized for real during training
        self.weights = defaultdict(lambda: 0.0)

    def load_weights(self, weights: dict[int, float]):
        self.weights.update(weights)

    def _get_features(self, state: tuple[Pokemon, Pokemon], move: Move):
        # TODO: Optimize feature extraction
        pokemon_a, pokemon_b = state
        type_mod = Type.dmg_modifier(move.info.type, pokemon_b.species.types[0]) * \
               (Type.dmg_modifier(move.info.type, pokemon_b.species.types[1]) if len(pokemon_b.species.types) > 1 else 1)
        type_mod /= 4  # Normalize the value between 0 and 1

        dmg_class_mod_stat_atk, dmg_class_mod_stat_def = (pokemon_a.stats.attack, pokemon_b.stats.defense) \
            if move.info.damage_class is DamageClass.PHYSICAL else (pokemon_a.stats.special, pokemon_b.stats.special)
        dmg_class_mod = (dmg_class_mod_stat_atk / (dmg_class_mod_stat_atk + dmg_class_mod_stat_def))
        return [
            pokemon_a.hp / pokemon_a.stats.total_hp,
            pokemon_b.hp / pokemon_b.stats.total_hp,
            dmg_class_mod,
            type_mod,
            (move.info.power / 250),
            (move.info.accuracy if move.info.accuracy is not None else 1),
            # move.info.hit_info.min_hits,
            # move.info.hit_info.max_hits,
            int(move.info.high_crit_ratio),
            # move.info.priority,
            move.info.drain,
            # move.info.healing,
            # int(move.pp == 0)
            # TODO: Add more features
        ]

    def _get_q_value(self, state: tuple[Pokemon, Pokemon], move: Move) -> float:
        if state[0].fainted:
            # Losing terminal state
            return 0
        features = self._get_features(state, move)
        q_val = sum(self.weights[ind] * feature for ind, feature in enumerate(features))
        return q_val

    def _update(self, reward, action: Move, state: tuple[Pokemon, Pokemon], next_state: tuple[Pokemon, Pokemon]):
        next_action = self._choose_move_from_policy(next_state, epsilon=False)
        q_val = self._get_q_value(state, action)
        td_error = (
                reward
                + (self.gamma * self._get_q_value(next_state, next_action))
                - q_val
        )
        features = self._get_features(state, action)
        for i, feature in enumerate(features):
            self.weights[i] += self.alpha * td_error * feature
