from battle_strategies import FullyRandomStrategy
from data_store import DataStore
from gameplay import Battle
from generator import PokemonGenerator
from models import Trainer

if __name__ == '__main__':
    data_store = DataStore()
    generator = PokemonGenerator(data_store.all_pokemon)

    pokemon_a, pokemon_b = generator.generate(2)

    battle = Battle(Trainer("Trainer A", pokemon_a, FullyRandomStrategy()),
                    Trainer("Trainer B", pokemon_b, FullyRandomStrategy()))
    battle.run()
