"""formats-c: the held-out set for roles.py, written after roles.py was frozen. See datagen_formats.py."""
from __future__ import annotations

from .datagen import OWN
from .datagen_formats import Ctx, Format


# ---------------------------------------------------------------- with a standard marker
def precedence_auto_reply_ooo(c: Ctx) -> bytes:
    n, first, a = c.person()
    return c.message(n, a, f"AUTO: {c.orig()} (Out of Office)",
                     f"I will be out of the office from {c.later(1, 4)} to {c.later(8, 14)} and will reply to your message after I return.\n\n{n}",
                     {"Precedence": "auto_reply"})


def repository_notification(c: Ctx) -> bytes:
    n, first, _ = c.person()
    num = c.rng.randint(100, 4000)
    return c.message("octo-bot", f"noreply@{c.host('code')}", f"Re: [widgets/api] Fix rounding in checkout totals (#{num})",
                     f"{n} commented on this pull request.\n\n> Looks good to me, merging after CI passes.\n\n"
                     f"Reply to this email directly or view it on the site.\n")


def marketing_from_a_person_with_list_headers(c: Ctx) -> bytes:
    n, first, _ = c.person()
    host = c.host("brightside", "example.org")
    return c.message(f"{first} at Brightside", f"{c.first_slug}@{host}", "Three things we shipped this month",
                     f"Hi,\n\nHere is what is new at Brightside this month: faster exports, a calmer inbox view and two new integrations.\n\n"
                     f"{first}\n",
                     {"List-Unsubscribe": f"<https://{host}/unsubscribe/xyz>"})


def qmail_failure_notice(c: Ctx) -> bytes:
    _, _, b = c.person()
    return c.raw(
        f"From: MAILER-DAEMON@{c.host('qmail', 'example.net')}\nTo: {OWN}\nSubject: failure notice\nDate: {c.date}\nMessage-ID: {c.mid()}\nReturn-Path: <>\n"
        "MIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\n\n"
        "Hi. This is the qmail-send program at mail.example.net.\nI'm afraid I wasn't able to deliver your message to the following addresses.\n"
        f"This is a permanent error; I've given up. Sorry it didn't work out.\n\n<{b}>:\nSorry, no mailbox here by that name. (#5.1.1)\n")


def calendar_reminder_noreply(c: Ctx) -> bytes:
    return c.message("Calendar", f"noreply-calendar@{c.host('cal')}", "Reminder: Weekly sync @ Tue 10:00",
                     "Weekly sync\nTuesday 10:00 - 10:30 (GMT)\nJoining info: video call link in the invitation\n\n"
                     "You are receiving this email because you are an attendee of this event.\n")


# ---------------------------------------------------------------- without a standard marker
def founder_welcome_drip(c: Ctx) -> bytes:
    n, first, _ = c.person()
    return c.message(f"{first} from Acme", f"{c.first_slug}@{c.host('acme')}", "Welcome to Acme - quick question",
                     f"Hi,\n\nI'm {first}, one of the founders. Thanks for signing up! What are you hoping to use Acme for?\n\n"
                     f"Just hit reply, I read every response.\n\n{first}\n")


def delivery_exception_carrier(c: Ctx) -> bytes:
    return c.message("Parcelhub", f"delivery@{c.host('parcelhub', 'example.net')}", "We missed you: delivery attempt unsuccessful",
                     f"We tried to deliver your parcel today but no one was available.\n\nReference: PH{c.rng.randint(10**8, 10**9 - 1)}\n"
                     f"We will try again on {c.later(1, 3)}, or you can collect it from your local depot.\n")


def refund_processed_notice(c: Ctx) -> bytes:
    return c.message("Larkspur Store", f"store@{c.host('larkspur', 'example.org')}", "Your refund has been processed",
                     f"Hello,\n\nWe have processed your refund of ${c.rng.randint(12, 380)}.{c.rng.randint(0, 99):02d}. "
                     "It can take 5-10 business days to appear on your statement.\n\nThanks for shopping with us.\n")


def bank_alert(c: Ctx) -> bytes:
    return c.message("Northfield Bank", f"alerts@{c.host('northfield', 'example.net')}", "Card purchase alert",
                     f"A purchase of ${c.rng.randint(5, 250)}.{c.rng.randint(0, 99):02d} was made with your card ending 4242 at Copperline Supply.\n\n"
                     "If this was not you, call the number on the back of your card.\n")


def ooo_offline_personal(c: Ctx) -> bytes:
    n, first, a = c.person()
    return c.message(n, a, f"Re: {c.orig()}",
                     f"Thanks for your note! I'm offline this week and back on {c.later(5, 9, '%A %d %B')}. I'll catch up with everything then.\n\n{first}")


def ooo_travelling_personal(c: Ctx) -> bytes:
    n, first, a = c.person()
    colleague = c.rng.choice(["Dana", "Marcus", "Ingrid", "Tobias", "Leona"])
    return c.message(n, a, f"Re: {c.orig()}",
                     f"Hi, I'm travelling for work and will be slow to reply until {c.later(4, 10)}. "
                     f"If it can't wait, please ping {colleague} ({colleague.lower()}@example.com).\n\n{first}")


def appointment_reminder(c: Ctx) -> bytes:
    return c.message("Harbour Dental", f"reception@{c.host('harbourdental')}", "Reminder: your appointment on Tuesday",
                     f"Hello,\n\nThis is a reminder of your appointment on Tuesday {c.later(2, 6, '%d %B')} at {c.rng.choice(['09:30', '10:30', '14:00', '16:15'])}.\n\n"
                     "Reply YES to confirm or call us to reschedule.\n")


def order_confirmation_shop(c: Ctx) -> bytes:
    return c.message("Birchwood Shop", f"shop@{c.host('birchwood', 'example.org')}", f"Thanks for your order #{c.rng.randint(10000, 99999)}",
                     f"Hi,\n\nThanks for your order! We're getting it ready now.\n\nEstimated delivery: {c.later(3, 7)}\n"
                     "You'll get another email when it ships.\n")


def pricing_change_from_a_person(c: Ctx) -> bytes:
    n, first, _ = c.person()
    return c.message(f"{first} at Larkspur", f"{c.first_slug}@{c.host('larkspur-app')}", "Our pricing is changing on 1 June",
                     "Hi,\n\nFrom 1 June our plans change. Existing customers keep their current pricing for twelve months, and annual plans "
                     f"stay 20% cheaper than monthly.\n\nQuestions? Just reply.\n\n{first}\n")


FORMATS = [
    Format("precedence_auto_reply_ooo", "auto_reply", True, precedence_auto_reply_ooo),
    Format("repository_notification", "bulk", True, repository_notification),
    Format("marketing_from_a_person_with_list_headers", "bulk", True, marketing_from_a_person_with_list_headers),
    Format("qmail_failure_notice", "bounce", True, qmail_failure_notice),
    Format("calendar_reminder_noreply", "bulk", True, calendar_reminder_noreply),
    Format("founder_welcome_drip", "bulk", False, founder_welcome_drip),
    Format("delivery_exception_carrier", "bulk", False, delivery_exception_carrier),
    Format("refund_processed_notice", "bulk", False, refund_processed_notice),
    Format("bank_alert", "bulk", False, bank_alert),
    Format("ooo_offline_personal", "auto_reply", False, ooo_offline_personal),
    Format("ooo_travelling_personal", "auto_reply", False, ooo_travelling_personal),
    Format("appointment_reminder", "bulk", False, appointment_reminder),
    Format("order_confirmation_shop", "bulk", False, order_confirmation_shop),
    Format("pricing_change_from_a_person", "bulk", False, pricing_change_from_a_person),
]
