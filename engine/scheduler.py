import os
import threading
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Callable

BASE_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def generate_schedule_no_delay(count: int) -> List[datetime]:
    """
    Generate immediate schedule: all emails as soon as possible.
    """
    now = datetime.now()
    return [now for _ in range(count)]

def generate_schedule_custom_delay(count: int, min_sec: float, max_sec: float) -> List[datetime]:
    """
    Generate a schedule with random delays between emails.
    """
    times = []
    current = datetime.now()
    for _ in range(count):
        delay = random.uniform(min_sec, max_sec)
        current += timedelta(seconds=delay)
        times.append(current)
    return times

def generate_schedule_batch(count: int, min_batch: int, max_batch: int,
                            min_delay: float, max_delay: float) -> List[datetime]:
    """
    Generate a batch send schedule: send random-sized batches, then wait random delay.
    """
    times = []
    current = datetime.now()
    remaining = count
    while remaining > 0:
        batch_size = random.randint(min_batch, max_batch)
        to_send = min(batch_size, remaining)
        for _ in range(to_send):
            times.append(current)
        remaining -= to_send
        if remaining > 0:
            delay = random.uniform(min_delay, max_delay)
            current += timedelta(seconds=delay)
    return times

def generate_schedule_spike(day_counts: List[int],
                            start_date: datetime = None) -> List[datetime]:
    """
    Generate a schedule for spike mode across multiple days.
    day_counts: list of email counts per day
    start_date: date to start (default now)
    """
    if start_date is None:
        start_date = datetime.now()
    schedule: List[datetime] = []
    for day_index, count in enumerate(day_counts):
        day_start = (start_date + timedelta(days=day_index)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_day = 24 * 3600
        daily_times = sorted(
            day_start + timedelta(seconds=random.uniform(0, seconds_day))
            for _ in range(count)
        )
        schedule.extend(daily_times)
    return schedule

class CampaignScheduler:
    """
    Schedules and runs send tasks based on a list of datetime send_times.
    """

    def __init__(self,
                 send_func: Callable[[Dict[str, Any]], None],
                 tasks: List[Dict[str, Any]]):
        """
        send_func: function to call for each send, signature send_func(task_args)
        tasks: list of dicts with keys:
            - send_time: datetime when to send
            - args: dict of arguments for send_func
        """
        self.timers: List[threading.Timer] = []
        now = datetime.now()
        for task in tasks:
            send_time = task['send_time']
            args = task['args']
            delay = (send_time - now).total_seconds()
            if delay < 0:
                continue
            timer = threading.Timer(delay, send_func, args=(args,))
            self.timers.append(timer)

    def start(self):
        """Start all scheduled send timers."""
        for t in self.timers:
            t.start()

    def cancel(self):
        """Cancel all pending send timers."""
        for t in self.timers:
            t.cancel()
