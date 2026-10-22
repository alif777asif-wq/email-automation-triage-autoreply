"""formats-b: the held-out machine-mail format set, written after guard.py was frozen. See datagen_formats.py."""
from __future__ import annotations

from .datagen import OWN
from .datagen_formats import Ctx, Format


# ---------------------------------------------------------------- with a standard marker
def outlook_ooo_rule_headers(c: Ctx) -> bytes:
    n, first, a = c.person()
    return c.message(n, a, f"Out of Office AutoReply: {c.orig()}",
                     f"Hello,\n\nThank you for your message. I am currently out of the office and will return on {c.later()}. "
                     f"Your email has not been forwarded.\n\nRegards,\n{first}",
                     {"Auto-Submitted": "auto-replied", "X-MS-Exchange-Inbox-Rules-Loop": a})


def ci_failure_notice(c: Ctx) -> bytes:
    run = c.rng.randint(400, 9000)
    return c.message("CI", f"noreply@{c.host('ci')}", f"[widgets/api] Run failed: tests - main (#{run})",
                     f"Run #{run} failed on main ({c.rng.getrandbits(28):07x}).\n\nTests failed: {c.rng.randint(1, 9)}\n"
                     f"First failure: test_checkout_totals\n\nView the run in your browser to see the logs.\n")


def mailing_list_digest(c: Ctx) -> bytes:
    host = c.host("lists", "example.org")
    vol, issue = c.rng.randint(8, 30), c.rng.randint(1, 60)
    return c.message("dev list", f"dev-request@{host}", f"dev Digest, Vol {vol}, Issue {issue}",
                     f"Send dev mailing list submissions to dev@{host}\n\nToday's Topics:\n\n   1. Release schedule for 4.2 (Mateo Alvarez)\n"
                     "   2. Re: Release schedule for 4.2 (Priya Patel)\n   3. Docs sprint on Friday (Kenji Tanaka)\n",
                     {"List-Id": f"<dev.{host}>", "Precedence": "list", "X-Mailing-List": f"dev@{host}"})


def exim_failure_notice(c: Ctx) -> bytes:
    _, _, b = c.person()
    return c.raw(
        f"From: Mail Delivery System <Mailer-Daemon@{c.host('mail', 'example.net')}>\nTo: {OWN}\nSubject: Mail delivery failed: returning message to sender\n"
        f"Date: {c.date}\nMessage-ID: {c.mid()}\nMIME-Version: 1.0\n"
        "Content-Type: multipart/report; report-type=delivery-status; boundary=\"exim-b\"\n\n--exim-b\nContent-Type: text/plain; charset=us-ascii\n\n"
        "This message was created automatically by mail delivery software.\n\nA message that you sent could not be delivered to one or more of its\n"
        f"recipients. This is a permanent error. The following address(es) failed:\n\n  {b}\n    host mx.example.org [198.51.100.7]\n"
        f"    SMTP error from remote mail server after RCPT TO:<{b}>:\n    550 Unrouteable address\n\n"
        f"--exim-b\nContent-Type: message/delivery-status\n\nReporting-MTA: dns; mail.example.net\n\nFinal-Recipient: rfc822;{b}\nAction: failed\nStatus: 5.0.0\n\n--exim-b--\n")


def vendor_status_alert(c: Ctx) -> bytes:
    return c.message("Status", f"alerts@{c.host('status')}", "[Resolved] Elevated error rates on the API",
                     "Resolved - We have fixed the issue causing elevated error rates. All systems are operating normally.\n\n"
                     f"Posted at 09:{c.rng.randint(10, 59)} UTC. Subscribers receive an update when the status changes.\n",
                     {"Auto-Submitted": "auto-generated", "Precedence": "bulk"})


# ---------------------------------------------------------------- without a standard marker
def contact_form_thanks(c: Ctx) -> bytes:
    studio = c.rng.choice(["Brightside Studio", "Harbour & Pine", "Lumen Works", "Northgate Dental"])
    return c.message(studio, f"info@{c.host('studio')}", f"Thanks for contacting {studio}",
                     f"Hi there,\n\nThanks for getting in touch! We've received your message and will get back to you within 1-2 business days.\n\n"
                     f"The {studio} team\n")


def subscription_renewal_notice(c: Ctx) -> bytes:
    n, first, _ = c.person()
    day = c.later(2, 9)
    return c.message("Acme Cloud", f"billing@{c.host('acmecloud')}", f"Your subscription renews on {day}",
                     f"Hi {first},\n\nYour Acme Cloud Pro subscription will renew on {day} for ${c.rng.choice([9, 19, 29, 49, 99])}.00. "
                     "You can update your payment details or cancel any time from your account settings.\n\nThe Acme Cloud team\n")


def invoice_ready_notice(c: Ctx) -> bytes:
    return c.message("Fieldwork Accounting", f"billing@{c.host('fieldwork')}", f"Invoice 2026-{c.rng.randint(100, 999):04d} is ready",
                     f"Hello,\n\nYour invoice for October is ready to view in your account.\n\nTotal due: ${c.rng.randint(80, 2400)}.00\n"
                     f"Due date: {c.later(10, 25)}\n\nThanks for your business.\n")


def parcel_delivered_notice(c: Ctx) -> bytes:
    return c.message("Swiftpost", f"tracking@{c.host('swiftpost', 'example.net')}", "Delivered: your parcel from Acme",
                     f"Your parcel was delivered today at 14:{c.rng.randint(10, 59)} and left with a neighbour.\n\n"
                     f"Tracking number: SP{c.rng.randint(10**9, 10**10 - 1)}\nSigned for by: N. Neighbour\n")


def password_reset_email(c: Ctx) -> bytes:
    return c.message("Acme", f"support@{c.host('acme-app')}", "Reset your password",
                     "We got a request to reset your Acme password. Use the button below to choose a new one.\n\n"
                     "If you didn't ask for this, you can ignore this email and your password will stay the same.\n")


def feedback_survey(c: Ctx) -> bytes:
    return c.message("Acme Feedback", f"hello@{c.host('acme-fb')}", "How did we do?",
                     "Hi,\n\nYou recently contacted our support team. How would you rate your experience?\n\n"
                     "Great   |   Okay   |   Not good\n\nIt takes ten seconds and helps us improve.\n")


def out_of_country_notice(c: Ctx) -> bytes:
    n, first, a = c.person()
    colleague = c.rng.choice(FIRST_NAMES)
    return c.message(n, a, f"Re: {c.orig()}",
                     f"Hello,\n\nI'm out of the country until {c.later()} with no access to email. For urgent requests please contact "
                     f"{colleague} at {colleague.lower()}@example.com.\n\nThanks,\n{first}")


def promo_pricing_offer(c: Ctx) -> bytes:
    return c.message("Fable & Co", f"hello@{c.host('fableandco', 'example.org')}", "Annual plans: 20% off pricing this week",
                     "Hi,\n\nFor a few days only, save 20% on annual plans. See pricing and upgrade today.\n")


def chat_notification_notify(c: Ctx) -> bytes:
    n, first, _ = c.person()
    return c.message("TeamChat", f"notify@{c.host('teamchat')}", f"{n} sent you a message",
                     f"{first}: \"Any update on the export bug? Customers are asking.\"\n\nReply in TeamChat.\n")


FIRST_NAMES = ["Dana", "Marcus", "Ingrid", "Tobias", "Leona"]

FORMATS = [
    Format("outlook_ooo_rule_headers", "auto_reply", True, outlook_ooo_rule_headers),
    Format("ci_failure_notice", "bulk", True, ci_failure_notice),
    Format("mailing_list_digest", "bulk", True, mailing_list_digest),
    Format("exim_failure_notice", "bounce", True, exim_failure_notice),
    Format("vendor_status_alert", "bulk", True, vendor_status_alert),
    Format("contact_form_thanks", "auto_reply", False, contact_form_thanks),
    Format("subscription_renewal_notice", "bulk", False, subscription_renewal_notice),
    Format("invoice_ready_notice", "bulk", False, invoice_ready_notice),
    Format("parcel_delivered_notice", "bulk", False, parcel_delivered_notice),
    Format("password_reset_email", "bulk", False, password_reset_email),
    Format("feedback_survey", "bulk", False, feedback_survey),
    Format("out_of_country_notice", "auto_reply", False, out_of_country_notice),
    Format("promo_pricing_offer", "bulk", False, promo_pricing_offer),
    Format("chat_notification_notify", "bulk", False, chat_notification_notify),
]
