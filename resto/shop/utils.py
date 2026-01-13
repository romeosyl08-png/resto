from datetime import time, timedelta

OPEN_TIME = time(18, 00)
CUTOFF_TIME = time(9, 30)

def is_order_window_open(now_time: time) -> bool:
    # ouvert de 18:00 → 23:59 et de 00:00 → 09:29
    print("CHECK:", now_time, "OPEN:", OPEN_TIME, "CUTOFF:", CUTOFF_TIME)
    return (now_time >= OPEN_TIME) or (now_time < CUTOFF_TIME)

def service_date(now_dt):
    # après 18h → menu du lendemain
    return (now_dt.date() + timedelta(days=1)) if now_dt.time() >= OPEN_TIME else now_dt.date()


