import requests

from scrapers.move_scraper import MoveScraper
from scrapers.pokemon_scraper import PokemonScraper

if __name__ == '__main__':
    resp = requests.get("https://pokeapi.co/api/v2/generation/1")
    gen1_data = resp.json()

    move_scraper = MoveScraper()
    moves = move_scraper.scrape(gen1_data)

    poke_scraper = PokemonScraper(moves)
    all_pokemon = poke_scraper.scrape(gen1_data)
    print("Done")
