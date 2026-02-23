"""Tests for eligibility matching engine."""

import pytest
import pytest_asyncio

from app.models import Scheme
from app.schemas.eligibility import EligibilityCheckRequest
from app.services.eligibility_service import _compute_match, check_eligibility


# ---------------------------------------------------------------------------
# Unit tests for _compute_match (pure logic, no DB)
# ---------------------------------------------------------------------------

class TestComputeMatch:
    """Test the scoring function that matches a user profile to a scheme."""

    def _make_scheme(self, **kwargs) -> Scheme:
        """Create a minimal Scheme object with given eligibility fields."""
        s = Scheme.__new__(Scheme)
        defaults = dict(
            target_gender=None, min_age=None, max_age=None,
            target_social_category=None, target_income_max=None,
            is_disability=None, is_student=None, is_bpl=None,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(s, k, v)
        return s

    def test_gender_match_exact(self):
        scheme = self._make_scheme(target_gender=["Female"])
        profile = EligibilityCheckRequest(gender="Female")
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0
        assert any("Gender" in m for m in matched)

    def test_gender_match_all(self):
        scheme = self._make_scheme(target_gender=["All"])
        profile = EligibilityCheckRequest(gender="Male")
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0
        assert any("open to all" in m for m in matched)

    def test_gender_mismatch(self):
        scheme = self._make_scheme(target_gender=["Female"])
        profile = EligibilityCheckRequest(gender="Male")
        score, matched = _compute_match(scheme, profile)
        assert score == 0.0
        assert len(matched) == 0

    def test_age_within_range(self):
        scheme = self._make_scheme(min_age=18, max_age=35)
        profile = EligibilityCheckRequest(age=25)
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0
        assert any("Age" in m for m in matched)

    def test_age_below_minimum(self):
        scheme = self._make_scheme(min_age=18, max_age=35)
        profile = EligibilityCheckRequest(age=15)
        score, matched = _compute_match(scheme, profile)
        assert score == 0.0

    def test_age_above_maximum(self):
        scheme = self._make_scheme(min_age=18, max_age=35)
        profile = EligibilityCheckRequest(age=40)
        score, matched = _compute_match(scheme, profile)
        assert score == 0.0

    def test_age_at_boundary_min(self):
        scheme = self._make_scheme(min_age=18, max_age=35)
        profile = EligibilityCheckRequest(age=18)
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0

    def test_age_at_boundary_max(self):
        scheme = self._make_scheme(min_age=18, max_age=35)
        profile = EligibilityCheckRequest(age=35)
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0

    def test_social_category_match(self):
        scheme = self._make_scheme(target_social_category=["SC", "ST"])
        profile = EligibilityCheckRequest(social_category="SC")
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0
        assert any("Category" in m for m in matched)

    def test_social_category_all(self):
        scheme = self._make_scheme(target_social_category=["All"])
        profile = EligibilityCheckRequest(social_category="OBC")
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0

    def test_social_category_mismatch(self):
        scheme = self._make_scheme(target_social_category=["SC", "ST"])
        profile = EligibilityCheckRequest(social_category="General")
        score, matched = _compute_match(scheme, profile)
        assert score == 0.0

    def test_income_within_limit(self):
        scheme = self._make_scheme(target_income_max=250000)
        profile = EligibilityCheckRequest(income=200000)
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0
        assert any("Income" in m for m in matched)

    def test_income_exceeds_limit(self):
        scheme = self._make_scheme(target_income_max=250000)
        profile = EligibilityCheckRequest(income=300000)
        score, matched = _compute_match(scheme, profile)
        assert score == 0.0

    def test_disability_match(self):
        scheme = self._make_scheme(is_disability=True)
        profile = EligibilityCheckRequest(is_disability=True)
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0

    def test_disability_mismatch(self):
        scheme = self._make_scheme(is_disability=True)
        profile = EligibilityCheckRequest(is_disability=False)
        score, matched = _compute_match(scheme, profile)
        assert score == 0.0

    def test_student_match(self):
        scheme = self._make_scheme(is_student=True)
        profile = EligibilityCheckRequest(is_student=True)
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0

    def test_bpl_match(self):
        scheme = self._make_scheme(is_bpl=True)
        profile = EligibilityCheckRequest(is_bpl=True)
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0

    def test_no_criteria_returns_baseline(self):
        """Schemes with no structured criteria get a 0.1 'universal' score."""
        scheme = self._make_scheme()
        profile = EligibilityCheckRequest(age=25, gender="Male")
        score, matched = _compute_match(scheme, profile)
        assert score == 0.1
        assert "Open to all" in matched

    def test_multiple_criteria_partial_match(self):
        """Test scoring with multiple criteria where only some match."""
        scheme = self._make_scheme(
            target_gender=["Female"],
            min_age=18,
            max_age=60,
            target_social_category=["SC", "ST"],
        )
        profile = EligibilityCheckRequest(
            gender="Female",
            age=25,
            social_category="General",  # mismatch
        )
        score, matched = _compute_match(scheme, profile)
        # 2 matched (gender, age) out of 3 criteria
        assert score == pytest.approx(2 / 3)

    def test_case_insensitive_gender(self):
        scheme = self._make_scheme(target_gender=["female"])
        profile = EligibilityCheckRequest(gender="Female")
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0

    def test_case_insensitive_social_category(self):
        scheme = self._make_scheme(target_social_category=["sc"])
        profile = EligibilityCheckRequest(social_category="SC")
        score, matched = _compute_match(scheme, profile)
        assert score == 1.0
