"""Entrypoint: клавіатура → MANUAL_CONTROL у SITL."""

from __future__ import annotations

import argparse
import time
from typing import Optional

from .axes import DEFAULT_RATE, AxisState
from .keyboard import KeyboardSource
from .loop import DEFAULT_HZ, ManualControlSender, run_loop


class SystemClock:
    """Реалізація протоколу `loop.Clock` на системному годиннику."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="keyboard-adapter")
    parser.add_argument("--connect", default="udp:127.0.0.1:14550", help="MAVLink endpoint")
    parser.add_argument("--hz", type=float, default=DEFAULT_HZ)
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE, help="одиниць/с")
    parser.add_argument("--duration", type=float, default=None, help="секунд (за замовчуванням — до Ctrl+C)")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    from pymavlink import mavutil  # локальний імпорт: тести не потребують pymavlink

    conn = mavutil.mavlink_connection(args.connect)
    conn.wait_heartbeat()
    print(f"heartbeat from system {conn.target_system} component {conn.target_component}")

    source = KeyboardSource().start()
    print("W/S pitch  A/D roll  Q/E yaw  Shift/Ctrl throttle   (Ctrl+C — вихід)")
    try:
        mav: ManualControlSender = conn.mav
        run_loop(
            mav,
            source.snapshot,
            SystemClock(),
            hz=args.hz,
            duration=args.duration,
            state=AxisState(rate=args.rate),
            target=conn.target_system,
        )
    except KeyboardInterrupt:
        pass
    finally:
        source.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
