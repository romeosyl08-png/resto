from .utils import OPEN_TIME, OrderPhase


ORDER_PHASE_UI = {
    OrderPhase.INACTIVE: {
        "badge": "INDISPONIBLE",
        "badge_class": "badge-danger",
        "message": "Indisponible",
        "can_order": False,
    },
    OrderPhase.SOLDOUT: {
        "badge": "RUPTURE",
        "badge_class": "badge-danger",
        "message": "Rupture de stock",
        "can_order": False,
    },
    OrderPhase.PREOPEN: {
        "badge": "BIENTÔT",
        "badge_class": "badge-warning",
        "message": f"Ouverture à {OPEN_TIME.strftime('%H:%M')}",
        "can_order": False,
    },
    OrderPhase.CLOSED: {
        "badge": "FERMÉ",
        "badge_class": "badge-primary",
        "message": "Commandes fermées",
        "can_order": False,
    },
    OrderPhase.OPEN: {
        "badge": None,
        "badge_class": None,
        "message": None,
        "can_order": True,
    },
}
