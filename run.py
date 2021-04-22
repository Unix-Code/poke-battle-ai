import time
from concurrent.futures import ThreadPoolExecutor

from battle_strategies import FullyRandomStrategy, ApproxQLearningStrategy, InteractiveBattleStrategy
from data_store import DataStore
from gameplay import Battle
from generator import PokemonGenerator, Matchup
from models import Trainer


if __name__ == '__main__':
    data_store = DataStore()
    generator = PokemonGenerator(data_store.all_pokemon)

    start = time.time()
    q_strat = ApproxQLearningStrategy(gamma=0.9, alpha=0.01, epsilon=0.1)
    q_strat.train(generator, num_episodes=10000)
    end = time.time()
    print(f"Training Time: {end - start}")

    num_test_runs = 1000

    pokemon_a, pokemon_b = generator.generate(2, Matchup.NEUTRAL)
    battle = Battle(Trainer("Trainer A", pokemon_a, q_strat),
                    Trainer("You", pokemon_b, InteractiveBattleStrategy()))
    battle.run()

    # def test_run(ind, matchup_type):
    #     pokemon_a, pokemon_b = generator.generate(2, matchup_type)
    #     battle = Battle(Trainer("Trainer A", pokemon_a, q_strat),
    #                     Trainer("Trainer B", pokemon_b, FullyRandomStrategy()),
    #                     training_mode=True)
    #     winner_ind = battle.run()
    #     return int(winner_ind == 0)
    #
    # import pprint; pprint.pprint(q_strat.weights)
    #
    # start = time.time()
    # with ThreadPoolExecutor() as executor:
    #     results = executor.map(lambda ind: test_run(ind, Matchup.ADVANTAGEOUS), range(num_test_runs // 2))
    #     num_advantaged_wins = sum(results)
    #     results = executor.map(lambda ind: test_run(ind, Matchup.DISADVANTAGEOUS), range(num_test_runs // 2))
    #     num_disadvantaged_wins = sum(results)
    #
    # end = time.time()
    # print(f"Testing Time: {end - start}")
    #
    # print(f"Strategy Total Win Rate: {(num_advantaged_wins + num_disadvantaged_wins) / num_test_runs * 100}%")
    # print(f"Strategy Advantaged Win Rate: {num_advantaged_wins / (num_test_runs / 2) * 100}%")
    # print(f"Strategy Disadvantaged Win Rate: {num_disadvantaged_wins / (num_test_runs / 2) * 100}%")
