"""formats-a: the first machine-mail format set (the development set of guard.py). See datagen_formats.py."""
from __future__ import annotations

from .datagen import OWN
from .datagen_formats import Ctx, Format


def gmail_vacation_responder(c: Ctx) -> bytes:
    n, first, a = c.person()
    return c.message(n, a, f"Re: {c.orig()}",
                     f"Hi,\n\nThanks for your email. I'm on vacation until {c.later()} and will have limited access to email. "
                     f"I'll get back to you as soon as I can.\n\nBest,\n{first}",
                     {"Auto-Submitted": "auto-replied", **({"Precedence": "bulk"} if c.rng.random() < .4 else {})})


def exchange_automatic_reply(c: Ctx) -> bytes:
    n, _, a = c.person()
    return c.message(n, a, f"Automatic reply: {c.orig()}",
                     f"I am away from the office until {c.later()} and checking email only occasionally. "
                     f"For anything urgent please call the front desk.\n\n{n}",
                     {"Auto-Submitted": "auto-replied", "Content-Language": "en-US"})


def leave_notice_headers_stripped(c: Ctx) -> bytes:
    n, _, a = c.person()
    return c.message(n, a, f"Re: {c.orig()}",
                     f"Thank you for your email. I am on annual leave until {c.later()} and will respond when I return. "
                     f"If your matter is urgent, please contact my colleague at team@example.com.\n\nKind regards,\n{n}")


def helpdesk_confirmation_headers(c: Ctx) -> bytes:
    return c.message("Northwind Support", f"help@{c.host('desk')}", f"[Ticket #{c.rng.randint(10000, 99999)}] We received your request",
                     "Hello,\n\nThis is an automatic confirmation that we have received your email. A support agent will respond shortly.\n\n"
                     "Please do not add new requests to this ticket.\n",
                     {"Auto-Submitted": "auto-generated", "X-Auto-Response-Suppress": "All"})


def helpdesk_confirmation_stripped(c: Ctx) -> bytes:
    return c.message("Northwind Support", f"help@{c.host('desk')}", f"[Ticket #{c.rng.randint(10000, 99999)}] We received your request",
                     "Hello,\n\nThis is an automatic confirmation that we have received your email. A support agent will respond shortly.\n")


def exchange_ndr(c: Ctx) -> bytes:
    _, _, b = c.person()
    return c.raw(
        f"From: Microsoft Outlook <postmaster@{c.host('contoso-mail')}>\nTo: {OWN}\nSubject: Undeliverable: {c.orig()}\nDate: {c.date}\n"
        f"Message-ID: {c.mid()}\nX-MS-Exchange-Message-Is-Ndr:\nMIME-Version: 1.0\n"
        "Content-Type: multipart/report; report-type=delivery-status; boundary=\"b1\"\n\n--b1\nContent-Type: text/plain; charset=utf-8\n\n"
        f"Delivery has failed to these recipients or groups:\n\n{b}\nThe email address you entered couldn't be found. "
        "Please check the recipient's email address and try to resend the message.\n\n"
        f"--b1\nContent-Type: message/delivery-status\n\nReporting-MTA: dns;mail.example.com\n\nFinal-Recipient: rfc822;{b}\nAction: failed\nStatus: 5.1.10\n\n--b1--\n")


def gmail_failure_notice(c: Ctx) -> bytes:
    _, _, b = c.person()
    return c.raw(
        f"From: Mail Delivery Subsystem <mailer-daemon@{c.host('googlemail')}>\nTo: {OWN}\nSubject: Delivery Status Notification (Failure)\nDate: {c.date}\n"
        f"Message-ID: {c.mid()}\nMIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\n\n"
        f"** Address not found **\n\nYour message wasn't delivered to {b} because the address couldn't be found, or is unable to receive mail.\n\n"
        "The response was:\n550 5.1.1 The email account that you tried to reach does not exist.\n")


def gmail_delay_notice(c: Ctx) -> bytes:
    _, _, b = c.person()
    return c.raw(
        f"From: Mail Delivery Subsystem <mailer-daemon@{c.host('googlemail')}>\nTo: {OWN}\nSubject: Delivery Status Notification (Delay)\nDate: {c.date}\n"
        f"Message-ID: {c.mid()}\nMIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\n\n"
        f"** Delivery incomplete **\n\nThere was a temporary problem delivering your message to {b}. Gmail will retry for 47 more hours. "
        "You'll be notified if the delivery fails permanently.\n")


def security_gateway_rejection(c: Ctx) -> bytes:
    _, _, b = c.person()
    return c.message("Mail Administrator", f"bounce-handler@{c.host('secure-mail', 'example.net')}", "Message blocked: recipient policy",
                     f"Your message to {b} was blocked by the recipient's email security policy.\nReference: {c.rng.getrandbits(32):08X}\n")


def newsletter_list_headers(c: Ctx) -> bytes:
    host = c.host("widgetweekly", "example.org")
    return c.message("Widget Weekly", f"editor@{host}", c.rng.choice(["This week in widgets", "Five tips for faster shipping"]),
                     "Five tips for faster shipping.\n\nRead more on our site.\n\nTo stop receiving these emails, use the link below.\n",
                     {"List-Id": f"<weekly.{host}>", "List-Unsubscribe": f"<https://{host}/u/abc>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})


def saas_notification(c: Ctx) -> bytes:
    n, first, _ = c.person()
    return c.message("Boards", f"notifications@{c.host('boards')}", f"{first} commented on \"Q3 launch checklist\"",
                     f"{n} wrote:\n\"Can someone confirm the export is working before Friday?\"\n\nOpen the card to reply.\n")


def payment_receipt(c: Ctx) -> bytes:
    return c.message("Acme Payments", f"receipts@{c.host('pay')}", f"Your receipt from Acme #{c.rng.randint(1000, 9999)}",
                     f"Receipt from Acme\n\nAmount paid: ${c.rng.randint(9, 400)}.00\nPayment method: card ending 4242\n"
                     f"Invoice INV-2026-{c.rng.randint(1, 9999):04d}\n\nThank you for your payment.\n")


def sign_in_code(c: Ctx) -> bytes:
    return c.message("Acme Security", f"security@{c.host('accounts')}", f"Your sign-in code is {c.rng.randint(100000, 999999)}",
                     "Use this code to sign in. It expires in 10 minutes.\n\nIf you didn't request this code, you can safely ignore this email.\n")


def shipping_notification(c: Ctx) -> bytes:
    return c.message("Acme Orders", f"orders@{c.host('store')}", f"Your order ORD-{c.rng.randint(10000, 99999)} has shipped",
                     f"Good news! Your package is on its way.\n\nTracking number: 1Z{c.rng.getrandbits(40):010X}\nEstimated delivery: {c.later()}\n")


FORMATS = [
    Format("gmail_vacation_responder", "auto_reply", True, gmail_vacation_responder),
    Format("exchange_automatic_reply", "auto_reply", True, exchange_automatic_reply),
    Format("leave_notice_headers_stripped", "auto_reply", False, leave_notice_headers_stripped),
    Format("helpdesk_confirmation_headers", "auto_reply", True, helpdesk_confirmation_headers),
    Format("helpdesk_confirmation_stripped", "auto_reply", False, helpdesk_confirmation_stripped),
    Format("exchange_ndr", "bounce", True, exchange_ndr),
    Format("gmail_failure_notice", "bounce", True, gmail_failure_notice),
    Format("gmail_delay_notice", "bounce", True, gmail_delay_notice),
    Format("security_gateway_rejection", "bounce", True, security_gateway_rejection),
    Format("newsletter_list_headers", "bulk", True, newsletter_list_headers),
    Format("saas_notification", "bulk", True, saas_notification),
    Format("payment_receipt", "bulk", False, payment_receipt),
    Format("sign_in_code", "bulk", False, sign_in_code),
    Format("shipping_notification", "bulk", False, shipping_notification),
]
