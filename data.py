"""
Reference data for common Emergency Department orders.

The actual order lists live in an editable sidecar file, data.json,
kept next to this script (or next to the compiled .exe when frozen with
PyInstaller). That means the order sets can be edited on a deployed
machine -- add/remove a lab, tweak a medication's default dose, add an
imaging study -- without recompiling the .exe.

On first run (no data.json present yet), one is created automatically
from the DEFAULTS below, pre-populated with today's order sets, ready to
be hand-edited afterward. If data.json is missing a key or fails to
parse, this module falls back to DEFAULTS for that key (or all of them)
and LOAD_ERROR is set so the app can warn the user instead of crashing.
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
    "Ethanol Level",
    "Acetaminophen Level",
    "Salicylate Level",
    "TSH",
]

# name: display name
# default_dose: pre-filled suggestion (editable in the UI, may be blank)
# default_route: pre-filled suggestion (editable in the UI)
# requires_weight: set true for weight-based dosing -- if any checked
#   medication has this set, the generated order sheet adds a reminder
#   line at the bottom to document patient height/weight. Omitted
#   entries default to false.
DEFAULT_MEDICATIONS = [
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
    {"name": "Epinephrine 1:1,000", "default_dose": "0.5 mg", "default_route": "IM"},
    {"name": "Albuterol Nebulizer", "default_dose": "2.5 mg", "default_route": "Neb"},
    {"name": "Ipratropium Nebulizer", "default_dose": "0.5 mg", "default_route": "Neb"},
    {"name": "Methylprednisolone (Solu-Medrol)", "default_dose": "125 mg", "default_route": "IV"},
    {"name": "Dexamethasone", "default_dose": "10 mg", "default_route": "IV/PO"},
    {"name": "Prednisone", "default_dose": "40 mg", "default_route": "PO"},
    {"name": "Nitroglycerin SL", "default_dose": "0.4 mg", "default_route": "SL"},
    {"name": "Ceftriaxone (Rocephin)", "default_dose": "1 g", "default_route": "IV"},
    {"name": "Cefazolin (Ancef)", "default_dose": "1 g", "default_route": "IV"},
    {"name": "Cefepime", "default_dose": "1 g", "default_route": "IV"},
    {"name": "Vancomycin", "default_dose": "20 mg/kg", "default_route": "IV", "requires_weight": True},
    {"name": "Ampicillin-Sulbactam (Unasyn)", "default_dose": "3 g", "default_route": "IV"},
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
    {"name": "Activated Charcoal", "default_dose": "50 g", "default_route": "PO", "requires_weight": True},
    {"name": "Tetanus/Tdap Booster", "default_dose": "0.5 mL", "default_route": "IM"},
    {"name": "Ketamine", "default_dose": "", "default_route": "IV", "requires_weight": True},
    {"name": "Etomidate", "default_dose": "", "default_route": "IV", "requires_weight": True},
    {"name": "Rocuronium", "default_dose": "", "default_route": "IV", "requires_weight": True},
    {"name": "Succinylcholine", "default_dose": "", "default_route": "IV", "requires_weight": True},
]

# Common routes offered in the Route dropdown (still freely editable).
DEFAULT_COMMON_ROUTES = [
    "PO", "IV", "IM", "SL", "SC", "PR", "IN", "Neb", "Topical", "IV/PO", "IV/SC",
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
]

_DEFAULTS = {
    "labs": DEFAULT_LABS,
    "medications": DEFAULT_MEDICATIONS,
    "common_routes": DEFAULT_COMMON_ROUTES,
    "imaging_modalities": DEFAULT_IMAGING_MODALITIES,
    "contrast_modalities": DEFAULT_CONTRAST_MODALITIES,
    "other_orders": DEFAULT_OTHER_ORDERS,
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
IMAGING_MODALITIES = _data["imaging_modalities"]
CONTRAST_MODALITIES = set(_data["contrast_modalities"])
OTHER_ORDERS = _data["other_orders"]
