import unittest

from privacygate.readiness import evaluate_loaded_models


class ReadinessTests(unittest.TestCase):
    def test_one_gemma_model_is_ready(self):
        result = evaluate_loaded_models(["google/gemma-4-e2b-it-q4"])
        self.assertTrue(result.ready)
        self.assertEqual(result.selected_model, "google/gemma-4-e2b-it-q4")

    def test_configured_model_must_be_loaded(self):
        result = evaluate_loaded_models(["google/gemma-4-e2b"], "google/gemma-4-e4b")
        self.assertFalse(result.ready)
        self.assertIn("does not match", result.message)

    def test_multiple_models_require_explicit_choice(self):
        result = evaluate_loaded_models(["google/gemma-4-e2b", "google/gemma-4-e4b"])
        self.assertFalse(result.ready)
        self.assertIn("Multiple", result.message)

    def test_non_gemma_fallback_is_rejected(self):
        result = evaluate_loaded_models(["another/model"])
        self.assertFalse(result.ready)
        self.assertIn("not identified as Gemma", result.message)

    def test_no_loaded_model_is_not_ready(self):
        self.assertFalse(evaluate_loaded_models([]).ready)


if __name__ == "__main__":
    unittest.main()
