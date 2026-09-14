"""Entrypoint: клавіатура → MANUAL_CONTROL у SITL."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Callable, Mapping, Optional, Protocol

from .axes import DEFAULT_RATE, AxisState
from .keyboard import KeyboardSource
from .loop import DEFAULT_HZ, ManualControlSender, run_loop


class KeySource(Protocol):
    """Спільний мінімум `KeyboardSource`/`EvdevSource`, потрібний тут: не
    `start()` (той повертає різні конкретні типи в різних бекендах — виклик
    робимо одразу після конструювання, ще на конкретному типі)."""

    def snapshot(self) -> set[str]: ...

    def stop(self) -> None: ...


class NullManualControlSender:
    """`ManualControlSender`, що нічого нікуди не шле — для `--dry`, без SITL/MAVLink."""

    def manual_control_send(
        self, target: int, x: int, y: int, z: int, r: int, buttons: int
    ) -> None:
        pass


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
    parser.add_argument(
        "--input-backend",
        choices=["pynput", "evdev"],
        default="pynput",
        help="pynput — X11-сесія (Xorg); evdev — Linux, працює й на Wayland "
        "(потрібна група `input`)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="шлях до /dev/input/eventN для --input-backend evdev "
        "(за замовчуванням — автовизначення)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="друкувати щотакту розпізнані клавіші й значення осей "
        "(перевірити, чи взагалі доходять натискання)",
    )
    parser.add_argument(
        "--dry",
        action="store_true",
        help="без MAVLink/SITL — лише перевірити перехоплення клавіш і мапінг осей "
        "(увімкнено --connect ігнорується; --debug вмикається автоматично)",
    )
    return parser.parse_args(argv)


class TickPrinter:
    """Живий однорядковий дебаг-вивід, притримуваний за часом (не щотакту 20 Гц —
    інакше на терміналах, де `\\r` не перезаписує рядок (переносить), це виглядає
    як спам). `\\x1b[K` стирає залишок попереднього рядка, щоб не лишалось "хвостів"
    коли новий рядок коротший."""

    def __init__(
        self, min_interval_s: float = 0.1, now: Callable[[], float] = time.monotonic
    ) -> None:
        self._min_interval_s = min_interval_s
        self._now = now
        self._last_printed_at: Optional[float] = None

    def __call__(self, keys: set[str], values: Mapping[str, float]) -> None:
        moment = self._now()
        if self._last_printed_at is not None and moment - self._last_printed_at < self._min_interval_s:
            return
        self._last_printed_at = moment
        keys_label = " ".join(sorted(keys)) or "-"
        line = (
            f"keys={keys_label:<24} "
            f"pitch={values['pitch']:>5.0f} roll={values['roll']:>5.0f} "
            f"yaw={values['yaw']:>5.0f} throttle={values['throttle']:>5.0f}"
        )
        sys.stdout.write("\r\x1b[K" + line)
        sys.stdout.flush()


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    debug = args.debug or args.dry

    mav: ManualControlSender
    target = 0
    if args.dry:
        print("--dry: без SITL/MAVLink, лише перехоплення клавіш і мапінг осей")
        mav = NullManualControlSender()
    else:
        from pymavlink import mavutil  # локальний імпорт: тести не потребують pymavlink

        conn = mavutil.mavlink_connection(args.connect)
        conn.wait_heartbeat()
        print(f"heartbeat from system {conn.target_system} component {conn.target_component}")
        mav = conn.mav
        target = conn.target_system

    source: KeySource
    if args.input_backend == "evdev":
        from .evdev_source import EvdevSource

        source = EvdevSource(device_path=args.device)
        source.start()
    else:
        keyboard_source = KeyboardSource()
        keyboard_source.start()
        source = keyboard_source

    print("W/S pitch  A/D roll  Q/E yaw  Shift/Ctrl throttle   (Ctrl+C — вихід)")
    try:
        run_loop(
            mav,
            source.snapshot,
            SystemClock(),
            hz=args.hz,
            duration=args.duration,
            state=AxisState(rate=args.rate),
            target=target,
            on_tick=TickPrinter() if debug else None,
        )
    except KeyboardInterrupt:
        pass
    finally:
        source.stop()
        if debug:
            print()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
