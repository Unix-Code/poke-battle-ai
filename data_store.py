import pickle
from pathlib import Path

import requests

from models import PokemonSpecies, MoveInfo
from scrapers import MoveScraper, PokemonScraper


class DataStore:
    def __init__(self, moves_cache: str = "./data/all_moves.data", pokemon_cache: str = "./data/all_pokemon.data"):
        gen1_data = None
        if Path(moves_cache).exists():
            with open(moves_cache, "rb") as f:
                self.all_moves: list[MoveInfo] = pickle.load(f)
        else:
            resp = requests.get("https://pokeapi.co/api/v2/generation/1")
            gen1_data = resp.json()
            move_scraper = MoveScraper()
            self.all_moves = move_scraper.scrape(gen1_data)
            with open(moves_cache, "wb") as f:
                pickle.dump(self.all_moves, f)

        if Path(pokemon_cache).exists():
            with open(pokemon_cache, "rb") as f:
                self.all_pokemon: list[PokemonSpecies] = pickle.load(f)
        else:
            if gen1_data is None:
                resp = requests.get("https://pokeapi.co/api/v2/generation/1")
                gen1_data = resp.json()
            poke_scraper = PokemonScraper(self.all_moves)
            self.all_pokemon: list[PokemonSpecies] = poke_scraper.scrape(gen1_data)
            with open(pokemon_cache, "wb") as f:
                pickle.dump(self.all_pokemon, f)
