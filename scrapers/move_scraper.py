import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests

from models import Move, DamageClass, HitCountInfo, Type

logger = logging.getLogger(__name__)


class MoveScraper:
    def __init__(self):
        self.blacklist: set[str] = {"fly", "dig", "dream-eater", "self-destruct"}
        self.high_crit_ratio_moves: set[str] = {"crabhammer", "karate-chop", "razor-leaf", "slash"}

    def _scrape_move(self, move_url: str) -> Optional[Move]:
        move_data = requests.get(move_url).json()
        if move_data["name"] in self.blacklist:
            return None

        # TODO: Support status moves?
        if move_data["damage_class"]["name"].upper() not in [x.value for x in DamageClass]:
            logger.info(f"IGNORED STATUS MOVE: {move_data['name']} | {move_data['id']}")
            return None

        if move_data["past_values"]:
            if len(move_data["past_values"]) == 0:
                logger.warning(f"MULTIPLE PAST VALUES DETECTED: {move_data['name']} | {move_data['id']}")

            # Use past values instead
            move_data.update({k: v for k, v in move_data["past_values"][0].items()
                              if k in ["accuracy", "power", "type", "pp"] and v is not None})

        if move_data["power"] is None:
            logger.info(f"IGNORED NON-STANDARD DAMAGING MOVE: {move_data['name']} | {move_data['id']}")
            return None

        try:
            min_hits = move_data["meta"]["min_hits"]
            max_hits = move_data["meta"]["max_hits"]
            hit_count_info = HitCountInfo.as_standard() if min_hits is None and max_hits is None \
                else HitCountInfo(min_hits=min_hits, max_hits=max_hits)

            return Move(
                api_id=move_data["id"],
                name=move_data["name"],
                type=Type(move_data["type"]["name"].upper()),
                power=move_data["power"],
                pp=move_data["pp"],
                damage_class=DamageClass(move_data["damage_class"]["name"].upper()),
                high_crit_ratio=(move_data["name"] in self.high_crit_ratio_moves),
                healing=(move_data["meta"]["healing"] / 100),
                drain=(move_data["meta"]["drain"] / 100),
                hit_count_info=hit_count_info,
                accuracy=move_data["accuracy"]
            )
        except ValueError as e:
            raise e

    def scrape(self, top_level_data: dict) -> list[Move]:
        move_urls = [move["url"] for move in top_level_data["moves"]]
        with ThreadPoolExecutor() as executor:
            results = executor.map(self._scrape_move, move_urls)
            moves = [x for x in results if x]
        return moves
