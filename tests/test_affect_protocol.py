import unittest

from iris.server import affect_proposal, display_content


class AffectProtocolTest(unittest.TestCase):
    def test_parses_complete_vector_and_hides_protocol(self):
        line = "AFFECT joy:51.5; sadness:49; fear:47; anger:50; trust:54; disgust:50; surprise:52; anticipation:55"
        raw = "I understand.\n" + line
        proposal = affect_proposal(raw)
        self.assertEqual(proposal["trust"], 54.0)
        self.assertEqual(set(proposal), {"joy", "sadness", "fear", "anger", "trust", "disgust", "surprise", "anticipation"})
        self.assertEqual(display_content(raw), "I understand.")

    def test_rejects_partial_and_duplicate_vectors(self):
        with self.assertRaises(ValueError):
            affect_proposal("AFFECT joy:50")
        complete = "joy:50; sadness:50; fear:50; anger:50; trust:50; disgust:50; surprise:50; anticipation:50"
        with self.assertRaises(ValueError):
            affect_proposal(f"AFFECT {complete}\nAFFECT {complete}")


if __name__ == "__main__":
    unittest.main()
