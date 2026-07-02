"""Build the ~30 extraction shards fanned out across the three frameworks.

Each shard is one unit of work for one parallel agent: a bounded slice of a
framework small enough to extract in a single ``max_turns`` agent run. Pure
stdlib — no SDK, no config import — so it is cheap to unit-test.
"""

from __future__ import annotations

# Each entry: (key, title, scope_hint). key must be filename-safe and unique
# within its framework (it names the per-shard temp file).
_GDPR = [
    ("principles", "Principles (Art. 5)",
     "Lawfulness, fairness, transparency, purpose limitation, data minimisation, "
     "accuracy, storage limitation, integrity/confidentiality, accountability."),
    ("lawful-basis", "Lawful basis & consent (Art. 6–11)",
     "Lawfulness of processing, conditions for consent, children, special "
     "categories, criminal-conviction data, processing not requiring identification."),
    ("rights-transparency", "Transparency & access (Art. 12–15)",
     "Transparent information, information to be provided when data is/ isn't "
     "collected from the subject, right of access."),
    ("rights-control", "Rectification, erasure, restriction (Art. 16–20)",
     "Rectification, erasure ('right to be forgotten'), restriction, notification "
     "obligation, data portability."),
    ("rights-object", "Objection & automated decisions (Art. 21–23)",
     "Right to object, automated individual decision-making including profiling, "
     "and permitted restrictions."),
    ("controller-core", "Controller & processor duties (Art. 24–31)",
     "Responsibility, data protection by design and by default, joint controllers, "
     "representatives, processor contracts, records of processing, cooperation."),
    ("security-breach", "Security & breach (Art. 32–34)",
     "Security of processing, breach notification to the authority and to data "
     "subjects, timelines and thresholds."),
    ("dpia-dpo", "DPIA & DPO (Art. 35–39)",
     "Data protection impact assessment, prior consultation, designation, position "
     "and tasks of the data protection officer."),
    ("transfers", "International transfers (Art. 44–50)",
     "Adequacy, appropriate safeguards, SCCs/BCRs, derogations, transfers not "
     "authorised by Union law."),
    ("remedies", "Remedies, liability & penalties (Art. 77–84)",
     "Right to lodge complaints, judicial remedies, compensation and liability, "
     "administrative fines and their conditions."),
]

_SOC2 = [
    ("cc1", "Common Criteria CC1 — Control environment",
     "Integrity/ethics, board oversight, structure/authority, competence, accountability."),
    ("cc2", "Common Criteria CC2 — Communication & information",
     "Quality information, internal and external communication of objectives/controls."),
    ("cc3", "Common Criteria CC3 — Risk assessment",
     "Objectives, risk identification/analysis, fraud risk, change impact."),
    ("cc4", "Common Criteria CC4 — Monitoring activities",
     "Ongoing/separate evaluations; evaluating and communicating deficiencies."),
    ("cc5", "Common Criteria CC5 — Control activities",
     "Selection/development of controls and technology, deployment via policy."),
    ("cc6", "Common Criteria CC6 — Logical & physical access",
     "Identity/credentials, access provisioning/removal, least privilege, "
     "boundary protection, encryption, physical access."),
    ("cc7", "Common Criteria CC7 — System operations",
     "Vulnerability detection, monitoring, incident response and recovery."),
    ("cc8", "Common Criteria CC8 — Change management",
     "Authorising, designing, developing, testing and deploying changes."),
    ("cc9", "Common Criteria CC9 — Risk mitigation",
     "Risk-mitigation activities; vendor and business-partner risk."),
    ("availability", "Availability criteria (A1)",
     "Capacity, environmental protections, backup and recovery."),
    ("confidentiality", "Confidentiality criteria (C1)",
     "Identification, retention and disposal of confidential information."),
    ("processing-integrity", "Processing Integrity criteria (PI1)",
     "Completeness, validity, accuracy, timeliness, authorisation of processing."),
    ("privacy", "Privacy criteria (P1–P8)",
     "Notice, choice/consent, collection, use/retention/disposal, access, "
     "disclosure, quality, monitoring and enforcement."),
]

_ISO = [
    ("org-a5-1", "Organizational A.5 — policies & responsibilities",
     "Information security policies, roles/responsibilities, segregation of duties, "
     "management responsibilities, contact with authorities and special-interest "
     "groups, threat intelligence, security in project management."),
    ("org-a5-2", "Organizational A.5 — assets & access policy",
     "Inventory and acceptable use of information/assets, return of assets, "
     "classification and labelling, information transfer, access control policy, "
     "identity and authentication information management."),
    ("org-a5-3", "Organizational A.5 — suppliers, incidents, continuity, legal",
     "Supplier and cloud-service security, incident management and evidence, ICT "
     "readiness for continuity, legal/statutory/contractual and privacy "
     "requirements, intellectual property, documented operating procedures."),
    ("people-a6", "People controls A.6",
     "Screening, terms of employment, awareness/education/training, disciplinary "
     "process, responsibilities after termination, confidentiality agreements, "
     "remote working, security event reporting."),
    ("physical-a7-1", "Physical A.7 — perimeter & entry",
     "Physical security perimeters, entry controls, securing offices/rooms/"
     "facilities, physical security monitoring, protection against physical and "
     "environmental threats, working in secure areas."),
    ("physical-a7-2", "Physical A.7 — equipment",
     "Clear desk/screen, equipment siting and protection, supporting utilities, "
     "cabling security, equipment maintenance, secure disposal or reuse, removal "
     "of assets off premises."),
    ("tech-a8-1", "Technological A.8 — access & endpoints",
     "User endpoint devices, privileged access rights, information access "
     "restriction, access to source code, secure authentication, capacity "
     "management, protection against malware."),
    ("tech-a8-2", "Technological A.8 — vulnerabilities & data protection",
     "Technical vulnerability management, configuration management, information "
     "deletion, data masking, data leakage prevention."),
    ("tech-a8-3", "Technological A.8 — resilience & monitoring",
     "Backup, redundancy, logging, monitoring activities, clock synchronisation, "
     "use of privileged utility programs, installation of software on systems."),
    ("tech-a8-4", "Technological A.8 — network & cryptography",
     "Network security, security of network services, segregation of networks, "
     "web filtering, use of cryptography."),
    ("tech-a8-5", "Technological A.8 — secure development",
     "Secure development lifecycle, application security requirements, secure "
     "architecture/engineering, secure coding, security testing, outsourced "
     "development, separation of environments, change management, test information, "
     "protection of audit test systems."),
]

_FRAMEWORK_SHARDS = {"gdpr": _GDPR, "soc2": _SOC2, "iso27001": _ISO}


def build_shards(cfg: dict) -> list[dict]:
    """All shards for the frameworks enabled in ``cfg`` (order: config order)."""
    shards: list[dict] = []
    for fw in cfg.get("frameworks", list(_FRAMEWORK_SHARDS)):
        for key, title, scope_hint in _FRAMEWORK_SHARDS.get(fw, []):
            shards.append(
                {"framework": fw, "key": key, "title": title, "scope_hint": scope_hint}
            )
    return shards
