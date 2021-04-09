import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests

from models import DamageClass, HitCountInfo, Type, MoveInfo

logger = logging.getLogger(__name__)


class MoveScraper:
    def __init__(self):
        """
        ~~~ Blacklist ~~~
        Charging Moves: Skull Bash, Razor Wind, Sky Attack, Solar Beam, Bide, Counter
        Moves with a recharge turn: Hyper Beam
        Invulnerable Turn Moves: Fly, Dig
        Multi-turn Effect Moves: Bind, Leech Seed
        Moves that hit for many turns: Rage, Thrash, Petal Dance
        No status-conditional moves: Dream Eater
        Not valid since these are 1v1 battles: Self Destruct
        Already manually defined: Struggle
        """
        self.blacklist: set[str] = {"skull-bash", "razor-wind",  "sky-attack", "solar-beam",
                                    "bide", "counter", "hyper-beam", "fly", "dig", "bind",
                                    "leech-seed", "rage", "thrash", "petal-dance", "dream-eater",
                                    "self-destruct", "struggle"}
        self.high_crit_ratio_moves: set[str] = {"crabhammer", "karate-chop", "razor-leaf", "slash"}

    def _scrape_move(self, move_url: str) -> Optional[MoveInfo]:
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

            return MoveInfo(
                api_id=move_data["id"],
                name=move_data["name"],
                type=Type(move_data["type"]["name"].upper()),
                power=move_data["power"],
                total_pp=move_data["pp"],
                damage_class=DamageClass(move_data["damage_class"]["name"].upper()),
                priority=move_data["priority"],
                high_crit_ratio=(move_data["name"] in self.high_crit_ratio_moves),
                healing=(move_data["meta"]["healing"] / 100),
                drain=(move_data["meta"]["drain"] / 100),
                hit_count_info=hit_count_info,
                accuracy=(move_data["accuracy"] / 100 if move_data["accuracy"] else None)
            )
        except ValueError as e:
            raise e

    def scrape(self, top_level_data: dict) -> list[MoveInfo]:
        move_urls = [move["url"] for move in top_level_data["moves"]]
        with ThreadPoolExecutor() as executor:
            results = executor.map(self._scrape_move, move_urls)
            moves = [x for x in results if x]
        return moves
