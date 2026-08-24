"""User manager for registration and authentication."""

from __future__ import annotations

import uuid
from typing import override

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin

from tradenet_chat.auth.models import User


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    @override
    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        pass
