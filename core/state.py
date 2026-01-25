from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ChatState:
    history: List[Dict[str, str]] = field(default_factory=list)
    lang: str = "ar"
    last_intent: Optional[str] = None
    last_bot_reply: str = ""  # helps anti-repeat

    # ---- Context / follow-ups ----
    awaiting_location_city: bool = False
    awaiting_shipping_place: bool = False
    shipping_scope: Optional[str] = None  # "ksa" | "outside" | None

    # ---- Catalog state (for numbers / groups) ----
    view_mode: str = "none"  # "none" | "groups" | "items"
    last_groups: List[str] = field(default_factory=list)
    last_group_items: Dict[str, List[str]] = field(default_factory=dict)
    last_items: List[str] = field(default_factory=list)

    def push(self, role: str, content: str) -> None:
        if not content:
            return
        self.history.append({"role": role, "content": content})

    def reset(self) -> None:
        self.history.clear()
        self.last_intent = None
        self.last_bot_reply = ""
        self.lang = "ar"
        self.awaiting_location_city = False
        self.awaiting_shipping_place = False
        self.shipping_scope = None
        self.view_mode = "none"
        self.last_groups.clear()
        self.last_group_items.clear()
        self.last_items.clear()
