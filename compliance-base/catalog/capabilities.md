# Capability Catalog

Derived from the compliance constraint catalog on 2026-07-23 via the `compliance-capabilities` ultracode workflow (extract → merge → stack → verify).
Per-framework capability lists (cross-framework overlap intentionally kept). Each capability groups the constraints it satisfies and maps to recommended greenfield-2026 stack components.

| Framework | Capabilities | Mandatory covered | Uncovered |
|-----------|--------------|-------------------|-----------|
| GDPR / DSGVO | 25 | 109/109 | 0 |
| SOC 2 | 25 | 111/111 | 0 |
| ISO/IEC 27001:2022 | 18 | 59/59 | 0 |

---

## GDPR / DSGVO — 25 capabilities

### Privacy notice & transparency delivery
*Governance & Privacy Ops* · satisfies 8 constraints

Layered privacy notices and just-in-time transparency UI that surface controller/DPO identity, purposes, legal basis, recipients, transfers, retention, and all data-subject rights in plain language for both directly and indirectly collected data, and that flag the right to object explicitly and separately.

**Stack (greenfield 2026):** Transcend (Consent & Preference Management + Privacy Center), iubenda, Klaro!, Didomi

<sub>GDPR-ART12-01, GDPR-ART13-01, GDPR-ART13-02, GDPR-ART13-03, GDPR-ART14-01, GDPR-ART14-02, GDPR-ART14-03, GDPR-ART21-05</sub>

### Data-subject request intake & access fulfillment
*Governance & Privacy Ops* · satisfies 7 constraints

A DSAR workflow engine that intakes, tracks, and fulfills rights requests within the one-month SLA (with logged extension/decline reasons and complaint-rights messaging), provides free abuse-controlled handling, confirms whether data is processed, and assembles access exports with required metadata and a machine-readable copy that does not expose third parties.

**Stack (greenfield 2026):** Transcend (Privacy Requests / DSR Automation), OneTrust Data Subject Request (DSR) Automation, Temporal, Osano (Subject Rights Management)

<sub>GDPR-ART11-02, GDPR-ART12-02, GDPR-ART12-03, GDPR-ART12-04, GDPR-ART15-01, GDPR-ART15-02, GDPR-ART15-03</sub>

### Requester identity verification
*IAM* · satisfies 1 constraints

An identity-proofing step in the request pipeline that requires additional identity evidence before disclosing or acting on personal data when there is reasonable doubt about the requester, protecting against impersonated rights requests.

**Stack (greenfield 2026):** Keycloak, Persona, Stripe Identity, Ory Kratos

<sub>GDPR-ART12-05</sub>

### Rectification, erasure & restriction processing
*Data Protection* · satisfies 6 constraints

Data-lifecycle operations that let subjects correct inaccurate data, complete incomplete data with supplementary statements, erase data on qualifying grounds while honoring legal-hold/retention exemptions, and place a reversible processing-restriction state with pre-lift notification.

**Stack (greenfield 2026):** Fides (Ethyca), Temporal, Transcend, OpenFGA

<sub>GDPR-ART16-01, GDPR-ART16-02, GDPR-ART17-01, GDPR-ART17-03, GDPR-ART18-01, GDPR-ART18-02</sub>

### Downstream recipient tracking & change propagation
*Data Protection* · satisfies 3 constraints

A recipient/disclosure ledger that records where personal data was shared and, on rectification/erasure/restriction, propagates the change to each recipient (and to other controllers of publicly-disclosed data) unless impossible/disproportionate, and can disclose the recipient list to the subject on request.

**Stack (greenfield 2026):** Fides (Ethyca), PostgreSQL (append-only disclosure ledger, e.g. via temporal_tables/system-versioning), Temporal, Transcend

<sub>GDPR-ART17-02, GDPR-ART19-01, GDPR-ART19-02</sub>

### Data portability & structured export
*Data Protection* · satisfies 3 constraints

An export service that outputs subject-provided, automated, consent/contract-based data in a structured, commonly used, machine-readable format, supports direct controller-to-controller transmission where technically feasible, and scopes the export to eligible data without affecting others' rights.

**Stack (greenfield 2026):** Data Transfer Initiative Portability API (formerly Data Transfer Project), Temporal (open-source; Temporal Cloud managed), S3-compatible object storage with presigned expiring URLs (AWS S3 managed / MinIO open-source), Transcend Data Mapping & DSR automation (or OneTrust)

<sub>GDPR-ART20-01, GDPR-ART20-02, GDPR-ART20-03</sub>

### Objection & opt-out management
*Governance & Privacy Ops* · satisfies 6 constraints

A preference/opt-out subsystem that lets subjects object to legitimate-interest/public-task processing and profiling (with a compelling-grounds balancing evaluation), enforces an absolute stop for direct-marketing objections, supports objection to research/statistical processing, and accepts automated machine-readable objection signals.

**Stack (greenfield 2026):** Ethyca Fides, Transcend Consent & Privacy Requests, Ketch, Global Privacy Control (GPC)

<sub>GDPR-ART21-01, GDPR-ART21-02, GDPR-ART21-03, GDPR-ART21-04, GDPR-ART21-06, GDPR-ART21-07</sub>

### Automated decision-making & profiling safeguards
*Governance & Privacy Ops* · satisfies 4 constraints

Controls governing solely-automated significant decisions: gating them to permitted grounds (contract, law, or explicit consent), blocking special-category data unless conditions are met, and providing human-intervention, view-expression, and contest mechanisms.

**Stack (greenfield 2026):** Open Policy Agent (OPA), OneTrust (Consent & Preference Management + Privacy Rights Automation), Camunda 8, Fiddler AI

<sub>GDPR-ART22-01, GDPR-ART22-02, GDPR-ART22-03, GDPR-ART22-04</sub>

### Lawful-basis & purpose governance
*Governance & Privacy Ops* · satisfies 9 constraints

A processing registry that binds every activity to an identified lawful basis before it begins, records legitimate-interests balancing, enforces fair processing, purpose limitation, and a compatibility assessment for further use, gates criminal-conviction data to official-authority conditions, and ensures any restriction of data-subject rights rests on a lawful, necessary, proportionate measure with required safeguards.

**Stack (greenfield 2026):** OneTrust Privacy & Data Governance, OpenMetadata, Open Policy Agent (OPA), Transcend

<sub>GDPR-ART10-01, GDPR-ART23-01, GDPR-ART23-02, GDPR-ART5-01, GDPR-ART5-02, GDPR-ART5-04, GDPR-ART6-01, GDPR-ART6-02, GDPR-ART6-03</sub>

### Privacy by design & default
*Change & SDLC* · satisfies 3 constraints

Build-time and runtime measures that embed pseudonymization and data minimization into system design, avoid acquiring or retaining identifying data solely for compliance when identification is not required, and enforce privacy-by-default settings so only data necessary for each purpose is collected, processed, retained, or made accessible without explicit action.

**Stack (greenfield 2026):** Microsoft Presidio, Skyflow Data Privacy Vault, OpenFGA, Tonic.ai

<sub>GDPR-ART11-01, GDPR-ART25-01, GDPR-ART25-02</sub>

### Accountability, liability & governance evidence
*Governance & Privacy Ops* · satisfies 10 constraints

Risk-proportionate organizational and technical measures, backed by internal data-protection policies, that demonstrate and evidence compliance with all processing principles, preserve controller/processor-role and lawful-instruction documentation to bound (joint-and-several) liability, and maintain mitigating-factor evidence for fine assessment and national penalty regimes.

**Stack (greenfield 2026):** OneTrust Privacy & Data Governance, Fides (Ethyca), Vanta, Eramba

<sub>GDPR-ART24-01, GDPR-ART24-02, GDPR-ART5-09, GDPR-ART82-01, GDPR-ART82-02, GDPR-ART82-03, GDPR-ART83-01, GDPR-ART83-02, GDPR-ART83-03, GDPR-ART84-01</sub>

### Encryption & security of processing
*Data Protection* · satisfies 4 constraints

Risk-appropriate technical and organisational security controls — encryption at rest and in transit, pseudonymization, and measures ensuring confidentiality, integrity, availability, and resilience — protecting personal data against unauthorised or unlawful processing and accidental loss, destruction, or damage.

**Stack (greenfield 2026):** Cloud KMS (AWS KMS / Google Cloud KMS / Azure Key Vault), OpenBao (or HashiCorp Vault), cert-manager + Let's Encrypt, Linkerd (or Istio) service mesh

<sub>GDPR-ART32-01, GDPR-ART32-02, GDPR-ART32-03, GDPR-ART5-08</sub>

### Instruction-bound access control & least privilege
*IAM* · satisfies 2 constraints

Authorization enforcement ensuring personnel and processors can only access and process personal data on documented instructions, backed by least-privilege access controls.

**Stack (greenfield 2026):** OpenFGA, Open Policy Agent (OPA), Keycloak, Amazon Verified Permissions (Cedar)

<sub>GDPR-ART29-01, GDPR-ART32-06</sub>

### Backup, restore & availability resilience
*Business Continuity* · satisfies 1 constraints

Backup and disaster-recovery capability that restores availability of and access to personal data in a timely manner after a physical or technical incident.

**Stack (greenfield 2026):** AWS Backup, Velero, pgBackRest, S3 (with versioning + Cross-Region Replication + Object Lock)

<sub>GDPR-ART32-04</sub>

### Security testing & effectiveness assessment
*Incident & Vulnerability* · satisfies 1 constraints

A recurring process to test, assess, and evaluate the effectiveness of security measures protecting personal data (e.g. pen tests, control reviews, vulnerability scans).

**Stack (greenfield 2026):** Trivy, OWASP ZAP, HackerOne (PTaaS / bug bounty), Vanta

<sub>GDPR-ART32-05</sub>

### Breach detection, register & notification
*Incident & Vulnerability* · satisfies 8 constraints

Incident response pipeline that detects personal-data breaches, maintains an internal breach register, notifies the supervisory authority within 72 hours with required content and delay justification, propagates processor-to-controller alerts, and notifies affected subjects in plain language for high-risk breaches subject to defined exemptions.

**Stack (greenfield 2026):** Wazuh, TheHive 5 (StrangeBee), OneTrust Incident & Breach Response, n8n

<sub>GDPR-ART33-01, GDPR-ART33-02, GDPR-ART33-03, GDPR-ART33-04, GDPR-ART33-05, GDPR-ART34-01, GDPR-ART34-02, GDPR-ART34-03</sub>

### DPIA & prior consultation workflow
*Governance & Privacy Ops* · satisfies 8 constraints

Data protection impact assessment process triggered for high-risk/enumerated processing, capturing required DPIA content, DPO consultation, optional data-subject input, periodic review on risk change, and prior consultation with the supervisory authority for unmitigated residual risk.

**Stack (greenfield 2026):** OneTrust Assessment Automation (PIA/DPIA Automation), CNIL PIA tool, Camunda 8 (BPMN/DMN workflow engine), Vanta

<sub>GDPR-ART35-01, GDPR-ART35-02, GDPR-ART35-03, GDPR-ART35-04, GDPR-ART35-05, GDPR-ART35-06, GDPR-ART36-01, GDPR-ART36-02</sub>

### DPO designation & governance
*Governance & Privacy Ops* · satisfies 7 constraints

Designation of a qualified, independent Data Protection Officer with published contact details, adequate resources and access, protection from dismissal/conflicts, and assignment of statutory risk-based advisory and monitoring tasks.

**Stack (greenfield 2026):** OneTrust Privacy & Data Governance Cloud, Ethyca Fides, Osano, TrustArc Privacy Management Platform

<sub>GDPR-ART37-01, GDPR-ART37-02, GDPR-ART37-03, GDPR-ART38-01, GDPR-ART38-02, GDPR-ART39-01, GDPR-ART39-02</sub>

### Records of processing & authority cooperation
*Governance & Privacy Ops* · satisfies 4 constraints

Maintained records of processing activities (as controller and processor), designation of an EU representative for non-EU entities, and processes to cooperate with the supervisory authority on request.

**Stack (greenfield 2026):** Ethyca Fides, OneTrust Data Mapping & RoPA (Privacy Automation), Prighter (GDPR/UK Representative-as-a-Service), Transcend

<sub>GDPR-ART27-01, GDPR-ART30-01, GDPR-ART30-02, GDPR-ART31-01</sub>

### Processor & joint-controller contracting
*Vendor & Third-Party* · satisfies 4 constraints

Vendor governance that engages only processors giving sufficient guarantees, binds them with mandatory-clause written contracts, controls sub-processor authorization and flow-down liability, and formalizes joint-controller responsibility arrangements.

**Stack (greenfield 2026):** OneTrust Third-Party Risk Management (with DPA/Vendorpedia), Vanta Vendor Risk Management, Ironclad CLM, Documenso

<sub>GDPR-ART26-01, GDPR-ART28-01, GDPR-ART28-02, GDPR-ART28-03</sub>

### Cross-border transfer safeguards
*Governance & Privacy Ops* · satisfies 12 constraints

Controls governing personal-data transfers outside the EEA: enforcing Chapter V bases, relying on and monitoring adequacy decisions, applying appropriate safeguards (unmodified SCCs, BCRs, codes/certifications) with supplementary measures, rejecting foreign disclosure demands lacking an international legal basis, gating derogations to the specific situation with subject risk-warnings and last-resort documentation, and recording every derogation-based transfer.

**Stack (greenfield 2026):** OneTrust (Data Mapping / Cross-Border Transfers module + Assessment Automation), Fides by Ethyca, AWS European Sovereign Cloud, HashiCorp Vault (with BYOK / external key management)

<sub>GDPR-ART44-01, GDPR-ART45-01, GDPR-ART45-02, GDPR-ART46-01, GDPR-ART46-02, GDPR-ART46-03, GDPR-ART47-01, GDPR-ART48-01, GDPR-ART49-01, GDPR-ART49-02, GDPR-ART49-03, GDPR-ART49-04</sub>

### Consent capture & lifecycle management
*Governance & Privacy Ops* · satisfies 5 constraints

A consent subsystem that records demonstrable proof of consent, presents consent requests distinctly in plain language separate from other terms, ensures consent is freely given (not a condition of service), lets subjects withdraw as easily as they gave it, and enforces the explicit-consent standard for special-category data.

**Stack (greenfield 2026):** Didomi (Consent & Preference Management Platform), OneTrust Consent & Preferences, c15t, Usercentrics (incl. Cookiebot)

<sub>GDPR-ART7-01, GDPR-ART7-02, GDPR-ART7-03, GDPR-ART7-04, GDPR-ART9-02</sub>

### Special-category & children's data protection
*Data Protection* · satisfies 3 constraints

Handling controls that block processing of special-category data unless an Article 9(2) exception applies, verify the child's age against the applicable threshold for online services offered to children, and make reasonable technology-based efforts to verify parental authorisation.

**Stack (greenfield 2026):** Yoti (age assurance / facial age estimation), SuperAwesome Kids Web Services (KWS), OneTrust Consent & Preference Management, Google Cloud Sensitive Data Protection (formerly Cloud DLP)

<sub>GDPR-ART8-01, GDPR-ART8-02, GDPR-ART9-01</sub>

### Data minimisation, accuracy & retention lifecycle
*Data Protection* · satisfies 3 constraints

Data-lifecycle machinery limiting collection to what is necessary, keeping data accurate and rectified/erased without delay, and enforcing defined retention periods with automated deletion or anonymisation of identifiable data when they expire.

**Stack (greenfield 2026):** Ethyca Fides, Transcend, pg_partman + pg_cron, ARX Data Anonymization Tool

<sub>GDPR-ART5-05, GDPR-ART5-06, GDPR-ART5-07</sub>

### Data-subject transparency, complaints & remedies
*Governance & Privacy Ops* · satisfies 5 constraints

Subject-facing intake and information flows: clear plain-language notices at or before collection, informing subjects of and not obstructing their rights to lodge a supervisory-authority complaint and pursue an effective judicial remedy, accepting requests from mandated not-for-profit representatives, and a process to receive, track, and comply with binding supervisory-authority orders.

**Stack (greenfield 2026):** Osano (Consent & CMP), Ethyca Fides, Transcend (DSR Automation), Jira Service Management

<sub>GDPR-ART5-03, GDPR-ART77-01, GDPR-ART79-01, GDPR-ART80-01, GDPR-ART83-04</sub>

## SOC 2 — 25 capabilities

### Capacity planning & elastic scaling
*Infrastructure & Network* · satisfies 3 constraints

Continuously monitor compute, storage, and network utilization, forecast demand against available capacity, and provide manual or auto-scaling so the system meets demand before resources are exhausted and availability commitments are breached.

**Stack (greenfield 2026):** Prometheus, KEDA (Kubernetes Event-Driven Autoscaling), Karpenter, Grafana

<sub>SOC2-A1-01, SOC2-A1-02, SOC2-A1-03</sub>

### Environmental safeguards & facility monitoring
*Infrastructure & Network* · satisfies 2 constraints

Protect hosting facilities against environmental hazards (fire, flood, power loss, temperature, humidity) and monitor environmental conditions with alerting so responders can act before an anomaly causes an outage.

**Stack (greenfield 2026):** Cloud provider compliance attestations (AWS Artifact / Google Cloud Compliance Reports / Azure Service Trust Portal), Prometheus + Alertmanager with SNMP Exporter, PagerDuty (or Opsgenie), Sunbird DCIM (managed) or openDCIM (open-source)

<sub>SOC2-A1-04, SOC2-A1-05</sub>

### Business continuity & disaster recovery
*Business Continuity* · satisfies 9 constraints

Maintain encrypted isolated backups and redundant failover infrastructure with defined RTO/RPO, document and periodically test BC/DR plans and backup restoration, and identify disruption risks with proportionate mitigation including risk-transfer such as insurance.

**Stack (greenfield 2026):** restic, AWS Backup with S3 Object Lock (cross-region/cross-account), Velero, Terraform

<sub>SOC2-A1-06, SOC2-A1-07, SOC2-A1-08, SOC2-A1-09, SOC2-A1-10, SOC2-A1-11, SOC2-CC9-01, SOC2-CC9-02, SOC2-CC9-03</sub>

### Data classification & confidentiality protection
*Data Protection* · satisfies 4 constraints

Establish criteria to identify and classify confidential information at creation/receipt, maintain an inventory of confidential assets and locations, label the data, and apply access controls and encryption throughout its retention period.

**Stack (greenfield 2026):** Microsoft Purview Information Protection (sensitivity labels + DLP), AWS Macie (or Google Cloud Sensitive Data Protection / Cloud DLP), HashiCorp Vault, Open Policy Agent (OPA) with OpenFGA

<sub>SOC2-C1-01, SOC2-C1-02, SOC2-C1-03, SOC2-C1-04</sub>

### Data retention & secure disposal
*Data Protection* · satisfies 9 constraints

Define retention periods aligned to commitments and legal obligations, then irreversibly delete or anonymize data at end-of-life (cryptographic erasure, secure wipe, physical destruction) across all copies including backups, retaining evidence of disposal.

**Stack (greenfield 2026):** HashiCorp Vault, AWS S3 Object Lock + Lifecycle policies, OpenMetadata, ShredOS / nwipe

<sub>SOC2-C1-05, SOC2-C1-06, SOC2-C1-07, SOC2-C1-08, SOC2-C1-09, SOC2-C1-10, SOC2-C1-12, SOC2-P4-02, SOC2-P4-03</sub>

### Control environment: governance, ethics & personnel
*Governance & Privacy Ops* · satisfies 13 constraints

Maintain a code of conduct with ethics remediation, an independent competent board overseeing controls, defined organizational structure and authorities with segregation of duties, plus role-based competence requirements, training, succession, and individual accountability for control responsibilities.

**Stack (greenfield 2026):** NAVEX One (Ethics & Compliance suite), Vanta (or Drata) GRC platform, Rippling (or Workday) HRIS, SailPoint Identity Security (or open-source Keycloak for RBAC)

<sub>SOC2-CC1-01, SOC2-CC1-02, SOC2-CC1-03, SOC2-CC1-04, SOC2-CC1-05, SOC2-CC1-06, SOC2-CC1-07, SOC2-CC1-08, SOC2-CC1-09, SOC2-CC1-10, SOC2-CC1-11, SOC2-CC1-12, SOC2-CC1-13</sub>

### Control information & communications
*Governance & Privacy Ops* · satisfies 8 constraints

Identify and capture quality information needed for internal control from internal and external sources, and communicate control objectives, policies, and responsibilities internally (including a confidential reporting channel), to the board, and to external users.

**Stack (greenfield 2026):** Vanta (or Drata), GlobaLeaks, Confluence (or Notion), Diligent Boards

<sub>SOC2-CC2-01, SOC2-CC2-02, SOC2-CC2-03, SOC2-CC2-04, SOC2-CC2-05, SOC2-CC2-06, SOC2-CC2-07, SOC2-CC2-08</sub>

### Identity & access management
*IAM* · satisfies 9 constraints

Logical access layer that assigns unique identifiers, manages credential issuance/rotation/revocation, enforces MFA on privileged/remote/external paths, runs authorized provisioning and prompt deprovisioning, applies least privilege and segregation of duties, and performs recurring access and privileged-access recertification.

**Stack (greenfield 2026):** Microsoft Entra ID + Entra ID Governance, Okta Workforce Identity Cloud, SailPoint Identity Security Cloud, Keycloak

<sub>SOC2-CC5-05, SOC2-CC5-08, SOC2-CC6-01, SOC2-CC6-02, SOC2-CC6-03, SOC2-CC6-05, SOC2-CC6-06, SOC2-CC6-07, SOC2-CC6-08</sub>

### Encryption & cryptographic key management
*Data Protection* · satisfies 2 constraints

Protect sensitive and personal data with encryption at rest and in transit, restrict how and where such data may be transmitted, and securely manage cryptographic keys across their full lifecycle (generation, storage, rotation, destruction).

**Stack (greenfield 2026):** Cloud provider KMS (AWS KMS / Google Cloud KMS / Azure Key Vault), HashiCorp Vault (or OpenBao, its OSS/Linux Foundation fork), cert-manager + Let's Encrypt, Google Tink

<sub>SOC2-CC6-04, SOC2-CC6-12</sub>

### Control monitoring, evaluation & deficiency remediation
*Logging & Monitoring* · satisfies 10 constraints

Run ongoing monitoring and periodic independent evaluations against a documented control baseline, document and retain results, then assess and rank identified deficiencies, communicate them, track corrective actions to completion, and escalate significant deficiencies to senior management/board.

**Stack (greenfield 2026):** Vanta, Prowler, Grafana + Prometheus/Loki (Grafana Labs LGTM stack), Jira Service Management

<sub>SOC2-CC4-01, SOC2-CC4-02, SOC2-CC4-03, SOC2-CC4-04, SOC2-CC4-05, SOC2-CC4-07, SOC2-CC4-08, SOC2-CC4-09, SOC2-CC4-10, SOC2-CC4-11</sub>

### External communication & incident reporting channels
*Incident & Vulnerability* · satisfies 3 constraints

Provide channels for external parties to report security incidents, vulnerabilities, and complaints, notify external users of changes affecting security commitments, and select communication methods, formats, and timing appropriate to audience and urgency.

**Stack (greenfield 2026):** HackerOne, security.txt (RFC 9116), Atlassian Statuspage, Zammad

<sub>SOC2-CC2-10, SOC2-CC2-11, SOC2-CC2-12</sub>

### Risk assessment & fraud-risk governance
*Governance & Privacy Ops* · satisfies 11 constraints

Specify objectives and risk tolerances, identify and analyze risks to objectives from internal and external sources, determine documented risk responses, explicitly assess fraud potential including management override, and re-analyze risk when significant environmental, business, leadership, or technology changes occur.

**Stack (greenfield 2026):** LogicGate Risk Cloud, Diligent HighBond (Diligent One), Eramba, SimpleRisk

<sub>SOC2-CC3-01, SOC2-CC3-02, SOC2-CC3-03, SOC2-CC3-04, SOC2-CC3-05, SOC2-CC3-06, SOC2-CC3-07, SOC2-CC3-08, SOC2-CC3-09, SOC2-CC3-10, SOC2-CC3-11</sub>

### Control framework design, policy deployment & accountability
*Governance & Privacy Ops* · satisfies 8 constraints

Select and develop a risk-aligned mix of manual/automated and preventive/detective control activities, deploy them through documented policies and procedures with assigned accountability, perform them timely with corrective action, and periodically reassess them via competent personnel.

**Stack (greenfield 2026):** Vanta, Drata, Eramba, NIST OSCAL + IBM trestle

<sub>SOC2-CC5-01, SOC2-CC5-02, SOC2-CC5-03, SOC2-CC5-04, SOC2-CC5-10, SOC2-CC5-11, SOC2-CC5-12, SOC2-CC5-13</sub>

### Vendor & third-party risk management
*Vendor & Third-Party* · satisfies 13 constraints

Maintain a vendor/subprocessor inventory, assess risk at onboarding and ongoing, impose security/confidentiality/availability and retention/disposal obligations contractually, monitor subservice-organization controls, remediate deficiencies, and manage secure termination including data return/destruction and access revocation.

**Stack (greenfield 2026):** Vanta (Vendor Risk Management module), SecurityScorecard, OneTrust Third-Party Risk Management, Eramba (Community Edition)

<sub>SOC2-C1-11, SOC2-CC2-09, SOC2-CC3-12, SOC2-CC4-06, SOC2-CC9-04, SOC2-CC9-05, SOC2-CC9-06, SOC2-CC9-07, SOC2-CC9-08, SOC2-CC9-09, SOC2-CC9-10, SOC2-CC9-11, SOC2-P6-01</sub>

### Physical access control & secure media disposal
*Data Protection* · satisfies 2 constraints

Restrict and periodically review physical access to facilities, data centers, and hardware, and securely erase or destroy data on media and assets before disposal or reuse so residual sensitive data is unrecoverable.

**Stack (greenfield 2026):** Cloud provider (AWS / Azure / GCP) inherited data-center controls, Verkada or Kisi cloud access control, Kandji / Jamf / Microsoft Intune (MDM), Vanta or Drata (GRC automation)

<sub>SOC2-CC6-09, SOC2-CC6-10</sub>

### Infrastructure, network boundary & endpoint protection
*Infrastructure & Network* · satisfies 3 constraints

General controls over technology infrastructure (networks, servers, cloud) supporting reliable processing, boundary defenses (firewalls, segmentation, IDS/IPS) protecting the perimeter, and controls to prevent, detect, and remediate unauthorized or malicious software.

**Stack (greenfield 2026):** Cloudflare (WAF + DDoS + Zero Trust/Access), Cilium + Hubble (eBPF), CrowdStrike Falcon, Falco

<sub>SOC2-CC5-07, SOC2-CC6-11, SOC2-CC6-13</sub>

### Vulnerability management & remediation
*Incident & Vulnerability* · satisfies 2 constraints

Scheduled scanning of infrastructure and software for known vulnerabilities and configuration drift, with tracked, risk-prioritized remediation to resolution within defined SLAs.

**Stack (greenfield 2026):** Trivy, Wiz, DefectDojo, Snyk

<sub>SOC2-CC7-01, SOC2-CC7-10</sub>

### System monitoring, alerting & audit log retention
*Logging & Monitoring* · satisfies 3 constraints

Continuously monitor system components for anomalies with detection tooling and defined alerting thresholds that generate timely actionable alerts, and retain integrity-protected security logs supporting detection and post-hoc investigation.

**Stack (greenfield 2026):** Prometheus + Alertmanager, Grafana Loki + Grafana, Wazuh, AWS S3 with Object Lock (WORM)

<sub>SOC2-CC7-02, SOC2-CC7-03, SOC2-CC7-11</sub>

### Incident response & recovery
*Incident & Vulnerability* · satisfies 7 constraints

End-to-end incident lifecycle covering triage and severity evaluation, a documented and periodically tested IR plan, containment/eradication/mitigation, breach and stakeholder communication, recovery of affected systems, and post-incident root-cause review with corrective actions.

**Stack (greenfield 2026):** PagerDuty, incident.io, Cachet

<sub>SOC2-CC7-04, SOC2-CC7-05, SOC2-CC7-06, SOC2-CC7-07, SOC2-CC7-08, SOC2-CC7-09, SOC2-CC7-12</sub>

### Change management & secure SDLC
*Change & SDLC* · satisfies 15 constraints

Formal change process governing authorization, design/impact assessment, testing, independent approval, and implementation, with segregation of duties, version control, separated dev/test/prod environments, baseline configuration and security review, emergency-change and rollback paths, plus general controls over software acquisition, development, and maintenance and their technology dependencies.

**Stack (greenfield 2026):** GitHub (branch protection + CODEOWNERS + required reviews), GitHub Actions with Environments + required reviewers, OpenTofu (Terraform-compatible IaC), Argo CD (GitOps)

<sub>SOC2-CC5-06, SOC2-CC5-09, SOC2-CC8-01, SOC2-CC8-02, SOC2-CC8-03, SOC2-CC8-04, SOC2-CC8-05, SOC2-CC8-06, SOC2-CC8-07, SOC2-CC8-08, SOC2-CC8-09, SOC2-CC8-10, SOC2-CC8-11, SOC2-CC8-12, SOC2-CC8-13</sub>

### Privacy notice, consent & lawful collection
*Governance & Privacy Ops* · satisfies 7 constraints

Publish a privacy notice describing collection, use, retention, disclosure, and disposal of personal information at or before collection, and operate a consent ledger and collection controls that capture affirmative/explicit consent, verify source authority, and keep collection and use within notified purposes.

**Stack (greenfield 2026):** Ethyca Fides, OneTrust Consent & Preference Management, Ketch (Progressive Consent / Data Permissioning), Klaro!

<sub>SOC2-P1-01, SOC2-P1-02, SOC2-P2-01, SOC2-P2-02, SOC2-P3-01, SOC2-P3-02, SOC2-P4-01</sub>

### Data-subject rights & complaint handling
*Governance & Privacy Ops* · satisfies 3 constraints

Authenticated self-service and back-office workflows that let data subjects access, correct, amend, or delete their personal information and propagate changes to third parties, plus an intake-and-resolution process for privacy inquiries, complaints, and disputes with corrective-action tracking.

**Stack (greenfield 2026):** Ethyca Fides (with Lethe DSR engine), Transcend, OneTrust Privacy & Data Governance (DSR Automation + Privacy Incident/Complaint Management), OpenGDPR / self-hosted case management (e.g. Zammad or Camunda) fronting the DSR engine

<sub>SOC2-P5-01, SOC2-P5-02, SOC2-P8-01</sub>

### Privacy breach detection & notification
*Incident & Vulnerability* · satisfies 1 constraints

Process and tooling to identify, track, and report unauthorized use or disclosure of personal information, notifying affected data subjects and regulators within required timeframes.

**Stack (greenfield 2026):** Wazuh, TheHive (StrangeBee), OneTrust Incident & Breach Response, Microsoft Purview (DSPM / data classification)

<sub>SOC2-P6-02</sub>

### Personal data quality management
*Data Protection* · satisfies 1 constraints

Mechanisms that keep stored personal information accurate, complete, and relevant to the purposes for which it is used.

**Stack (greenfield 2026):** Great Expectations, Soda Core (SodaCL), dbt (tests + snapshots), Monte Carlo

<sub>SOC2-P7-01</sub>

### Processing integrity: validation, pipeline & output verification
*Change & SDLC* · satisfies 12 constraints

Documented processing specifications with intake controls validating inputs and authorizing sources, exactly-once complete/accurate/timely pipeline execution with dead-letter and reconciliation, and pre-release output verification, authorized delivery, and durable protected storage of inputs and outputs.

**Stack (greenfield 2026):** Temporal, Great Expectations (or Soda Core), Apache Kafka (with Schema Registry + DLQ), Amazon S3 with Object Lock (WORM)

<sub>SOC2-PI1-01, SOC2-PI1-02, SOC2-PI1-03, SOC2-PI1-04, SOC2-PI1-05, SOC2-PI1-06, SOC2-PI1-07, SOC2-PI1-08, SOC2-PI1-09, SOC2-PI1-10, SOC2-PI1-11, SOC2-PI1-12</sub>

## ISO/IEC 27001:2022 — 18 capabilities

### RBAC, Least Privilege & Identity Lifecycle
*IAM* · satisfies 7 constraints

Central identity provider with unique per-principal identities, a documented access-control policy, role-based least-privilege authorization, secure credential/secret handling, a joiner-mover-leaver provisioning flow with periodic recertification, elevated controls for privileged/break-glass accounts, and automatic access revocation on role change or termination.

**Stack (greenfield 2026):** Microsoft Entra ID + Entra ID Governance (or Okta + Okta Identity Governance), Keycloak, HashiCorp Vault (self-hosted or HCP Vault managed), Teleport

<sub>ISO-A5-07, ISO-A5-08, ISO-A5-09, ISO-A5-10, ISO-A5-11, ISO-A5-12, ISO-A6-10</sub>

### Data Classification, Asset Inventory & Secure Data Lifecycle
*Data Protection* · satisfies 8 constraints

An owned asset/information inventory with a sensitivity classification and labelling scheme, acceptable-use and handling rules, encrypted and controlled transfer channels, asset return on offboarding, and verified data sanitization or secure destruction before equipment reuse, disposal, or off-site maintenance.

**Stack (greenfield 2026):** Snipe-IT, Microsoft Purview Information Protection, OpenMetadata, Blancco Drive Eraser

<sub>ISO-A5-01, ISO-A5-02, ISO-A5-03, ISO-A5-04, ISO-A5-05, ISO-A5-06, ISO-A7-07, ISO-A7-08</sub>

### Cryptography: Encryption in Transit, At Rest & Key Management
*Data Protection* · satisfies 5 constraints

A documented cryptography policy enforcing strong current algorithms and adequate key lengths, TLS protection for all sensitive/personal data in transit (including service-to-service), encryption at rest for disks, databases and backups, and full-lifecycle management of keys, certificates and secrets (generation, storage, rotation, revocation, destruction) with tightly restricted access.

**Stack (greenfield 2026):** HashiCorp Vault (or OpenBao), Cloud KMS / HSM (AWS KMS, GCP Cloud KMS, or Azure Key Vault Managed HSM), cert-manager + Let's Encrypt/ACME, Linkerd (or Istio) service mesh

<sub>ISO-A8-06, ISO-A8-07, ISO-A8-08, ISO-A8-09, ISO-A8-10</sub>

### Network Segmentation & Multi-Tenant Isolation
*Infrastructure & Network* · satisfies 4 constraints

Secured and managed networks and devices, agreed security levels for in-house or outsourced network services, and traffic segregated into zones with logical per-tenant isolation in shared environments to limit lateral movement and contain compromise.

**Stack (greenfield 2026):** Cilium (with Hubble), Istio Ambient Mesh, Cloud VPC segmentation (AWS VPC / GCP VPC with subnets, security groups, and Network Firewall), Tailscale

<sub>ISO-A8-01, ISO-A8-02, ISO-A8-03, ISO-A8-04</sub>

### Secure Remote Access & Egress Filtering
*Infrastructure & Network* · satisfies 2 constraints

Remote and administrative access occurs only over authenticated, encrypted channels (VPN or equivalent) rather than exposed plaintext services, and outbound web access from managed systems is filtered to reduce exposure to malicious or unauthorized sites.

**Stack (greenfield 2026):** Tailscale, Teleport, Cloudflare Zero Trust (Gateway / Secure Web Gateway), Pomerium

<sub>ISO-A8-05, ISO-A8-11</sub>

### Network Activity Monitoring & Anomaly Detection
*Logging & Monitoring* · satisfies 1 constraints

Network activity is continuously monitored and logged so anomalous or unauthorized traffic and security events can be detected, alerted on, and investigated.

**Stack (greenfield 2026):** Suricata, Zeek, AWS GuardDuty, Elastic Security (SIEM)

<sub>ISO-A8-12</sub>

### Physical & Environmental Facility Security
*Infrastructure & Network* · satisfies 6 constraints

Physical safeguards for equipment and workspaces: clear-desk/clear-screen enforcement, secure equipment siting and screen-privacy positioning, protection against environmental threats, resilient supporting utilities, secured and segregated power/data cabling, and controlled authorized equipment maintenance.

**Stack (greenfield 2026):** AWS Artifact / Google Cloud Compliance Reports / Azure Service Trust Portal (cloud provider physical-security inheritance), Microsoft Intune (or Kandji / Jamf) MDM, NetBox, Verkada (or Envoy for visitor management + Kisi for access control)

<sub>ISO-A7-01, ISO-A7-02, ISO-A7-03, ISO-A7-04, ISO-A7-05, ISO-A7-06</sub>

### Endpoint & Off-Premises Asset Protection
*Infrastructure & Network* · satisfies 3 constraints

Devices and assets used, transported, or stored off-premises are protected against the higher risks of operating outside controlled facilities; off-site removal of equipment, information, or software requires prior authorization and tracking; and users safeguard unattended equipment via session termination, screen locks, and log-off.

**Stack (greenfield 2026):** Microsoft Intune, Jamf Pro, Fleet (osquery), Snipe-IT

<sub>ISO-A7-09, ISO-A7-10, ISO-A7-11</sub>

### Security Incident Detection, Response & Forensics
*Incident & Vulnerability* · satisfies 6 constraints

An incident-management program with defined roles and runbooks, a staff event-reporting channel, event triage/classification, documented containment-eradication-recovery-communication workflows, post-incident learning feeding control improvements, and legally-admissible evidence collection with chain-of-custody preservation.

**Stack (greenfield 2026):** Wazuh, TheHive (with Cortex), incident.io, Velociraptor

<sub>ISO-A5-24, ISO-A5-25, ISO-A5-26, ISO-A5-27, ISO-A5-28, ISO-A6-08</sub>

### Vulnerability Remediation in the Delivery Pipeline
*Incident & Vulnerability* · satisfies 1 constraints

Security vulnerabilities discovered during design, coding, testing, or acceptance are identified and remediated before systems are promoted to production.

**Stack (greenfield 2026):** Trivy (Aqua Security), GitHub Advanced Security (CodeQL + Dependabot), Snyk, OWASP Dependency-Track

<sub>ISO-A8-35</sub>

### Secure Development Lifecycle & Secure Coding
*Change & SDLC* · satisfies 5 constraints

Documented secure-development rules spanning the full lifecycle: security requirements specified for built or acquired apps, secure architecture and engineering principles applied, secure coding standards and tooling used, and security testing verifying requirements before release.

**Stack (greenfield 2026):** OWASP ASVS 5.0 (Application Security Verification Standard), Semgrep, GitHub Advanced Security (CodeQL + secret scanning + Dependabot), OWASP ZAP

<sub>ISO-A8-25, ISO-A8-26, ISO-A8-27, ISO-A8-28, ISO-A8-29</sub>

### Change & Release Management for Production
*Change & SDLC* · satisfies 2 constraints

Changes to systems and information-processing facilities follow formal change management (assessment, approval, testing, rollback), and installation/updating of software on operational systems is governed so only approved, authorized software reaches production.

**Stack (greenfield 2026):** GitHub (Enterprise) — PRs + required reviewers + Environment protection rules, Argo CD, Argo Rollouts, Kyverno + Sigstore Cosign

<sub>ISO-A8-13, ISO-A8-32</sub>

### Environment Separation & Test Data Protection
*Change & SDLC* · satisfies 3 constraints

Development, test, and production environments are separated with controlled promotion; production/sensitive data is not used in test unless masked, anonymized, or otherwise safeguarded and authorized; and audit access to operational systems is planned and controlled to minimize production impact.

**Stack (greenfield 2026):** Argo CD, OpenTofu (with per-environment workspaces/state), Neosync, Teleport

<sub>ISO-A8-31, ISO-A8-33, ISO-A8-34</sub>

### Supplier, ICT Supply-Chain & Cloud Security Management
*Vendor & Third-Party* · satisfies 5 constraints

A vendor risk-management process with due diligence before and during engagement, security requirements embedded in supplier agreements and flowed down through the ICT/software-component supply chain, continuous monitoring and change management of supplier services, and cloud-service governance covering acquisition, shared-responsibility boundaries, and secure exit.

**Stack (greenfield 2026):** OneTrust Third-Party Risk Management, Bitsight (or SecurityScorecard), OWASP Dependency-Track, Wiz (or open-source Prowler)

<sub>ISO-A5-19, ISO-A5-20, ISO-A5-21, ISO-A5-22, ISO-A5-23</sub>

### Outsourced Development Oversight
*Vendor & Third-Party* · satisfies 1 constraints

Third-party and outsourced development activity is directed, monitored, and reviewed so the organization's security requirements are met throughout the engagement.

**Stack (greenfield 2026):** GitHub Enterprise (CODEOWNERS + branch protection + required reviews + audit log), Vanta, Semgrep, Sigstore / cosign (with SLSA provenance)

<sub>ISO-A8-30</sub>

### PII/Privacy Controls & Legal-Regulatory Register
*Governance & Privacy Ops* · satisfies 3 constraints

PII-aware data handling (privacy-by-design safeguards, PII discovery/tagging, consent and retention enforcement), a maintained register of applicable legal, statutory, regulatory and contractual obligations mapped to controls, and intellectual-property/software-licensing compliance tracking.

**Stack (greenfield 2026):** Microsoft Presidio, Transcend, Vanta, OSS Review Toolkit (ORT)

<sub>ISO-A5-31, ISO-A5-32, ISO-A5-34</sub>

### Security Governance, HR Security & Operating Procedures
*Governance & Privacy Ops* · satisfies 9 constraints

Documented operating procedures for information-processing facilities plus the people-side program: pre-employment screening, security responsibilities in employment terms, recurring awareness training, a graduated disciplinary process, signed confidentiality/NDA agreements, remote-working controls, and duties that survive termination or role change.

**Stack (greenfield 2026):** Vanta, KnowBe4, Checkr, BookStack

<sub>ISO-A5-37, ISO-A6-01, ISO-A6-02, ISO-A6-03, ISO-A6-04, ISO-A6-05, ISO-A6-06, ISO-A6-07, ISO-A6-09</sub>

### ICT Continuity & Disaster Recovery
*Business Continuity* · satisfies 1 constraints

Backup, redundancy and failover capabilities with defined RTO/RPO targets, plus documented and regularly tested restore procedures so information and systems can be recovered to meet business-continuity objectives.

**Stack (greenfield 2026):** AWS Backup, AWS Elastic Disaster Recovery (DRS), Velero, pgBackRest

<sub>ISO-A5-30</sub>
