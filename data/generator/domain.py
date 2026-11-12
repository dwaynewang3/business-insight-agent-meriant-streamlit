"""Business assumptions for the fictional insurer, Meridian General Insurance.

The numbers are invented but chosen to resemble an Australian motor and home insurer: claim
rates, claim costs in AUD, southern-hemisphere seasons, premiums and geography. Scenario
files decide what differs between the dev and test data; this module holds what stays the
same.
"""

# Metro areas in each state and territory, with the first three digits of their postcodes.
# The first metro in each state is the largest and holds about half of its policies.
METROS: dict[str, dict[str, list[str]]] = {
    "NSW": {
        "Sydney": ["200", "201", "202", "203", "204", "205", "206", "207", "211", "212",
                   "213", "214", "215", "216", "217", "219", "220", "222"],
        "Newcastle-Hunter": ["228", "229", "230", "232"],
        "Wollongong": ["250", "251", "252"],
    },
    "VIC": {
        "Melbourne": ["300", "301", "302", "303", "304", "305", "306", "307", "308", "309",
                      "310", "312", "313", "314", "315", "316", "317", "318", "319"],
        "Geelong": ["321", "322"],
        "Ballarat-Bendigo": ["335", "355"],
    },
    "QLD": {
        "Brisbane": ["400", "401", "405", "406", "407", "410", "411", "412"],
        "Gold Coast": ["420", "421", "422"],
        "Townsville-Cairns": ["481", "487"],
    },
    "WA": {"Perth": ["600", "601", "602", "603", "605", "606", "607", "610", "615", "616"],
           "Bunbury": ["623"]},
    "SA": {"Adelaide": ["500", "501", "502", "503", "504", "505", "506", "507", "508", "509"],
           "Mount Gambier": ["529"]},
    "TAS": {"Hobart": ["700", "701", "702"], "Launceston": ["724", "725"]},
    "ACT": {"Canberra": ["260", "261", "290", "291"]},
    "NT": {"Darwin": ["080", "081", "082"]},
}

# For each product and cause of loss: monthly claim rate per policy, typical claim cost
# (median, AUD), how widely costs vary (lognormal sigma), typical days from report to
# close, and whether a repair shop does the work.
#
# Motor policies don't cover injuries: in Australia those go to compulsory third party
# (CTP) insurance, which is separate. "Storm" is the Australian term for wind, hail and
# rain damage.
CAUSES: dict[str, dict[str, dict]] = {
    "motor": {
        "collision": dict(rate=0.0040, median=6300, sigma=0.70, close_days=21, shop=True),
        "glass": dict(rate=0.0015, median=950, sigma=0.40, close_days=6, shop=True),
        "storm": dict(rate=0.0004, median=5700, sigma=0.50, close_days=18, shop=True),
        "theft": dict(rate=0.0006, median=13500, sigma=0.60, close_days=40, shop=False),
        "third_party_property": dict(rate=0.0008, median=9000, sigma=0.70, close_days=45,
                                     shop=False),
    },
    "home": {
        "water_damage": dict(rate=0.0022, median=13500, sigma=0.70, close_days=35, shop=False),
        "storm": dict(rate=0.0024, median=16500, sigma=0.70, close_days=40, shop=False),
        "fire": dict(rate=0.0003, median=52000, sigma=0.90, close_days=80, shop=False),
        "theft": dict(rate=0.0006, median=6000, sigma=0.60, close_days=25, shop=False),
        "liability": dict(rate=0.0004, median=22000, sigma=0.90, close_days=70, shop=False),
    },
}

# Third-party and liability claims are reported later and take longer to settle.
LONG_TAIL_CAUSES = {"third_party_property", "liability"}

# Seasonal multipliers on claim rates, by (cause, region) and month. Anything unlisted is 1.0.
# Southern-hemisphere seasons: summer is December to February.
SEASONALITY: dict[tuple[str, str], dict[int, float]] = {
    ("storm", "QLD & NT"): {12: 1.7, 1: 2.8, 2: 2.6, 3: 1.6},  # summer storm season
    ("storm", "NSW & ACT"): {10: 1.4, 11: 1.6, 12: 1.5, 1: 1.3},  # spring hail
    ("fire", "VIC & TAS"): {12: 1.4, 1: 1.7, 2: 1.6},  # bushfire season
    ("collision", "VIC & TAS"): {6: 1.15, 7: 1.2, 8: 1.15},  # wet winter roads
}

# Repair and labour costs are higher in some states and territories.
STATE_COST_FACTOR = {"NSW": 1.12, "VIC": 1.08, "ACT": 1.05, "NT": 1.15}

# Annual premium (AUD) before state adjustment and policy-level variation. Home premiums
# cover building and contents.
BASE_PREMIUM = {"motor": 1000, "home": 2400}
STATE_PREMIUM_FACTOR = {"NSW": 1.15, "QLD": 1.25, "NT": 1.4, "WA": 1.05}
EXCESSES = {"motor": (800, 1000), "home": (500, 1000)}

AGE_BANDS = ("18-24", "25-34", "35-44", "45-54", "55-64", "65+")
AGE_BAND_WEIGHTS = (0.08, 0.20, 0.20, 0.19, 0.17, 0.16)

# Share of claims closed without any payment (declined, withdrawn, below the excess).
CLOSED_WITHOUT_PAYMENT_RATE = 0.08

SHOP_NAME_SUFFIXES = ("Smash Repairs", "Panel & Paint", "Collision Repairs", "Body Works")

NOTE_TEMPLATES: dict[tuple[str, str], list[str]] = {
    ("motor", "collision"): [
        "Insured rear-ended at traffic lights. Front and rear bumper damage, car still driveable.",
        "Two-car collision at a roundabout. Other driver failed to give way per police report.",
        "Reversed into a bollard in a shopping centre car park. Tailgate and rear bumper damage.",
    ],
    ("motor", "glass"): [
        "Stone chip on the motorway spread into a long windscreen crack.",
        "Windscreen cracked by a falling branch during a storm.",
    ],
    ("motor", "storm"): [
        "Hail dents across bonnet, roof and boot. Photos attached.",
        "Storm damage to roof and windscreen while parked on the street.",
    ],
    ("motor", "theft"): [
        "Car stolen from the driveway overnight. Police report lodged.",
        "Car stolen from an apartment car park. Police report lodged.",
    ],
    ("motor", "third_party_property"): [
        "Insured at fault in a low-speed collision. Third party's car needs panel repairs.",
        "Insured's car rolled into a neighbour's fence. Fence repair quote submitted.",
    ],
    ("home", "water_damage"): [
        "Burst flexi hose under the kitchen sink. Water damage to floorboards and cabinets.",
        "Hot water system leak damaged the laundry and hallway flooring.",
        "Leaking shower recess caused water damage to the adjoining bedroom wall.",
    ],
    ("home", "storm"): [
        "Wind lifted roof tiles. Water stains on the ceiling in two bedrooms.",
        "Hail damage to roof and gutters. Inspection requested.",
    ],
    ("home", "fire"): [
        "Kitchen fire spread to cabinets and ceiling. Smoke damage throughout.",
        "Electrical fire in the garage. Contents and structure damaged.",
    ],
    ("home", "theft"): [
        "Break-in while on holidays. Electronics and jewellery taken.",
        "Bikes and tools stolen from the garden shed.",
    ],
    ("home", "liability"): [
        "Visitor slipped on wet front steps. Medical expenses claimed.",
        "Dog bite involving a neighbour. Medical bills submitted.",
    ],
}


def seasonal_factor(cause: str, region: str, month: int) -> float:
    return SEASONALITY.get((cause, region), {}).get(month, 1.0)
