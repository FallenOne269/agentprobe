"""
Observability hooks for agentprobe.

Hooks let you attach lightweight callbacks at key lifecycle points so you can
stream telemetry to any observability backend (logging, Prometheus,
OpenTelemetry, Datadog, etc.) without touching runner internals.

Example::

    from agentprobe import HookRegistry, HookEvent

    hooks = HookRegistry()

    @hooks.on(HookEvent.SCENARIO_END)
    def emit_metric(payload):
        name   = payload.data["scenario"].name
        passed = payload.data["result"].passed
        print(f"[metric] {name} passed={passed}")

    runner = Runner(backend=be, hooks=hooks)
    runner.run_directory("scenarios/")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class HookEvent(str, Enum):
    """Lifecycle events emitted by the Runner."""

    RUN_START = "run_start"
    """Fired before the first scenario executes.

    Payload keys:
        directory (str): path to the scenarios directory
        tag (str | None): active tag filter
    """

    RUN_END = "run_end"
    """Fired after all scenarios complete.

    Payload keys:
        run_result (RunResult): the final aggregated result
    """

    SCENARIO_START = "scenario_start"
    """Fired immediately before a scenario is executed.

    Payload keys:
        scenario (Scenario): the scenario about to run
    """

    SCENARIO_END = "scenario_end"
    """Fired immediately after a scenario is evaluated.

    Payload keys:
        scenario (Scenario): the scenario that ran
        result  (EvaluationResult): the evaluation outcome
    """


@dataclass
class EventPayload:
    """Container passed to every hook callback."""

    event: HookEvent
    data: dict[str, Any] = field(default_factory=dict)


HookCallback = Callable[[EventPayload], None]


class HookRegistry:
    """
    Registry for observability hook callbacks.

    Usage::

        registry = HookRegistry()

        # decorator style
        @registry.on(HookEvent.SCENARIO_END)
        def my_handler(payload):
            ...

        # imperative style
        registry.register(HookEvent.RUN_END, my_handler)

        runner = Runner(backend=..., hooks=registry)
    """

    def __init__(self) -> None:
        self._handlers: dict[HookEvent, list[HookCallback]] = {
            event: [] for event in HookEvent
        }

    def on(self, event: HookEvent) -> Callable[[HookCallback], HookCallback]:
        """Decorator: register *fn* as a handler for *event*."""

        def decorator(fn: HookCallback) -> HookCallback:
            self._handlers[event].append(fn)
            return fn

        return decorator

    def register(self, event: HookEvent, fn: HookCallback) -> None:
        """Register *fn* as a handler for *event* (imperative form)."""
        self._handlers[event].append(fn)

    def emit(self, event: HookEvent, **data: Any) -> None:
        """
        Fire all callbacks registered for *event*.

        Exceptions raised by individual handlers are logged and swallowed so
        that a bad hook can never crash a test run.
        """
        payload = EventPayload(event=event, data=data)
        for handler in self._handlers[event]:
            try:
                handler(payload)
            except Exception:
                logger.exception(
                    "Hook handler %r raised an exception for event %s",
                    handler,
                    event,
                )
