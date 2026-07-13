from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TaskItem:
    text: str
    done: bool = False


class TaskList:
    def __init__(self) -> None:
        self.items: list[TaskItem] = []

    def add(self, text: str, done: bool = False) -> None:
        clean = " ".join(text.strip().split())
        if not clean:
            return
        for item in self.items:
            if item.text.lower() == clean.lower():
                item.done = done
                return
        self.items.append(TaskItem(clean, done))

    def done(self, index: int) -> None:
        if index < 1 or index > len(self.items):
            raise ValueError("task not found")
        self.items[index - 1].done = True

    def clear(self) -> None:
        self.items.clear()

    def update_from_text(self, text: str) -> None:
        for done, task_text in _parse_checkboxes(text):
            self.add(task_text, done=done)

    def handle_command(self, command: str) -> str:
        lower = command.strip().lower()
        if lower in {"/task", "/tasks", "/task list", "/tasks list"}:
            return self.format()
        if lower in {"/task clear", "/tasks clear"}:
            self.clear()
            return "tasks cleared"
        if lower.startswith("/task add ") or lower.startswith("/tasks add "):
            _, _, text = command.partition(" add ")
            self.add(text)
            return "task added"
        if lower.startswith("/task done ") or lower.startswith("/tasks done "):
            _, _, value = command.partition(" done ")
            try:
                self.done(int(value.strip()))
            except ValueError:
                return "task not found"
            return "task done"
        return "usage: /task add <text> | /task done <n> | /task clear"

    def format(self) -> str:
        if not self.items:
            return "no tasks"
        lines = []
        for index, item in enumerate(self.items, start=1):
            marker = "x" if item.done else " "
            lines.append(f"{index}. [{marker}] {item.text}")
        return "\n".join(lines)


def _parse_checkboxes(text: str) -> list[tuple[bool, str]]:
    matches = re.findall(r"(?im)^\s*[-*]\s+\[([ xX])\]\s+(.+?)\s*$", text)
    return [(mark.lower() == "x", body.strip()) for mark, body in matches]


def has_visible_tasks(text: str) -> bool:
    clean = text.strip()
    return bool(clean and clean.lower() != "no tasks")
