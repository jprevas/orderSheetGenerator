"""
Reference data for common Emergency Department orders.

This is a starting set covering the most frequently used ED labs,
medications, and imaging studies. Edit these lists to customize the
order sets available in the app -- nothing elsewhere in the program
needs to change.
"""

# --- Labs -------------------------------------------------------------
# Simple list of lab order names shown as checkboxes.
LABS = [
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
    "Ethanol Level",
    "Acetaminophen Level",
    "Salicylate Level",
    "TSH",
]

# --- Medications --------------------------------------------------------
# name: display name
# default_dose: pre-filled suggestion (editable in the UI, may be blank)
# default_route: pre-filled suggestion (editable in the UI)
MEDICATIONS = [
    {"name": "Acetaminophen (Tylenol)", "default_dose": "650 mg", "default_route": "PO"},
    {"name": "Ibuprofen (Motrin)", "default_dose": "600 mg", "default_route": "PO"},
    {"name": "Ketorolac (Toradol)", "default_dose": "15 mg", "default_route": "IV"},
    {"name": "Aspirin", "default_dose": "324 mg", "default_route": "PO"},
    {"name": "Ondansetron (Zofran) ODT", "default_dose": "4 mg", "default_route": "PO"},
    {"name": "Ondansetron (Zofran)", "default_dose": "4 mg", "default_route": "IV"},
    {"name": "Metoclopramide (Reglan)", "default_dose": "10 mg", "default_route": "IV"},
    {"name": "Diphenhydramine (Benadryl)", "default_dose": "25 mg", "default_route": "IV"},
    {"name": "Famotidine (Pepcid)", "default_dose": "20 mg", "default_route": "IV"},
    {"name": "Morphine", "default_dose": "4 mg", "default_route": "IV"},
    {"name": "Fentanyl", "default_dose": "50 mcg", "default_route": "IV"},
    {"name": "Lorazepam (Ativan)", "default_dose": "1 mg", "default_route": "IV"},
    {"name": "Naloxone (Narcan)", "default_dose": "0.4 mg", "default_route": "IV"},
    {"name": "Epinephrine 1:1,000", "default_dose": "0.3 mg", "default_route": "IM"},
    {"name": "Albuterol Nebulizer", "default_dose": "2.5 mg", "default_route": "Neb"},
    {"name": "Ipratropium Nebulizer", "default_dose": "0.5 mg", "default_route": "Neb"},
    {"name": "Methylprednisolone (Solu-Medrol)", "default_dose": "125 mg", "default_route": "IV"},
    {"name": "Dexamethasone", "default_dose": "10 mg", "default_route": "IV/PO"},
    {"name": "Prednisone", "default_dose": "40 mg", "default_route": "PO"},
    {"name": "Nitroglycerin SL", "default_dose": "0.4 mg", "default_route": "SL"},
    {"name": "Ceftriaxone (Rocephin)", "default_dose": "1 g", "default_route": "IV"},
    {"name": "Vancomycin", "default_dose": "", "default_route": "IV"},
    {"name": "Piperacillin-Tazobactam (Zosyn)", "default_dose": "3.375 g", "default_route": "IV"},
    {"name": "Azithromycin", "default_dose": "500 mg", "default_route": "PO"},
    {"name": "Metronidazole (Flagyl)", "default_dose": "500 mg", "default_route": "PO"},
    {"name": "Normal Saline Bolus", "default_dose": "1 L", "default_route": "IV"},
    {"name": "Lactated Ringers Bolus", "default_dose": "1 L", "default_route": "IV"},
    {"name": "Dextrose 50%", "default_dose": "25 g", "default_route": "IV"},
    {"name": "Insulin Regular for Hyperkalemia", "default_dose": "10", "default_route": "IV"},
    {"name": "Insulin Aspart (Novolog)", "default_dose": "", "default_route": "SC"},
    {"name": "Magnesium Sulfate", "default_dose": "2 g", "default_route": "IV"},
    {"name": "Calcium Gluconate", "default_dose": "1 g", "default_route": "IV"},
    {"name": "Sodium Bicarbonate", "default_dose": "1 amp", "default_route": "IV"},
    {"name": "Activated Charcoal", "default_dose": "50 g", "default_route": "PO"},
    {"name": "Tetanus/Tdap Booster", "default_dose": "0.5 mL", "default_route": "IM"},
    {"name": "Ketamine", "default_dose": "", "default_route": "IV"},
    {"name": "Etomidate", "default_dose": "", "default_route": "IV"},
    {"name": "Rocuronium", "default_dose": "", "default_route": "IV"},
    {"name": "Succinylcholine", "default_dose": "", "default_route": "IV"},
]

# Common routes offered in the Route dropdown (still freely editable).
COMMON_ROUTES = [
    "PO", "IV", "IM", "SL", "SC", "PR", "IN", "Neb", "Topical", "IV/PO", "IV/SC",
]

# --- Imaging --------------------------------------------------------------
# Modality -> list of study names available in the Study dropdown.
IMAGING_MODALITIES = {
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
        "Internal Auditory Canal (IAC)",
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
        "Echocardiogram",
        "FAST Exam",
    ],
}

# Modalities for which a "With Contrast" checkbox is offered (contrast is
# handled as a separate toggle instead of being baked into every study name).
CONTRAST_MODALITIES = {"CT", "MRI"}

# --- Other / Nursing orders ------------------------------------------------
OTHER_ORDERS = [
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
]
