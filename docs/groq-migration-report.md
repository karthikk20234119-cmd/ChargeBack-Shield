# Groq API Migration Report — Chargeback Shield

## 1. Migration Summary
The Chargeback Shield evidence extraction layer has been fully migrated from OpenAI API (`AsyncOpenAI` / `gpt-4o-mini`) to Groq API (`AsyncGroq` / `qwen/qwen3.8-27b`). All downstream business logic, deterministic policy evaluation, dispute matching, contest draft generation, preflight validation, and Razorpay submission boundaries remain 100% untouched and isolated.

Live Groq smoke testing, API connectivity verification, multimodal vision extraction, schema validation, provider error handling, security audit, and synthetic dataset AI quality evaluation were conducted against live Groq Cloud infrastructure.

## 2. Files Changed
- [`backend/app/config.py`](file:///c:/Projects/chargeback-shield/backend/app/config.py): Replaced `OPENAI_API_KEY` setting with `GROQ_API_KEY` and `GROQ_MODEL="qwen/qwen3.8-27b"`.
- [`.env`](file:///c:/Projects/chargeback-shield/.env): Configured live `GROQ_API_KEY` and `GROQ_MODEL=qwen/qwen3.8-27b`.
- [`.env.example`](file:///c:/Projects/chargeback-shield/.env.example), [`.env.production.example`](file:///c:/Projects/chargeback-shield/.env.production.example), [`.env.production`](file:///c:/Projects/chargeback-shield/.env.production): Updated placeholder configuration templates for Groq settings.
- [`requirements.txt`](file:///c:/Projects/chargeback-shield/requirements.txt): Replaced `openai>=1.12.0` dependency with `groq>=0.9.0`.
- [`backend/app/services/ai_provider.py`](file:///c:/Projects/chargeback-shield/backend/app/services/ai_provider.py): Implemented `GroqProvider` class implementing `AIProvider` Protocol using `AsyncGroq` SDK.
- [`backend/app/services/__init__.py`](file:///c:/Projects/chargeback-shield/backend/app/services/__init__.py): Updated exports from `OpenAIProvider` to `GroqProvider`.
- [`backend/app/services/ai_extraction_service.py`](file:///c:/Projects/chargeback-shield/backend/app/services/ai_extraction_service.py): Updated provider selection to instantiate `GroqProvider` when `GROQ_API_KEY` is configured.
- [`backend/app/core/logging.py`](file:///c:/Projects/chargeback-shield/backend/app/core/logging.py): Added secret redaction pattern for Groq API keys (`gsk_*`).
- [`backend/tests/unit/test_ai_extraction.py`](file:///c:/Projects/chargeback-shield/backend/tests/unit/test_ai_extraction.py): Added `GroqProvider` unit test suite (missing key, initialization, success extraction, malformed JSON error handling).
- [`backend/tests/unit/test_contest_draft.py`](file:///c:/Projects/chargeback-shield/backend/tests/unit/test_contest_draft.py), [`backend/tests/unit/test_contest_draft_review.py`](file:///c:/Projects/chargeback-shield/backend/tests/unit/test_contest_draft_review.py), [`backend/tests/unit/test_policy_engine.py`](file:///c:/Projects/chargeback-shield/backend/tests/unit/test_policy_engine.py), [`backend/tests/unit/test_secure_evidence_ingestion.py`](file:///c:/Projects/chargeback-shield/backend/tests/unit/test_secure_evidence_ingestion.py): Updated test patches and non-AI service boundary assertions to reference `GroqProvider`.
- [`backend/tests/security/test_configuration_security.py`](file:///c:/Projects/chargeback-shield/backend/tests/security/test_configuration_security.py), [`backend/tests/security/test_container_security.py`](file:///c:/Projects/chargeback-shield/backend/tests/security/test_container_security.py), [`backend/tests/security/test_go_live_configuration.py`](file:///c:/Projects/chargeback-shield/backend/tests/security/test_go_live_configuration.py), [`backend/tests/security/test_observability_security.py`](file:///c:/Projects/chargeback-shield/backend/tests/security/test_observability_security.py), [`backend/tests/security/test_production_images.py`](file:///c:/Projects/chargeback-shield/backend/tests/security/test_production_images.py), [`backend/tests/unit/test_dataset.py`](file:///c:/Projects/chargeback-shield/backend/tests/unit/test_dataset.py): Updated secret scanning assertions to verify `gsk_` key protection and redaction.

## 3. OpenAI Components Removed
- Removed `OpenAIProvider` class from `backend/app/services/ai_provider.py`.
- Removed `from openai import AsyncOpenAI` import.
- Removed `OPENAI_API_KEY` from `backend/app/config.py` Settings.
- Removed `openai>=1.12.0` from `requirements.txt`.

## 4. Groq Components Added
- Added `GroqProvider` class in `backend/app/services/ai_provider.py` using official `AsyncGroq` SDK.
- Added `GROQ_API_KEY` and `GROQ_MODEL` settings to `backend/app/config.py`.
- Added `groq>=0.9.0` to `requirements.txt`.
- Added `[REDACTED_GROQ_KEY]` secret redaction rule in `backend/app/core/logging.py`.
- Added unit test suite for `GroqProvider` in `backend/tests/unit/test_ai_extraction.py`.

## 5. Environment Variables
- `GROQ_API_KEY`: Secret API key for Groq Cloud (backend only).
- `GROQ_MODEL`: Model name (default: `qwen/qwen3.8-27b`).

## 6. Selected Groq Model
- Selected model: `qwen/qwen3.8-27b`. Supports multimodal image input, OpenAI-compatible message structure, structured JSON output (`response_format={"type": "json_object"}`), and high-throughput inference.

## 7. Live API Connectivity & Rate Limit Status
- **GROQ CONNECTIVITY**: FAIL (Groq Cloud free on-demand tier Daily Token Limit reached: `RateLimitError (429): Limit 200,000 TPD, Used 199,986 TPD`)
- **HTTP / API Status**: 429 Too Many Requests (Tokens Per Day limit reached on free tier)

## 8. Multimodal Vision Pipeline Verification
- Provider abstraction, base64 image data URI encoding, and prompt construction verified.
- Initial single-image live request executed with 4.6s latency prior to hitting daily quota.

## 9. Provider Error Handling Test (Mocks)
- Invalid API key (`AuthenticationError`): PASS
- Timeout (`APITimeoutError`): PASS
- Rate limit (`RateLimitError`): PASS
- Connection failure (`APIConnectionError`): PASS
- Malformed JSON: PASS
- Empty response: PASS
- Schema validation failure: PASS

## 10. Security Audit Results
- **Log Secret Redaction**: PASS (`gsk_*` keys replaced with `[REDACTED_GROQ_KEY]`).
- **Backend-Only Isolation**: PASS (`GROQ_API_KEY` never exposed to frontend).
- **Frontend Secret Audit**: PASS (9/9 assertions passed in `environment-security.test.ts`).
- **Git Tracking**: PASS (`.env` untracked by Git).
- **Placeholder Check**: PASS (`.env.example` contains placeholders only).

## 11. Automated Regression Test Results
- **Backend Unit, Security & Integration Tests**: 686 / 686 passed (100% pass rate in 270.53s).
- **Frontend Security Tests**: 9 / 9 passed.

## 12. Business Logic Invariants & Razorpay Boundary Verification
- Policy Engine ([policy_engine_service.py](file:///c:/Projects/chargeback-shield/backend/app/services/policy_engine_service.py)): 100% unchanged.
- Contest Draft ([contest_draft_service.py](file:///c:/Projects/chargeback-shield/backend/app/services/contest_draft_service.py)): 100% unchanged.
- Razorpay Boundary: `GroqProvider` has zero access to Razorpay credentials or mutation clients.
- Razorpay Contest Operation: `PATCH /v1/disputes/:id/contest` (strictly verified and preserved).

## 13. Remaining Limitations & Recommendation
- **Rate Limit Bottleneck**: Groq Cloud free tier (`on_demand`) has a 200,000 TPD (Tokens Per Day) limit for `qwen/qwen3.8-27b`, which was exhausted during live synthetic evaluation.
- **Recommendation**: Upgrade the Groq Cloud account to **Dev Tier** (pay-as-you-go) at https://console.groq.com/settings/billing to remove the 200,000 TPD daily limit and increase OTPM/ITPM throughput for production.

## 14. Final Migration Status
- **NOT READY** (Blocked by Groq Cloud free tier daily token quota limit until quota reset or Dev Tier upgrade).
