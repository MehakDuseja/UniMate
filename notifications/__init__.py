"""University update notification system."""

from notifications.job import run_notification_check
from notifications.subscription_service import (
    list_subscribers,
    list_subscribed_university_ids,
    remove_subscription,
    upsert_subscription,
)

__all__ = [
    "run_notification_check",
    "upsert_subscription",
    "remove_subscription",
    "list_subscribers",
    "list_subscribed_university_ids",
]
