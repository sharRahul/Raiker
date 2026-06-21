from raiker.runtime.executors.base import Executor


class ExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, Executor] = {}

    def register(self, capability: str, executor: Executor) -> None:
        self._executors[capability] = executor

    def get(self, capability: str) -> Executor | None:
        return self._executors.get(capability)

    def has(self, capability: str) -> bool:
        return capability in self._executors