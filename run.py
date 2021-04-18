from battle_strategies import FullyRandomStrategy, ApproxQLearningStrategy
from data_store import DataStore
from gameplay import Battle
from generator import PokemonGenerator
from models import Trainer

if __name__ == '__main__':
    data_store = DataStore()
    generator = PokemonGenerator(data_store.all_pokemon)

    pokemon_a, pokemon_b = generator.generate(2)

    q_strat = ApproxQLearningStrategy(gamma=0.9, alpha=0.5, epsilon=0.2, num_episodes=3)

    battle = Battle(Trainer("Trainer A", pokemon_a, q_strat),
                    Trainer("Trainer B", pokemon_b, FullyRandomStrategy()))
    battle.run()
