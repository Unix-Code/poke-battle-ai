import copy
import random
from abc import ABC, abstractmethod
from collections import defaultdict

from gameplay import Battle
from models import Move, Pokemon


class BattleStrategy(ABC):
    @abstractmethod
    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon, trainer_ind: int) -> Move:
        raise NotImplementedError()


class FullyRandomStrategy(BattleStrategy):
    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon, trainer_ind: int) -> Move:
        return random.choice(curr_pokemon.move_set)


class ApproxQLearningStrategy(BattleStrategy):

    def __init__(self, gamma: float, alpha: float, epsilon: float, num_episodes: int):
        self.gamma = gamma
        self.alpha = alpha
        self.epsilon = epsilon
        self.num_episodes = num_episodes
        # Initialized for real during training
        self.weights = None
        # Since the features will need to be access multiple times per state/move pair,
        # cache them the first time they are calculated
        self.features_cache = defaultdict(lambda: [])

    def _is_terminal(self, state: tuple[Pokemon, Pokemon]):
        return state[0].hp <= 0 or state[1].hp <= 0

    def _get_features(self, state: tuple[Pokemon, Pokemon], move: Move):
        # Use a tuple of HP values as the state and move API IDs when storing/accessing features
        cache_entry = self.features_cache[((state[0].hp, state[1].hp), move.info.api_id)]
        if cache_entry:
            return cache_entry

        features = []
        # TODO: write feature functions such that f_i(state, move) returns a useful value
        # Then append each value to the `features` list above
        self.features_cache[((state[0].hp, state[1].hp), move.info.api_id)] = features
        return features

    def _get_q_value(self, state: tuple[Pokemon, Pokemon], move: Move) -> float:
        features = self._get_features(state, move)
        q_val = 0
        for feature_ind, feature in enumerate(features):
            q_val += self.weights[feature_ind] * feature
        return q_val

    def _choose_move_from_policy(self, state: tuple[Pokemon, Pokemon],
                                 epsilon: bool = False) -> Move:
        if epsilon and random.random() >= self.epsilon:
            return random.choice(state[0].move_set)
        else:
            best_move = state[0].move_set[0], -1
            for move in state[0].move_set:
                val = self._get_q_value(state, move)
                if val > best_move[1]:
                    best_move = move, val
            return best_move[0]

    def _transition(self, move: Move, attacker: Pokemon, defender: Pokemon,
                    trainer_ind: int) -> tuple[float, tuple[Pokemon, Pokemon]]:
        initial_attacker_hp = attacker.hp
        initial_defender_hp = defender.hp
        # Simulate one round of the battle
        battle = Battle(training_mode=True)
        battle.use_move(attacker, defender, move, trainer_ind)
        battle.use_move(defender, attacker, random.choice(defender.move_set), (trainer_ind + 1) % 2)
        attacker_hp_delta = attacker.hp - initial_attacker_hp
        defender_hp_delta = defender.hp - initial_defender_hp

        # The delta will most likely be negative, so the reward will be positive
        # TODO: Maybe come up with a better reward value
        reward = -defender_hp_delta + attacker_hp_delta
        return reward, (attacker, defender)

    def _train(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon, trainer_ind: int):
        self.weights = defaultdict(lambda: 0.0)
        for _ in range(self.num_episodes):
            state = curr_pokemon, opposing_pokemon
            while not self._is_terminal(state):
                move = self._choose_move_from_policy(state)
                reward, next_state = self._transition(
                    move, copy.deepcopy(state[0]), copy.deepcopy(state[1]), trainer_ind
                )
                next_move = self._choose_move_from_policy(next_state, True)
                difference = (
                    reward
                    + self._get_q_value(next_state, next_move)
                    - self._get_q_value(state, move)
                )
                features = self._get_features(state, move)
                for i, feature in enumerate(features):
                    self.weights[i] = self.weights[i] + self.alpha * difference * features[i]
                state = next_state

    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon, trainer_ind: int) -> Move:
        if self.weights is None:
            self._train(curr_pokemon, opposing_pokemon, trainer_ind)
        return self._choose_move_from_policy((curr_pokemon, opposing_pokemon))
