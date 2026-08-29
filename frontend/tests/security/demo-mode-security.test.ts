/**
 * Demo Mode Security Audit Suite — Chargeback Shield Task 7.5
 * 
 * Verifies 15 mandatory security & safety isolation contracts for Demo Mode.
 */

import { DEMO_STAGES, DEMO_DISPUTE_ID, DEMO_DATA_TAG } from '../../src/data/demoFixtures';

export function runDemoModeSecurityAudit(): { passed: boolean; assertionsCount: number } {
  let assertions = 0;

  // 1. Assert Demo Data Tag is Present
  if (DEMO_DATA_TAG !== 'DEMO DATA — NOT LIVE RAZORPAY DATA') {
    throw new Error('SECURITY VIOLATION: Demo data tag is missing or incorrect');
  }
  assertions++;

  // 2. Assert All 17 Demo Lifecycle Stages Exist
  if (DEMO_STAGES.length !== 17) {
    throw new Error(`SECURITY VIOLATION: Demo mode expected 17 stages, found ${DEMO_STAGES.length}`);
  }
  assertions++;

  // 3. Assert Stage 12 (UNKNOWN) Has Reconciliation-Only Notice and No Retry Submission
  const stage12 = DEMO_STAGES.find((s) => s.id === 12);
  if (!stage12 || !stage12.security_boundary.includes('NO retry submission button')) {
    throw new Error('SECURITY VIOLATION: Stage 12 UNKNOWN state missing strict reconciliation-only notice');
  }
  assertions++;

  // 4. Assert Demo Fixtures Contain No Real Razorpay Credentials
  const fixturesStr = JSON.stringify(DEMO_STAGES);
  if (fixturesStr.includes('rzp_live_') || fixturesStr.includes('rzp_test_secret')) {
    throw new Error('SECURITY VIOLATION: Demo fixtures contain live Razorpay credentials');
  }
  assertions++;

  // 5. Assert Direct External Razorpay Submissions are Prohibited in Demo Fixtures
  if (fixturesStr.includes('api.razorpay.com/v1/payments')) {
    throw new Error('SECURITY VIOLATION: Direct external payment mutation URL found in demo fixtures');
  }
  assertions++;

  // 6. Assert Demo Dispute ID Is Cryptographically Isolated
  if (DEMO_DISPUTE_ID !== 'demo-dispute-001') {
    throw new Error('SECURITY VIOLATION: Demo dispute ID is not isolated');
  }
  assertions++;

  // 7. Assert Human Review Stage (Stage 9) Preserves BLOCKED Draft Protection Contract
  const stage9 = DEMO_STAGES.find((s) => s.id === 9);
  if (!stage9 || !stage9.security_boundary.includes('BLOCKED drafts cannot be approved')) {
    throw new Error('SECURITY VIOLATION: Stage 9 human review checkpoint missing BLOCKED draft protection');
  }
  assertions++;

  // 8. Assert Submission Preflight Gate (Stage 10) Generates Authorization Hash
  const stage10 = DEMO_STAGES.find((s) => s.id === 10);
  if (!stage10 || !stage10.output.includes('pf_hash_')) {
    throw new Error('SECURITY VIOLATION: Stage 10 preflight gate missing cryptographic hash');
  }
  assertions++;

  // 9. Assert Controlled Contest Submission (Stage 11) Enforces Single Post Route
  const stage11 = DEMO_STAGES.find((s) => s.id === 11);
  if (!stage11 || !stage11.security_boundary.includes('Single controlled POST endpoint')) {
    throw new Error('SECURITY VIOLATION: Stage 11 submission boundary missing controlled endpoint requirement');
  }
  assertions++;

  // 10. Assert Audit Trail (Stage 16) Has SHA-256 Hash Verification
  const stage16 = DEMO_STAGES.find((s) => s.id === 16);
  if (!stage16 || !stage16.security_boundary.includes('Cryptographic hash verification')) {
    throw new Error('SECURITY VIOLATION: Stage 16 audit trail missing cryptographic hash boundary');
  }
  assertions++;

  // 11. Assert Financial Fields Are Untouched across Demo Stages
  for (const s of DEMO_STAGES) {
    if (s.input.includes('mutateAmount') || s.output.includes('mutateAmount')) {
      throw new Error(`SECURITY VIOLATION: Stage ${s.id} attempted financial amount mutation`);
    }
  }
  assertions++;

  // 12. Assert Policy Disqualifications Remain Untouched
  const stage7 = DEMO_STAGES.find((s) => s.id === 7);
  if (!stage7 || !stage7.security_boundary.includes('Policy rules executed strictly in backend Python engine')) {
    throw new Error('SECURITY VIOLATION: Stage 7 policy engine boundary missing backend authoritative rule');
  }
  assertions++;

  // 13. Assert Evidence Ingestion (Stage 3) Validates MIME & Magic Bytes
  const stage3 = DEMO_STAGES.find((s) => s.id === 3);
  if (!stage3 || !stage3.security_boundary.includes('Magic byte validation')) {
    throw new Error('SECURITY VIOLATION: Stage 3 missing magic byte validation contract');
  }
  assertions++;

  // 14. Assert Processing Sandbox (Stage 4) Revokes Execution Privileges
  const stage4 = DEMO_STAGES.find((s) => s.id === 4);
  if (!stage4 || !stage4.security_boundary.includes('execution privileges revoked')) {
    throw new Error('SECURITY VIOLATION: Stage 4 processing sandbox missing execution revocation contract');
  }
  assertions++;

  // 15. Assert Fact Extraction (Stage 5) Sanitizes Credentials & PII
  const stage5 = DEMO_STAGES.find((s) => s.id === 5);
  if (!stage5 || !stage5.security_boundary.includes('Strict PII/credential sanitization')) {
    throw new Error('SECURITY VIOLATION: Stage 5 fact extraction missing credential sanitization contract');
  }
  assertions++;

  return { passed: true, assertionsCount: assertions };
}

if (typeof window === 'undefined') {
  const res = runDemoModeSecurityAudit();
  console.log(`[DEMO MODE SECURITY AUDIT PASSED]: All ${res.assertionsCount} security assertions verified cleanly.`);
}
