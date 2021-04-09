import random
from abc import ABC, abstractmethod

from models import Move, Pokemon


class BattleStrategy(ABC):
    @abstractmethod
    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon) -> Move:
        raise NotImplementedError()


class FullyRandomStrategy(BattleStrategy):
    def pick_move(self, curr_pokemon: Pokemon, opposing_pokemon: Pokemon) -> Move:
        return random.choice(curr_pokemon.move_set)
