import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _normalize_card_title
from app.services.lean_lesson_generator import _polish_card_cosmetics
from app.core.title_sanitizer import plain_language_title


class TitleSanitizerTests(unittest.TestCase):
    def test_strips_unicode_integral_suffix_and_connective(self):
        self.assertEqual(
            plain_language_title(
                "Formula and symbolic setup for ∫_C F·dr",
                fallback="Formula breakdown",
            ),
            "Formula and symbolic setup",
        )

    def test_strips_delimited_and_plain_equations(self):
        self.assertEqual(
            plain_language_title("Newton's second law: \\(F = ma\\)", fallback="Core concept"),
            "Newton's second law",
        )
        self.assertEqual(
            plain_language_title("Slope-intercept form: y = mx + b", fallback="Core concept"),
            "Slope-intercept form",
        )

    def test_equation_only_title_uses_fallback(self):
        self.assertEqual(
            plain_language_title("$$\\int_a^b f(x)\\,dx$$", fallback="Core concept"),
            "Core concept",
        )

    def test_card_normalizer_enforces_plain_language_title(self):
        self.assertEqual(
            _normalize_card_title(
                value="Formula and symbolic setup for ∫_C F·dr",
                blueprint_key="formula_breakdown",
                card_index=1,
            ),
            "Formula and symbolic setup",
        )

    def test_topic_model_enforces_titles_on_every_construction_path(self):
        import app.db.base  # noqa: F401 - register mapped models before direct construction
        from app.models.topic import Topic

        topic = Topic(
            study_path_id="path",
            title="Line-integral setup: ∫_C F·dr",
            unit_title="Parameterization using \\(r(t) = (x(t), y(t))\\)",
            order_index=0,
        )
        self.assertEqual(topic.title, "Line-integral setup")
        self.assertEqual(topic.unit_title, "Parameterization")

    def test_final_card_sweep_catches_late_equation_titles(self):
        class Topic:
            course_type = "math_formula_method"

        cards = [{
            "title": "Formula for ∫_C F·dr",
            "card_type": "formula",
            "blueprint_key": "formula_breakdown",
            "points": ["The equation is shown below."],
        }]
        _polish_card_cosmetics(cards, Topic(), grounded_edge=False)
        self.assertEqual(cards[0]["title"], "Formula")


if __name__ == "__main__":
    unittest.main()
