"""
Reference data for common Emergency Department orders.
"""

import json
import os
import sys

# --- Defaults / seed content for data.json --------------------------------

DEFAULT_LABS = [
    "CBC",
    "BMP",
    "CMP",
    "LFTs",
    "Lipase",
    "Magnesium",
    "Phosphorus",
    "Lactic Acid",
    "D-Dimer",
    "Troponin",
    "BNP",
    "Ammonia",
    "PT/INR",
    "PTT",
    "Type & Screen",
    "Type & Crossmatch",
    "Venous Blood Gas (VBG)",
    "Arterial Blood Gas (ABG)",
    "Urinalysis (UA)",
    "Urine Culture",
    "Urine hCG",
    "Serum hCG (Qualitative)",
    "Serum hCG (Quantitative)",
    "Blood Cultures x2",
    "Rapid Strep",
    "Influenza/COVID/RSV PCR",
    "Serum Tox",
    "Urine Toxicology Screen",
    "Ethanol Level",
    "Acetaminophen Level",
    "Salicylate Level",
    "TSH",
    "POC Glucose",
]

# name: display name
# default_dose: pre-filled suggestion (editable in the UI, may be blank)
# default_route: pre-filled suggestion (editable in the UI)
# default_frequency: pre-filled suggestion for the Frequency field (may be blank)
# allow_prn: set true if this medication may be ordered PRN -- only then
#   does its row's PRN checkbox (and PRN Reason field) become clickable.
#   Omitted entries default to false (PRN checkbox stays disabled), since
#   most scheduled/one-time meds (antibiotics, boluses, RSI drugs, etc.)
#   aren't ordered PRN.
# default_prn_reason: pre-filled suggestion for the PRN Reason field, used
#   when the PRN box is checked (only meaningful if allow_prn is true)
# requires_weight: set true for weight-based dosing -- if any checked
#   medication has this set, the generated order sheet adds a reminder
#   line at the bottom to document patient height/weight. Omitted
#   entries default to false.
DEFAULT_MEDICATIONS = [
    {"name": "Acetaminophen (Tylenol)", "default_dose": "650 mg", "default_route": "PO", "default_frequency": "Q6H", "allow_prn": True, "default_prn_reason": "Pain/Fever"},
    {"name": "Ibuprofen (Motrin)", "default_dose": "600 mg", "default_route": "PO", "default_frequency": "Q6H", "allow_prn": True, "default_prn_reason": "Pain/Fever"},
    {"name": "Ketorolac (Toradol)", "default_dose": "15 mg", "default_route": "IV", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Pain"},
    {"name": "Aspirin", "default_dose": "324 mg", "default_route": "PO", "default_frequency": "Once"},
    {"name": "Ondansetron (Zofran) ODT", "default_dose": "4 mg", "default_route": "PO", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Nausea/Vomiting"},
    {"name": "Ondansetron (Zofran)", "default_dose": "4 mg", "default_route": "IV", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Nausea/Vomiting"},
    {"name": "Metoclopramide (Reglan)", "default_dose": "10 mg", "default_route": "IV", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Nausea/Vomiting"},
    {"name": "Diphenhydramine (Benadryl)", "default_dose": "25 mg", "default_route": "IV", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Itching/Allergic Reaction"},
    {"name": "Famotidine (Pepcid)", "default_dose": "20 mg", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Morphine", "default_dose": "4 mg", "default_route": "IV", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Pain"},
    {"name": "Fentanyl", "default_dose": "50 mcg", "default_route": "IV", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Pain"},
    {"name": "Lorazepam (Ativan)", "default_dose": "1 mg", "default_route": "IV", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Anxiety/Agitation"},
    {"name": "Naloxone (Narcan)", "default_dose": "0.4 mg", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Epinephrine 1:1,000", "default_dose": "0.5 mg", "default_route": "IM", "default_frequency": "Once"},
    {"name": "Albuterol Nebulizer", "default_dose": "2.5 mg", "default_route": "Neb", "default_frequency": "Q4H", "allow_prn": True, "default_prn_reason": "Shortness of Breath/Wheezing"},
    {"name": "Ipratropium Nebulizer", "default_dose": "0.5 mg", "default_route": "Neb", "default_frequency": "Q6H", "allow_prn": True},
    {"name": "Methylprednisolone (Solu-Medrol)", "default_dose": "125 mg", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Dexamethasone", "default_dose": "10 mg", "default_route": "IV/PO", "default_frequency": "Once"},
    {"name": "Prednisone", "default_dose": "40 mg", "default_route": "PO", "default_frequency": "Once"},
    {"name": "Nitroglycerin SL", "default_dose": "0.4 mg", "default_route": "SL", "default_frequency": "Once", "allow_prn": True, "default_prn_reason": "Chest Pain"},
    {"name": "Ceftriaxone (Rocephin)", "default_dose": "1 g", "default_route": "IV", "default_frequency": "Q24H"},
    {"name": "Cefazolin (Ancef)", "default_dose": "1 g", "default_route": "IV", "default_frequency": "Q8H"},
    {"name": "Cefepime", "default_dose": "1 g", "default_route": "IV", "default_frequency": "Q8H"},
    {"name": "Vancomycin", "default_dose": "20 mg/kg", "default_route": "IV", "default_frequency": "Q12H", "requires_weight": True},
    {"name": "Ampicillin-Sulbactam (Unasyn)", "default_dose": "3 g", "default_route": "IV", "default_frequency": "Q6H"},
    {"name": "Piperacillin-Tazobactam (Zosyn)", "default_dose": "3.375 g", "default_route": "IV", "default_frequency": "Q6H"},
    {"name": "Azithromycin", "default_dose": "500 mg", "default_route": "PO", "default_frequency": "Q24H"},
    {"name": "Metronidazole (Flagyl)", "default_dose": "500 mg", "default_route": "PO", "default_frequency": "Q8H"},
    {"name": "Normal Saline Bolus", "default_dose": "1 L", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Lactated Ringers Bolus", "default_dose": "1 L", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Dextrose 50%", "default_dose": "25 g", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Insulin Regular for Hyperkalemia", "default_dose": "10", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Insulin Aspart (Novolog)", "default_dose": "", "default_route": "SC", "default_frequency": "Once"},
    {"name": "Magnesium Sulfate", "default_dose": "2 g", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Calcium Gluconate", "default_dose": "1 g", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Sodium Bicarbonate", "default_dose": "1 amp", "default_route": "IV", "default_frequency": "Once"},
    {"name": "Activated Charcoal", "default_dose": "50 g", "default_route": "PO", "default_frequency": "Once", "requires_weight": True},
    {"name": "Tetanus/Tdap Booster", "default_dose": "0.5 mL", "default_route": "IM", "default_frequency": "Once"},
    {"name": "Ketamine", "default_dose": "", "default_route": "IV", "default_frequency": "Once", "requires_weight": True},
    {"name": "Etomidate", "default_dose": "", "default_route": "IV", "default_frequency": "Once", "requires_weight": True},
    {"name": "Rocuronium", "default_dose": "", "default_route": "IV", "default_frequency": "Once", "requires_weight": True},
    {"name": "Succinylcholine", "default_dose": "", "default_route": "IV", "default_frequency": "Once", "requires_weight": True},
]

# Common routes offered in the Route dropdown (still freely editable).
DEFAULT_COMMON_ROUTES = [
    "PO", "IV", "IM", "SL", "SC", "PR", "IN", "Neb", "Topical", "IV/PO", "IV/SC",
]

# Common frequencies offered in the Frequency dropdown (still freely editable).
DEFAULT_COMMON_FREQUENCIES = [
    "Once", "Daily", "BID", "TID", "QID", "Q4H", "Q6H", "Q8H", "Q12H", "Q24H", "Continuous",
]

# Common PRN reasons offered in the PRN Reason dropdown (still freely editable).
DEFAULT_PRN_REASONS = [
    "Pain", "Pain/Fever", "Fever", "Nausea/Vomiting", "Anxiety/Agitation",
    "Itching/Allergic Reaction", "Insomnia", "Constipation",
    "Shortness of Breath/Wheezing", "Chest Pain", "Breakthrough Pain",
]

# Common titration frequencies offered in the Drips tab (still freely editable).
DEFAULT_TITRATE_FREQUENCIES = [
    "Q5min", "Q10min", "Q15min", "Q30min", "Q1H", "Q2H", "Per Protocol",
]

# Continuous IV drip/infusion medications, shown on their own "Drips" tab
# since they need titration fields instead of a simple dose/route/frequency.
# name: display name
# default_initial_dose: pre-filled suggestion for the starting rate (may be blank)
# default_titrate_by: pre-filled suggestion for how much to titrate by (may be blank)
# default_titrate_frequency: pre-filled suggestion for how often to titrate (may be blank)
# default_max_dose: pre-filled suggestion for the not-to-exceed rate (may be blank)
# default_goal: pre-filled suggestion for the free-text titration goal (may be blank)
# requires_weight: same meaning as on DEFAULT_MEDICATIONS -- weight-based
#   (mcg/kg/min etc.) drips trigger the height/weight reminder line.
# is_protocol: set true for a drip that follows a fixed, non-titrated,
#   multi-phase regimen (e.g. Amiodarone's load-then-maintenance dosing)
#   rather than a simple start/titrate-by/frequency/max/goal shape. When
#   set, the Drips tab shows one free-text Protocol field pre-filled from
#   default_protocol_text instead of the usual titration fields.
# default_protocol_text: pre-filled suggestion for that free-text field
#   (only meaningful when is_protocol is true; may be blank)
DEFAULT_DRIPS = [
    {"name": "Norepinephrine (Levophed) 8mg/250mL", "default_initial_dose": "4 mcg/min", "default_titrate_by": "1- 4 mcg/min", "default_titrate_frequency": "Q5min", "default_max_dose": "50 mcg/min", "default_goal": "MAP >= 65"},
    {"name": "Epinephrine 5mg/250mL", "default_initial_dose": "2.5 mcg/min", "default_titrate_by": "2.5 mcg/min", "default_titrate_frequency": "Q5min", "default_max_dose": "20 mcg/min", "default_goal": "MAP >= 65", "requires_weight": True},
    {"name": "Vasopressin 20 units/100 mL", "default_initial_dose": "0.03 units/min", "default_max_dose": "0.03 units/min", "default_goal": "MAP >= 65"},
    {"name": "Dopamine", "default_initial_dose": "5 mcg/kg/min", "default_titrate_by": "2.5 mcg/kg/min", "default_titrate_frequency": "Q5-10min", "default_max_dose": "20 mcg/kg/min", "default_goal": "MAP >= 65", "requires_weight": True},
    {"name": "Propofol 1000 mg/100mL", "default_initial_dose": "10mcg/kg/min", "default_titrate_by": "5 mcg/kg/min", "default_titrate_frequency": "Q5min", "default_max_dose": "50 mcg/kg/min", "default_goal": "RASS -2 to 0", "requires_weight": True},
    {"name": "Nicardipine 25 mg/250 mL", "default_initial_dose": "5 mg/hr", "default_titrate_by": "2.5 mg/hr", "default_titrate_frequency": "Q15min", "default_max_dose": "15 mg/hr", "default_goal": "SBP < 140"},
    {"name": "Diltiazem Infusion 125 mg/125 mL", "default_initial_dose": "5 mg/hr", "default_titrate_by": "5 mg/hr", "default_titrate_frequency": "Q60min", "default_max_dose": "15 mg/hr", "default_goal": "HR < 110"},
    {"name": "Amiodarone (Drip)", "is_protocol": True, "default_protocol_text": "150 mg IV over 10 min, then 360 mg/200 mL 1 mg/min x 6h, then 540 mg/300 mL 0.5 mg/min x 18h (max 2.2 g/24h)"},
    {"name": "Nitroglycerin (Drip)", "default_initial_dose": "10 mcg/min", "default_titrate_by": "10 mcg/min", "default_titrate_frequency": "Q5min", "default_max_dose": "200 mcg/min", "default_goal": "SBP < 140 / pain relief"},
]

# Modality -> list of study names available in the Study dropdown.
DEFAULT_IMAGING_MODALITIES = {
    "XR": [
        "Chest",
        "Abdomen",
        "Pelvis",
        "C-Spine",
        "T-Spine",
        "L-Spine",
        "Shoulder",
        "Humerus",
        "Elbow",
        "Forearm",
        "Wrist",
        "Hand",
        "Finger",
        "Hip",
        "Femur",
        "Knee",
        "Tibia/Fibula",
        "Ankle",
        "Foot",
        "Toe",
        "Rib Series",
    ],
    "CT": [
        "Head",
        "C-Spine",
        "Chest",
        "Chest (PE Protocol)",
        "Chest/Abdomen/Pelvis",
        "Abdomen/Pelvis",
        "CT Angiogram Head/Neck",
        "Maxillofacial",
    ],
    "MRI": [
        "Brain",
        "C-Spine",
        "T-Spine",
        "L-Spine",
        "Orbit",
    ],
    "US": [
        "Abdominal (RUQ/Gallbladder)",
        "Complete Abdomen",
        "Renal",
        "Pelvic (Transabdominal)",
        "Pelvic (Transvaginal)",
        "Aorta",
        "Soft Tissue",
        "Venous Doppler / DVT Study",
        "Testicular",
    ],
}

# Modalities for which a "With Contrast" checkbox is offered (contrast is
# handled as a separate toggle instead of being baked into every study name).
DEFAULT_CONTRAST_MODALITIES = ["CT", "MRI"]

DEFAULT_OTHER_ORDERS = [
    "EKG",
    "IV Access",
    "Continuous Cardiac Monitoring",
    "Continuous Pulse Oximetry",
    "Vital Signs per ED Protocol",
    "NPO",
    "Foley Catheter",
    "Incentive Spirometry",
    "Fall Precautions",
    "Aspiration Precautions",
    "Strict Intake & Output",
    "Wound Care / Dressing Change",
    "Splint Application",
    "Ice Pack to Affected Area",
    "Elevate Extremity",
    "Weight-Bearing as Tolerated",
    "Non-Weight-Bearing",
    "Social Work Consult",
    "Case Management Consult",
    "Nasal Cannula Oxygen @ 2 L/min",
    "Straight Catheterization",
    "C-Collar Placement",
    "Close Observation (Suicide Precautions)",
    "NIH Stroke Scale",
    "Neuro Checks",
    "Dysphagia Screen",
]

# Order sets: one click checks off a whole bundle of orders.
#   name: button label
#   labs: list of lab names (must match an entry in "labs" to take effect)
#   medications: list of {"name" (must match "medications"), and optionally
#     "dose"/"route"/"frequency" overrides, "prn": true, "prn_reason": "..."}
#   imaging: list of {"modality", "study", "indication", optional "contrast": true}
#     -- "study" doesn't have to be in that modality's dropdown list; it's
#     added as free text either way.
#   other: list of names (must match an entry in "other_orders")
#
# Two kinds:
#   - Regular sets (is_aop absent/false): applying one is ADDITIVE -- it
#     doesn't uncheck/replace anything already selected, so multiple sets
#     can be combined freely with each other and with manual selections.
#   - AOP sets (is_aop: true) -- "Approved Order Protocol" bundles a nurse
#     orders under a standing protocol, not a physician composing an order
#     individually. Applying one clears any current selections, checks off
#     exactly that bundle, and then LOCKS every other order control in the
#     app so nothing outside the protocol can be added (the protocol's own
#     items stay editable/uncheckable). "indication" is required for these
#     -- it's printed as the top line of the order sheet ("AOP: {name} -
#     Indication: {indication}"), and the sheet gets an Ordering Nurse
#     signature line plus a blank Physician signature line instead of the
#     usual single physician signature line. Click "Clear All Selections"
#     to exit AOP mode and unlock everything again.
DEFAULT_ORDER_SETS = [
    {
        "name": "Chest Pain / ACS",
        "labs": ["CBC", "BMP", "Troponin", "PT/INR", "PTT", "Type & Screen"],
        "medications": [
            {"name": "Aspirin"},
            {"name": "Nitroglycerin SL", "prn": True, "prn_reason": "Chest Pain"},
        ],
        "imaging": [
            {"modality": "XR", "study": "Chest", "indication": "Chest pain"},
        ],
        "other": ["EKG", "IV Access", "Continuous Cardiac Monitoring", "Continuous Pulse Oximetry"],
    },
    {
        "name": "Sepsis",
        "labs": ["CBC", "BMP", "Lactic Acid", "Blood Cultures x2", "Urinalysis (UA)", "Urine Culture", "PT/INR", "PTT"],
        "medications": [
            {"name": "Normal Saline Bolus"},
            {"name": "Ceftriaxone (Rocephin)"},
        ],
        "imaging": [
            {"modality": "XR", "study": "Chest", "indication": "Sepsis workup, r/o pneumonia"},
        ],
        "other": [
            "IV Access", "Continuous Cardiac Monitoring", "Continuous Pulse Oximetry",
            "Strict Intake & Output", "Vital Signs per ED Protocol",
        ],
    },
    {
        "name": "Abdominal Pain",
        "labs": ["CBC", "CMP", "Lipase", "Urinalysis (UA)", "Urine hCG"],
        "medications": [
            {"name": "Ondansetron (Zofran)", "prn": True, "prn_reason": "Nausea/Vomiting"},
            {"name": "Ketorolac (Toradol)", "prn": True, "prn_reason": "Pain"},
        ],
        "imaging": [
            {"modality": "CT", "study": "Abdomen/Pelvis", "indication": "Abdominal pain", "contrast": True},
        ],
        "other": ["IV Access"],
    },
    {
        "name": "Renal Colic",
        "labs": ["CBC", "BMP", "Urinalysis (UA)", "Urine hCG"],
        "medications": [
            {"name": "Ketorolac (Toradol)", "prn": True, "prn_reason": "Pain"},
            {"name": "Ondansetron (Zofran)", "prn": True, "prn_reason": "Nausea/Vomiting"},
        ],
        "imaging": [
            {"modality": "CT", "study": "CT KUB (Renal Stone Protocol)", "indication": "Flank pain, r/o nephrolithiasis"},
        ],
        "other": ["IV Access"],
    },
    {
        "name": "Stroke / Code Stroke",
        "labs": ["CBC", "BMP", "PT/INR", "PTT", "Type & Screen"],
        "medications": [],
        "imaging": [
            {"modality": "CT", "study": "Head", "indication": "Acute stroke - code stroke protocol"},
        ],
        "other": [
            "EKG", "IV Access", "Continuous Cardiac Monitoring",
            "Continuous Pulse Oximetry", "Vital Signs per ED Protocol",
        ],
    },
    {
        "name": "Asthma / COPD Exacerbation",
        "labs": [],
        "medications": [
            {"name": "Albuterol Nebulizer"},
            {"name": "Ipratropium Nebulizer"},
            {"name": "Methylprednisolone (Solu-Medrol)"},
        ],
        "imaging": [
            {"modality": "XR", "study": "Chest", "indication": "Respiratory distress"},
        ],
        "other": ["Continuous Pulse Oximetry"],
    },
    # --- AOP (nurse-driven protocol) sets -------------------------------
    # Sourced from "AOP Orders.xlsx". Two protocols in that sheet were left
    # out: "Sickle Cell" (every order line was marked not-currently-live)
    # and its blanket pregnancy-screen items (moved into the "Female < 50"
    # modifier below instead, since a flat AOP bundle can't express "only if
    # potentially pregnant" -- see is_aop_modifier).
    {
        "name": "PT/INR (On Coumadin)",
        "is_aop": True,
        "indication": "On Warfarin (Coumadin)",
        "labs": ["PT/INR"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    {
        "name": "Oxygen (O2 Sat < 90%)",
        "is_aop": True,
        "indication": "O2 Saturation < 90%",
        "labs": [],
        "medications": [],
        "imaging": [],
        "other": ["Nasal Cannula Oxygen @ 2 L/min"],
    },
    {
        "name": "Abdominal Pain",
        "is_aop": True,
        "indication": "Abdominal Pain",
        "labs": ["CBC", "CMP", "Lipase"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    {
        "name": "Abnormal Labs",
        "is_aop": True,
        "indication": "Abnormal Labs",
        "labs": ["CBC", "CMP"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    {
        "name": "Altered Mental Status",
        "is_aop": True,
        "indication": "Altered Mental Status",
        "labs": ["CBC", "POC Glucose", "Urinalysis (UA)", "CMP"],
        "medications": [],
        "imaging": [],
        "other": ["NPO", "EKG"],
    },
    {
        "name": "Cellulitis",
        "is_aop": True,
        "indication": "Cellulitis",
        "labs": ["CBC", "BMP"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    {
        "name": "Chest Pain (Non-Traumatic, Age >=30)",
        "is_aop": True,
        "indication": "Chest Pain, non-traumatic, age >= 30",
        "labs": ["CBC", "CMP"],
        "medications": [],
        "imaging": [],
        "other": ["EKG"],
    },
    {
        "name": "Dizziness/Lightheadedness",
        "is_aop": True,
        "indication": "Dizziness/Lightheadedness",
        "labs": ["CBC", "BMP"],
        "medications": [],
        "imaging": [],
        "other": ["EKG"],
    },
    {
        "name": "Dysuria/UTI",
        "is_aop": True,
        "indication": "Dysuria/UTI Symptoms",
        "labs": ["Urinalysis (UA)"],
        "medications": [],
        "imaging": [],
        "other": ["Straight Catheterization"],
    },
    {
        "name": "Fall/Trauma",
        "is_aop": True,
        "indication": "Fall/Trauma",
        "labs": ["CBC", "CMP", "Lactic Acid", "Urinalysis (UA)"],
        "medications": [],
        "imaging": [],
        "other": ["C-Collar Placement", "EKG"],
    },
    {
        "name": "Generalized Weakness/Fatigue (Age >=70)",
        "is_aop": True,
        "indication": "Generalized Weakness/Fatigue, age >= 70",
        "labs": ["CBC", "CMP", "Urinalysis (UA)"],
        "medications": [],
        "imaging": [],
        "other": ["EKG"],
    },
    {
        "name": "GI Bleed",
        "is_aop": True,
        "indication": "GI Bleed",
        "labs": ["CBC", "CMP"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    {
        "name": "MH Eval/Emergency Petition",
        "is_aop": True,
        "indication": "Mental Health Evaluation / Emergency Petition",
        "labs": ["Urine Toxicology Screen", "CBC", "CMP", "Serum Tox"],
        "medications": [],
        "imaging": [],
        "other": ["Close Observation (Suicide Precautions)"],
    },
    {
        "name": "Numbness/Weakness (Non-Stroke)",
        "is_aop": True,
        "indication": "Numbness/Weakness",
        "labs": ["CBC", "BMP"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    {
        "name": "Renal Colic/Flank Pain",
        "is_aop": True,
        "indication": "Renal Colic/Flank Pain",
        "labs": ["Urinalysis (UA)", "CBC", "BMP"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    {
        "name": "Seizure",
        "is_aop": True,
        "indication": "Seizure",
        "labs": ["CBC", "CMP"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    {
        "name": "SOB without Fever (Age >=50)",
        "is_aop": True,
        "indication": "SOB without fever, age >= 50",
        "labs": ["CBC", "CMP", "Troponin"],
        "medications": [],
        "imaging": [],
        "other": ["EKG"],
    },
    {
        "name": "Stroke (Brain Attack)",
        "is_aop": True,
        "indication": "Stroke (Brain Attack)",
        "labs": ["CBC", "CMP", "PT/INR", "PTT", "Troponin", "Type & Screen", "Urinalysis (UA)"],
        "medications": [],
        "imaging": [
            {"modality": "CT", "study": "Head", "indication": "Acute stroke - stroke protocol"},
        ],
        "other": [
            "Continuous Pulse Oximetry", "Nasal Cannula Oxygen @ 2 L/min", "NIH Stroke Scale",
            "Neuro Checks", "Straight Catheterization", "NPO", "Dysphagia Screen", "EKG",
        ],
    },
    {
        "name": "Syncope",
        "is_aop": True,
        "indication": "Syncope/Near Syncope",
        "labs": ["CBC", "BMP"],
        "medications": [],
        "imaging": [],
        "other": ["EKG"],
    },
    {
        "name": "Vaginal Bleeding",
        "is_aop": True,
        "indication": "Vaginal Bleeding",
        "labs": ["CBC", "CMP"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
    # --- AOP modifiers ---------------------------------------------------
    # Stack on top of an already-active AOP (unlike a regular AOP, doesn't
    # clear/replace the current selection or lock the app on its own) --
    # for criteria that apply across many protocols rather than defining
    # one. See is_aop_modifier handling in app.py.
    {
        "name": "Female < 50 (Pregnancy Screen)",
        "is_aop_modifier": True,
        "labs": ["Serum hCG (Qualitative)"],
        "medications": [],
        "imaging": [],
        "other": [],
    },
]

_DEFAULTS = {
    "labs": DEFAULT_LABS,
    "medications": DEFAULT_MEDICATIONS,
    "common_routes": DEFAULT_COMMON_ROUTES,
    "common_frequencies": DEFAULT_COMMON_FREQUENCIES,
    "prn_reasons": DEFAULT_PRN_REASONS,
    "titrate_frequencies": DEFAULT_TITRATE_FREQUENCIES,
    "drips": DEFAULT_DRIPS,
    "imaging_modalities": DEFAULT_IMAGING_MODALITIES,
    "contrast_modalities": DEFAULT_CONTRAST_MODALITIES,
    "other_orders": DEFAULT_OTHER_ORDERS,
    "order_sets": DEFAULT_ORDER_SETS,
}


# --- Sidecar file loading ---------------------------------------------------

def _app_dir():
    """Directory the .exe lives in when frozen (PyInstaller), otherwise the
    directory this script lives in when run from source."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATA_FILE_PATH = os.path.join(_app_dir(), "data.json")


def _load():
    """Returns (data_dict, error_message_or_None)."""
    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            merged = dict(_DEFAULTS)
            merged.update({k: v for k, v in loaded.items() if k in _DEFAULTS})
            return merged, None
        except (json.JSONDecodeError, OSError) as exc:
            return dict(_DEFAULTS), "Couldn't read {}: {}".format(DATA_FILE_PATH, exc)
    else:
        try:
            with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(_DEFAULTS, f, indent=2)
        except OSError:
            pass  # read-only install location, e.g. -- fall back silently
        return dict(_DEFAULTS), None


_data, LOAD_ERROR = _load()

LABS = _data["labs"]
MEDICATIONS = _data["medications"]
COMMON_ROUTES = _data["common_routes"]
COMMON_FREQUENCIES = _data["common_frequencies"]
PRN_REASONS = _data["prn_reasons"]
TITRATE_FREQUENCIES = _data["titrate_frequencies"]
DRIPS = _data["drips"]
IMAGING_MODALITIES = _data["imaging_modalities"]
CONTRAST_MODALITIES = set(_data["contrast_modalities"])
OTHER_ORDERS = _data["other_orders"]
ORDER_SETS = _data["order_sets"]
