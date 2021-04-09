import json
from concurrent.futures import ThreadPoolExecutor

import requests

from models import Sprite, Type, PokemonStats, PokemonSpecies, MoveInfo


class PokemonScraper:
    def __init__(self, moves: list[MoveInfo]):
        self.moves = moves

    def _scrape_pokemon(self, poke_url: str) -> PokemonSpecies:
        with open("./data/poke_specials.json", "r") as f:
            data = json.load(f)
            special_stat_lookup = {entry["pokedex_id"]: entry["special"] for entry in data}

        poke_data = requests.get(poke_url).json()

        if poke_data["past_types"]:
            # Use past types (Gen 1) if present
            poke_data["types"] = poke_data["past_types"][0]["types"]

        gen1_sprites = poke_data["sprites"]["versions"]["generation-i"]["red-blue"]
        stat_lookup = {stat["stat"]["name"]: stat["base_stat"]
                       for stat in poke_data["stats"]
                       if stat["stat"]["name"] in ["hp", "attack", "defense", "speed"]}
        stat_lookup["total_hp"] = stat_lookup.pop("hp")

        base_stats = PokemonStats(**stat_lookup, special=special_stat_lookup[poke_data["id"]])

        raw_learn_set = {entry["move"]["name"] for entry in poke_data["moves"]
                         if entry["version_group_details"]
                         and entry["version_group_details"][0]["version_group"]["name"] == "red-blue"}

        return PokemonSpecies(
            api_id=poke_data["id"],
            name=poke_data["name"],
            sprite=Sprite(front=gen1_sprites["front_default"], back=gen1_sprites["back_default"]),
            types=[Type(t["type"]["name"].upper()) for t in sorted(poke_data["types"], key=lambda x: x["slot"])],
            base_stats=base_stats,
            learn_set={m for m in self.moves if m.name in raw_learn_set}
        )

    def scrape(self, top_level_data: dict) -> list[PokemonSpecies]:
        poke_urls = [p["url"].replace("pokemon-species", "pokemon") for p in top_level_data["pokemon_species"]]
        with ThreadPoolExecutor() as executor:
            results = executor.map(self._scrape_pokemon, poke_urls)
            pokemons = [x for x in results if x]
        return pokemons
