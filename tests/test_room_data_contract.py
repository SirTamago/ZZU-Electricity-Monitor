import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOM_DIR = ROOT / "page" / "data" / "rooms"
EXPECTED_AREA_IDS = ["99", "101", "102", "103", "104", "105"]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def option_values(html: str):
    values = []
    marker = '<option value="'
    for part in html.split(marker)[1:]:
        values.append(part.split('"', 1)[0])
    return values


class RoomDataContractTests(unittest.TestCase):
    def test_area_options_have_matching_room_shards(self):
        html = read_text(ROOT / "page" / "index.html")
        area_ids = [value for value in option_values(html) if value in EXPECTED_AREA_IDS]

        self.assertEqual(area_ids, EXPECTED_AREA_IDS)
        self.assertEqual(set(path.stem for path in ROOM_DIR.glob("*.json")), set(EXPECTED_AREA_IDS))

    def test_room_shards_match_frontend_contract(self):
        total_rooms = 0
        for path in sorted(ROOM_DIR.glob("*.json")):
            with self.subTest(path=path.name):
                data = json.loads(read_text(path))
                self.assertIsInstance(data.get("name"), str)
                self.assertTrue(data["name"])
                buildings = data.get("buildings")
                self.assertIsInstance(buildings, dict)
                self.assertTrue(buildings)

                for building_name, building in buildings.items():
                    self.assertIsInstance(building_name, str)
                    self.assertTrue(building_name)
                    units = building.get("units")
                    self.assertIsInstance(units, dict)
                    self.assertTrue(units)

                    for unit_name, unit in units.items():
                        self.assertIsInstance(unit_name, str)
                        self.assertTrue(unit_name)
                        rooms = unit.get("rooms")
                        ids = unit.get("ids")
                        self.assertIsInstance(rooms, list)
                        self.assertIsInstance(ids, list)
                        self.assertEqual(
                            len(rooms),
                            len(ids),
                            f"{path.name} {building_name} {unit_name}",
                        )
                        self.assertTrue(all(isinstance(room, str) and room for room in rooms))
                        self.assertTrue(all(isinstance(room_id, str) and room_id for room_id in ids))
                        total_rooms += len(rooms)

        self.assertGreater(total_rooms, 0)

    def test_room_query_fetch_path_matches_shard_directory(self):
        script = read_text(ROOT / "page" / "main.js")

        self.assertIn("fetch(`./data/rooms/${areaId}.json`)", script)


if __name__ == "__main__":
    unittest.main()
