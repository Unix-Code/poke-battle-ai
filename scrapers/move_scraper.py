import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests

from models import DamageClass, HitInfo, Type, MoveInfo, StatChangeEffect, StatType

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

    def _scrape_move(self, move_url: str) -> Optional[MoveInfo]:
        move_data = requests.get(move_url).json()
        if move_data["name"] in self.blacklist:
            return None

        # TODO: Support non-stat-changing status moves (ie burn, sleep, frozen, etc)?
        damage_class = DamageClass(move_data["damage_class"]["name"].upper())
        if damage_class is DamageClass.STATUS and len(move_data["stat_changes"]) == 0:
            logger.info(f"IGNORED STATUS MOVE (NOT STAT-CHANGING): {move_data['name']} | {move_data['id']}")
            return None

        if move_data["past_values"]:
            if len(move_data["past_values"]) > 1:
                logger.warning(f"MULTIPLE PAST VALUES DETECTED: {move_data['name']} | {move_data['id']}")

            # Use past values instead
            move_data.update({k: v for k, v in move_data["past_values"][0].items()
                              if k in ["accuracy", "power", "type", "pp"] and v is not None})

        if damage_class is not DamageClass.STATUS and move_data["power"] is None:
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

            stat_change_effect = None
            if len(move_data["stat_changes"]) > 0:
                if len(move_data["stat_changes"]) > 1:
                    logger.info(f"MULTIPLE STAT CHANGES DETECTED: {move_data['name']} | {move_data['id']}")
                # Use the last value here since Growth has 2 but only the last one is for Gen 1
                stat_change = move_data["stat_changes"].pop()

                # This truncates "special-attack" and "special-defense" to "special" (for Gen 1)
                raw_stat_type = stat_change["stat"]["name"].split("-")[0]

                # For some reason stat_chance is either 0 or 100 for sure-fire moves
                # (it should be guaranteed if move hits in most cases)
                stat_chance = 1 if move_data["meta"]["stat_chance"] == 0 else move_data["meta"]["stat_chance"] / 100
                stat_change_effect = StatChangeEffect(self_targeting=(move_data["target"]["name"] == "user"),
                                                      change=stat_change["change"],
                                                      stat_type=StatType(raw_stat_type),
                                                      chance=stat_chance)

            return MoveInfo(
                api_id=move_data["id"],
                name=move_data["name"],
                type=Type(move_data["type"]["name"].upper()),
                power=move_data["power"],
                total_pp=move_data["pp"],
                damage_class=damage_class,
                priority=move_data["priority"],
                high_crit_ratio=(move_data["name"] in self.high_crit_ratio_moves),
                healing=(move_data["meta"]["healing"] / 100),
                drain=(move_data["meta"]["drain"] / 100),
                hit_info=hit_count_info,
                accuracy=(move_data["accuracy"] / 100 if move_data["accuracy"] else None),
                stat_change_effect=stat_change_effect
            )
        except ValueError as e:
            raise e

    def scrape(self, top_level_data: dict) -> list[MoveInfo]:
        move_urls = [move["url"] for move in top_level_data["moves"]]
        with ThreadPoolExecutor() as executor:
            results = executor.map(self._scrape_move, move_urls)
            moves = [x for x in results if x]
        return moves
