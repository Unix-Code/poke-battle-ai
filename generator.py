import dataclasses
import random

from models import PokemonStats, PokemonSpecies, Pokemon, Move


class PokemonGenerator:
    def __init__(self, all_pokemon: list[PokemonSpecies]):
        # Makes it more interesting than generating pokemon with empty learnsets or only 1 possible move
        self.all_pokemon = [pokemon for pokemon in all_pokemon if len(pokemon.learn_set) > 1]
        self.names = ["Bob", "Bill", "John", "Mary", "Susan"]

    def _calc_stat(self, base_stat_val: int, level: int, is_hp: bool = False) -> int:
        return ((2 * base_stat_val * level) // 100) + level + (10 if is_hp else 5)

    def calc_all_stats(self, base_stats: PokemonStats, level: int) -> PokemonStats:
        full_stats = PokemonStats(**{f.name: self._calc_stat(getattr(base_stats, f.name), level, is_hp=(f.name == "hp"))
                                     for f in dataclasses.fields(PokemonStats)})
        return full_stats

    def _random_moves(self, poke_species: PokemonSpecies) -> tuple[Move, Move, Move, Move]:
        if len(poke_species.learn_set) == 0:
            raise ValueError("Can't pick random moves from an empty learn set")
        move_infos = random.sample(poke_species.learn_set, min(len(poke_species.learn_set), 4))
        # noinspection PyTypeChecker
        return tuple(Move(move_info, pp=move_info.total_pp) for move_info in move_infos)

    def _random_name(self) -> str:
        return random.choice([name for name in self.names])

    def _pokemon_from_species(self, poke_species: PokemonSpecies, level: int = 100) -> Pokemon:
        full_stats = self.calc_all_stats(poke_species.base_stats, level)
        move_set = self._random_moves(poke_species)
        nickname = self._random_name()
        return Pokemon(poke_species, hp=full_stats.total_hp,
                       stats=full_stats, move_set=move_set, nickname=nickname)

    def generate(self, n: int = 1) -> list[Pokemon]:
        pokemon_species = random.choices(self.all_pokemon, k=n)
        generated_pokemon = [self._pokemon_from_species(species) for species in pokemon_species]
        return generated_pokemon
