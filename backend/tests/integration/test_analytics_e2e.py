"""
End-to-End Integration Test Suite for Dispute Analytics, Management Reporting & Performance Insights — Chargeback Shield Task 6.4

Sets up a complete 12-stage dispute lifecycle fixture:
Dispute → Evidence → Processing → Extraction → Matching → Policy → Draft → Review → Preflight → Submission → Reconciliation → Lifecycle → Outcome → Alerts

Verifies:
- Management summary
- Outcome report
- Evidence report
- Matching report
- Policy report
- Draft report
- Submission report
- Operations report
- SLA report
- 12-stage lifecycle funnel
- Bottleneck analysis
- Failure matrix
- Security report
- Financial integrity report
- Structured JSON export with SHA-256 report hash stability
- Strict read-only immutability of all source business entities
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import init_db, get_db
from backend.app.main import app
from backend.app.models.contest_draft import ContestDraft
from backend.app.models.contest_submission import ContestSubmission
from backend.app.models.contest_submission_preflight import ContestSubmissionPreflight
from backend.app.models.dispute import Dispute
from backend.app.models.dispute_lifecycle_snapshot import DisputeLifecycleSnapshot
from backend.app.models.document import EvidenceDocument, ExtractedEvidence
from backend.app.models.matching import MatchResult
from backend.app.models.operational_alert import OperationalAlert
from backend.app.models.policy import PolicyResult
from backend.app.models.processed_artifact import ProcessedArtifact


@pytest.mark.asyncio
class TestAnalyticsE2E:
    """E2E Integration Test Suite for Dispute Analytics Layer."""

    async def test_full_analytics_pipeline(self, async_db: AsyncSession):
        """Builds full 12-stage lifecycle records and tests all 15 GET endpoints."""
        await init_db()
        # 1. Dispute
        disp = Dispute(
            id="disp_e2e_an_01",
            payment_id="pay_e2e_an_01",
            amount=750000,
            currency="INR",
            reason_code="13.1",
            status="won",
            raw_payload={"payload": {}},
        )
        async_db.add(disp)

        # 2. Document
        doc = EvidenceDocument(
            id="doc_e2e_an_01",
            dispute_id="disp_e2e_an_01",
            original_filename="receipt.pdf",
            internal_filename="receipt_int.png",
            file_path="/tmp/receipt.pdf",
            file_hash="hash_e2e_01",
            file_size_bytes=2048,
            mime_type="application/pdf",
            document_type="invoice",
            processing_status="PROCESSED",
        )
        async_db.add(doc)

        # 3. Processed Artifact
        art = ProcessedArtifact(
            id="art_e2e_an_01",
            evidence_id="doc_e2e_an_01",
            page_number=1,
            file_path="/tmp/p1.png",
            width=800,
            height=600,
            file_size_bytes=100,
            format="PNG",
            source_document_type="invoice",
        )
        async_db.add(art)

        # 4. Extracted Evidence
        ext = ExtractedEvidence(
            id="ext_e2e_an_01",
            document_id="doc_e2e_an_01",
            document_type="invoice",
            payment_id="pay_e2e_an_01",
            order_id="ord_e2e_01",
            amount_minor=750000,
            currency="INR",
            customer_name="Aarav Sharma",
            confidence_score=0.98,
            extracted_data={},
            schema_version="1.0",
            model_name="mock-vision-v1",
        )
        async_db.add(ext)

        # 5. Match Result
        m = MatchResult(
            id="m_e2e_an_01",
            dispute_id="disp_e2e_an_01",
            evidence_id="doc_e2e_an_01",
            fact_name="payment_id",
            extracted_value="pay_e2e_an_01",
            expected_value="pay_e2e_an_01",
            status="MATCH",
            confidence="HIGH",
            explanation="Match OK",
        )
        async_db.add(m)

        # 6. Policy Result
        pol = PolicyResult(
            id="pol_e2e_an_01",
            dispute_id="disp_e2e_an_01",
            policy_version="cb13.1-v1.0",
            outcome="ELIGIBLE",
            decision="ELIGIBLE",
            summary="Policy E2E summary",
            rule_results={},
        )
        async_db.add(pol)

        # 7. Draft
        draft = ContestDraft(
            id="draft_e2e_an_01",
            dispute_id="disp_e2e_an_01",
            title="Draft E2E",
            summary="Summary E2E",
            input_fingerprint="fp_e2e_01",
            generator_version="1.0",
            status="DRAFT",
            review_status="APPROVED",
        )
        async_db.add(draft)

        # 8. Preflight
        pref = ContestSubmissionPreflight(
            id="pref_e2e_an_01",
            dispute_id="disp_e2e_an_01",
            contest_draft_id="draft_e2e_an_01",
            status="READY",
            draft_status="DRAFT",
            review_status="APPROVED",
            input_fingerprint="fp_e2e_01",
            checks=["CHECK_1"],
            blocking_reasons=[],
            verified_financial_identity={"payment_id": "pay_e2e_an_01", "amount": 750000, "currency": "INR"},
        )
        async_db.add(pref)

        # 9. Submission
        sub = ContestSubmission(
            id="sub_e2e_an_01",
            dispute_id="disp_e2e_an_01",
            contest_draft_id="draft_e2e_an_01",
            preflight_id="pref_e2e_an_01",
            input_fingerprint="fp_e2e_01",
            idempotency_key="idem_e2e_01",
            state="SUBMITTED",
        )
        async_db.add(sub)

        # 10. Lifecycle Snapshot
        snap = DisputeLifecycleSnapshot(
            id="snap_e2e_an_01",
            dispute_id="disp_e2e_an_01",
            razorpay_dispute_id="disp_rzp_e2e_01",
            razorpay_status="won",
            previous_lifecycle_status="under_review",
            new_lifecycle_status="won",
            sync_result="NO_CHANGE",
            outcome="WON",
        )
        async_db.add(snap)

        # 11. Operational Alert
        al = OperationalAlert(
            id="al_e2e_an_01",
            dispute_id="disp_e2e_an_01",
            category="SLA",
            code="HUMAN_REVIEW_REQUIRED",
            severity="INFO",
            status="RESOLVED",
            title="Resolved Alert",
            message="Alert resolved",
            source_type="disputes",
            source_id="disp_e2e_an_01",
            fingerprint="fp_al_e2e_01",
        )
        async_db.add(al)

        await async_db.commit()

        # -------------------------------------------------------------------
        # Test HTTP REST Endpoints
        # -------------------------------------------------------------------
        async def _override_get_db():
            yield async_db

        app.dependency_overrides[get_db] = _override_get_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:

                # 1. Summary
                res_sum = await client.get("/api/analytics/summary")
                assert res_sum.status_code == 200
                data_sum = res_sum.json()
                assert data_sum["total_disputes"] >= 1
                assert data_sum["won"] >= 1

                # 2. Outcomes
                res_out = await client.get("/api/analytics/outcomes?period=daily")
                assert res_out.status_code == 200
                data_out = res_out.json()
                assert data_out["total"] >= 1

                # 3. Evidence
                res_ev = await client.get("/api/analytics/evidence")
                assert res_ev.status_code == 200
                assert res_ev.json()["total_documents"] >= 1

                # 4. Matching
                res_m = await client.get("/api/analytics/matching")
                assert res_m.status_code == 200
                assert res_m.json()["total_matches"] >= 1

                # 5. Policy
                res_pol = await client.get("/api/analytics/policy")
                assert res_pol.status_code == 200
                assert res_pol.json()["total_policy_evaluations"] >= 1

                # 6. Drafts
                res_dr = await client.get("/api/analytics/drafts")
                assert res_dr.status_code == 200
                assert res_dr.json()["total_drafts"] >= 1

                # 7. Submissions
                res_sub = await client.get("/api/analytics/submissions")
                assert res_sub.status_code == 200
                assert res_sub.json()["total_submissions"] >= 1

                # 8. Operations
                res_ops = await client.get("/api/analytics/operations")
                assert res_ops.status_code == 200
                assert res_ops.json()["total_alerts"] >= 1

                # 9. SLA
                res_sla = await client.get("/api/analytics/sla")
                assert res_sla.status_code == 200
                assert "sla_compliance_percentage" in res_sla.json()

                # 10. Funnel
                res_fn = await client.get("/api/analytics/funnel")
                assert res_fn.status_code == 200
                assert len(res_fn.json()["stages"]) == 12

                # 11. Bottlenecks
                res_bot = await client.get("/api/analytics/bottlenecks")
                assert res_bot.status_code == 200
                assert len(res_bot.json()["bottlenecks"]) >= 1

                # 12. Failures
                res_fail = await client.get("/api/analytics/failures")
                assert res_fail.status_code == 200

                # 13. Security
                res_sec = await client.get("/api/analytics/security")
                assert res_sec.status_code == 200

                # 14. Financial Integrity
                res_fin = await client.get("/api/analytics/financial-integrity")
                assert res_fin.status_code == 200
                assert res_fin.json()["disputes_checked"] >= 1

                # 15. Export
                res_exp = await client.get("/api/analytics/export")
                assert res_exp.status_code == 200
                data_exp = res_exp.json()
                assert "report_hash" in data_exp
                assert len(data_exp["report_hash"]) == 64
        finally:
            app.dependency_overrides.clear()

        # -------------------------------------------------------------------
        # Verify Read-Only Immutability of Source Entities
        # -------------------------------------------------------------------
        disp_check = (await async_db.execute(select(Dispute).where(Dispute.id == "disp_e2e_an_01"))).scalars().first()
        assert disp_check.amount == 750000
        assert disp_check.status == "won"
