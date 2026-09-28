from __future__ import annotations

import tempfile
import unittest
import shutil
from pathlib import Path

import yaml

from iris.imagination_pack import validate_manifest
from iris.imagination_doctrine import (
    compile_doctrine,
    validate_blueprint,
    validate_world_pressure,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "seeds" / "imagination_packs" / "villain" / "manifest.yaml"


class ImaginationPackSeedTest(unittest.TestCase):
    def test_villain_seed_is_versioned_inert_and_content_addressed(self) -> None:
        result = validate_manifest(MANIFEST, ROOT)
        self.assertEqual(result["id"], "imagination-pack:villain")
        self.assertEqual(result["version"], 5)
        self.assertEqual(result["status"], "seed-only")
        self.assertEqual(result["source_count"], 17)
        self.assertGreater(result["item_count"], 200)
        self.assertEqual(result["resource_count"], 24)
        self.assertEqual(result["lens_count"], 5)
        self.assertEqual(result["future_contract"]["output"], "atomic-world-packet")

    def test_changed_doctrine_is_rejected(self) -> None:
        manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        manifest["doctrine"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.yaml"
            shutil.copyfile(MANIFEST.parent / "classification.yaml", Path(directory) / "classification.yaml")
            path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                validate_manifest(path, ROOT)

    def test_villain_doctrine_compiles_losslessly_into_shared_primitives(self) -> None:
        graph = compile_doctrine(MANIFEST, ROOT)
        primitives = {item["id"]: item for item in graph["primitives"]}
        self.assertGreater(len(primitives), 600)
        self.assertGreater(len(graph["edges"]), 300)
        self.assertIn("primitive:families:corporate-predator", primitives)
        self.assertIn("primitive:macguffins:ancient-apocalypse-engine", primitives)
        self.assertIn("primitive:sidekicks:roles:chief-of-staff", primitives)
        self.assertIn("policy:assembly:moral-texture-family-pressure:gaslighting", primitives)
        self.assertIn("policy:novelty:weights:sidekick-full", primitives)
        macguffin = primitives["primitive:macguffins:ancient-apocalypse-engine"]
        self.assertIn("containment_needs", macguffin["content"])
        self.assertIn("artifact", macguffin["domains"])
        self.assertEqual(macguffin["lanes"], [])
        self.assertEqual(macguffin["classification"]["subject"], "holdings")
        self.assertEqual(macguffin["classification"]["treatment"], "preserve_losslessly")
        self.assertFalse(macguffin["classification"]["selectable"])
        self.assertFalse(any(item["classification"]["subject"] == "unclassified"
                             for item in primitives.values()))
        self.assertTrue(any(edge["relation"] == "compatible_with" for edge in graph["edges"]))
        self.assertTrue(any(edge["relation"] == "tagged_with" for edge in graph["edges"]))

    def test_blueprint_and_world_pressure_contracts_preserve_the_boundary(self) -> None:
        validate_blueprint({
            "id": "blueprint:black-ledger", "status": "draft",
            "ingredients": [{"primitive": "primitive:tag:betrayal", "origin": "user_selected",
                             "locked": True}],
            "tensions": [],
        })
        validate_world_pressure({
            "id": "pressure:black-ledger-custodian", "status": "open",
            "subject": "entity:black-ledger", "kind": "missing_custodian",
            "possible_resolutions": ["assign_existing_character", "create_character"],
        })
        with self.assertRaisesRegex(ValueError, "ingredient origin"):
            validate_blueprint({"id": "blueprint:bad", "status": "draft",
                                "ingredients": [{"primitive": "primitive:x", "origin": "canonical"}]})


if __name__ == "__main__":
    unittest.main()
