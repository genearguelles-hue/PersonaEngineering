from __future__ import annotations

import unittest

from pe_mission_control.resume_assessor import ResumePersonaAssessor
from pe_mission_control.resume_evidence_rubric import ResumeEvidenceRubric


class ResumeEvidenceRubricPhase3BTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rubric = ResumeEvidenceRubric()

    def test_case_management_integration_is_not_inferred_from_generic_integration(
        self,
    ) -> None:
        result = self.rubric.classify(
            {
                "id": "case-integration",
                "text": (
                    "Integrate AI tools with an existing case-management "
                    "system and other firm software."
                ),
                "required": True,
            },
            [
                {
                    "evidence_id": "generic-integration",
                    "type": "experience_bullet",
                    "text": (
                        "Developed enterprise AI workflow integration "
                        "prototypes."
                    ),
                    "employer": "",
                    "role_title": "",
                }
            ],
        )
        self.assertEqual(result.classification, "adjacent")
        self.assertEqual(result.weight, 0.0)
        self.assertIn("case_operations", result.missing_capabilities)

    def test_exact_deployed_case_integration_is_strong(self) -> None:
        result = self.rubric.classify(
            {
                "id": "case-integration",
                "text": (
                    "Integrate AI tools with an existing case-management "
                    "system and other firm software."
                ),
                "required": True,
            },
            [
                {
                    "evidence_id": "exact-integration",
                    "type": "experience_bullet",
                    "text": (
                        "Deployed and integrated AI tools with a case "
                        "management platform."
                    ),
                    "employer": "",
                    "role_title": "",
                }
            ],
        )
        self.assertEqual(result.classification, "strong")
        self.assertEqual(result.weight, 1.0)

    def test_composite_training_requirement_is_partial_without_support_feedback(
        self,
    ) -> None:
        result = self.rubric.classify(
            {
                "id": "training",
                "text": (
                    "Train staff and provide ongoing support and iteration "
                    "based on feedback."
                ),
                "required": True,
            },
            [
                {
                    "evidence_id": "training-only",
                    "type": "experience_bullet",
                    "text": "Delivered test-automation training for staff.",
                    "employer": "",
                    "role_title": "",
                }
            ],
        )
        self.assertEqual(result.classification, "partial")
        self.assertEqual(result.weight, 0.5)
        self.assertIn("support", result.missing_capabilities)
        self.assertIn("feedback_iteration", result.missing_capabilities)

    def test_assessor_weights_partial_and_excludes_adjacent(self) -> None:
        assessment = ResumePersonaAssessor().assess(
            evidence_map=[
                {
                    "requirement_id": "strong",
                    "required": True,
                    "classification": "strong",
                    "supporting_evidence_ids": ["a"],
                },
                {
                    "requirement_id": "partial",
                    "required": True,
                    "classification": "partial",
                    "supporting_evidence_ids": ["b"],
                },
                {
                    "requirement_id": "adjacent",
                    "required": True,
                    "classification": "adjacent",
                    "supporting_evidence_ids": ["c"],
                },
            ],
            rejected_claims=[],
            draft="Evidence-bounded résumé draft.",
            minimum_coverage=0.70,
        )
        self.assertAlmostEqual(assessment.requirement_coverage, 0.5)
        self.assertEqual(assessment.strong_count, 1)
        self.assertEqual(assessment.partial_count, 1)
        self.assertEqual(assessment.adjacent_count, 1)
        self.assertEqual(assessment.verdict, "revise")
        self.assertTrue(
            any(
                "adjacent evidence receives no coverage credit" in finding
                for finding in assessment.findings
            )
        )


if __name__ == "__main__":
    unittest.main()
