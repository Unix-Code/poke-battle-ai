import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests

from models import DamageClass, HitInfo, Type, MoveInfo, Ailment

logger = logging.getLogger(__name__)


class MoveScraper:
    def __init__(self):
        """
        ~~~ Blacklist ~~~
        Counter Moves: Bide, Counter
        Multi-turn Effect Moves: Bind, Leech Seed
        Moves that hit for many turns: Rage, Thrash, Petal Dance
        No status-conditional moves: Dream Eater
        Already manually defined: Struggle
        """
        self.self_destructing_moves: set[str] = {"self-destruct", "explosion"}
        self.moves_with_recharge: set[str] = {"hyper-beam"}
        self.moves_that_charge: set[str] = {"skull-bash", "razor-wind",  "sky-attack", "solar-beam", "fly", "dig"}
        self.moves_with_invulnerable_phase: set[str] = {"fly", "dig"}
        self.blacklist: set[str] = {"bide", "counter", "bind", "leech-seed", "rage", "thrash",
                                    "petal-dance", "dream-eater", "struggle"}
        self.high_crit_ratio_moves: set[str] = {"crabhammer", "karate-chop", "razor-leaf", "slash"}
        # Ignored ailments
        self.ailment_blacklist: set[str] = {"freeze", "none"}

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
            min_hits = move_data["meta"]["min_hits"] or 1
            max_hits = move_data["meta"]["max_hits"] or 1
            hit_count_info = HitInfo(min_hits=min_hits, max_hits=max_hits,
                                     has_invulnerable_phase=(move_data["name"] in self.moves_with_invulnerable_phase),
                                     requires_charge=(move_data["name"] in self.moves_that_charge),
                                     has_recharge=(move_data["name"] in self.moves_with_recharge),
                                     self_destructing=(move_data["name"] in self.self_destructing_moves))
            ailment = move_data["meta"]["ailment"]["name"]
            ailment_chance = move_data["meta"]["ailment_chance"] / 100
            if ailment not in self.ailment_blacklist and ailment_chance == 0:
                ailment_chance = 1

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
                hit_info=hit_count_info,
                accuracy=(move_data["accuracy"] / 100 if move_data["accuracy"] else None),
                ailment=Ailment(ailment.upper()) if ailment not in self.ailment_blacklist else None,
                ailment_chance=ailment_chance,
            )
        except ValueError as e:
            raise e

    def scrape(self, top_level_data: dict) -> list[MoveInfo]:
        move_urls = [move["url"] for move in top_level_data["moves"]]
        with ThreadPoolExecutor() as executor:
            results = executor.map(self._scrape_move, move_urls)
            moves = [x for x in results if x]
        return moves
