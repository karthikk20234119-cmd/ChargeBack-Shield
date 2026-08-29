# Chargeback Shield — 3–5 Minute Hackathon Demo Script

## Timeline & Presentation Breakdown

---

### **0:00 – 0:30 | The Problem**
> *"Merchants lose billions annually to payment chargebacks because dispute management is fragmented, manual, and slow. Compounding evidence from invoices, delivery tracking, and gateway logs manually takes days—often missing gateway response deadlines."*

---

### **0:30 – 1:00 | The Chargeback Shield Solution**
> *"Chargeback Shield is a production-grade, AI-assisted Dispute Defense Platform. It automates evidence processing, fact extraction, reason-code matching, and contest response drafting—while enforcing strict human-in-the-loop control and single-boundary submission security."*

---

### **1:00 – 1:30 | Evidence Ingestion & Fact Extraction (`/demo`)**
> *"When a dispute arrives, Chargeback Shield ingests evidence documents—invoices, proof of delivery, customer communications. It validates magic bytes and extracts structured facts with confidence scores without executing unsafe code or hallucinating facts."*

---

### **1:30 – 2:00 | Deterministic Matching & Policy Engine**
> *"Our rule-based matching engine links extracted facts directly to Razorpay reason codes (e.g., '13.1 Services Not Rendered'). The Policy Engine evaluates win probability, recommending whether to contest, accept, or request more information."*

---

### **2:00 – 2:30 | Explainable Contest Draft**
> *"Chargeback Shield generates a structured, human-readable contest draft containing factual arguments and direct evidence citations. Every claim made in the draft links directly back to a verified document."*

---

### **2:30 – 3:00 | Human Review Workspace (`/review`)**
> *"No contest response is ever submitted automatically. The Human Review Workspace presents the draft for merchant admin approval. We separate operational status from human review status, protected by atomic Compare-And-Swap locks to prevent double approvals."*

---

### **3:00 – 3:30 | Preflight Authorization & Single Mutation Boundary**
> *"Before submission, a Preflight check verifies that the draft is approved, policy is valid, and input fingerprints match. Submissions execute exclusively through `ContestSubmissionClient.submit_contest`—our single, audited mutation boundary."*

---

### **3:30 – 4:00 | UNKNOWN State Recovery & Operations (`/operations`)**
> *"If a network timeout occurs, submission state becomes `UNKNOWN`. Chargeback Shield NEVER blindly retries submissions. Operators use read-only status reconciliation to safely verify state. The Operations Command Center tracks SLA deadlines and alert queues."*

---

### **4:00 – 4:30 | Executive Analytics & Compliance Audit (`/analytics`, `/audit`)**
> *"Executive Analytics provides realtime funnel metrics and win-rate analysis. The Compliance Audit log records an append-only timeline with a deterministic SHA-256 export hash, ensuring complete auditability for financial auditors."*

---

### **4:30 – 5:00 | Security & Business Value**
> *"With 698/698 passing tests, zero credential leakage, zero financial identity mutations, multi-stage Docker containerization, and instant disaster recovery, Chargeback Shield transforms chargeback defense from a manual cost sink into a secure, automated revenue recovery engine."*
