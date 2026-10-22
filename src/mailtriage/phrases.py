"""Phrase banks used by the synthetic data generator.

POOL_A phrasings are used for the development set (rules were tuned against them).
POOL_B phrasings were written after the classifier rules were frozen and appear only
in the test set, so the test score measures generalisation to unseen wording.
"""

POOL_A = {
    "billing": {
        "subjects": [
            "Question about invoice {inv}",
            "Invoice {inv}: amount looks wrong",
            "Billing question",
            "Charged twice this month",
            "Need a copy of invoice {inv}",
            "VAT number missing on our invoice",
        ],
        "bodies": [
            "Hello,\n\nWe received invoice {inv} for ${amt}, but the total does not match our agreement. Could you check the charge and send a corrected invoice?",
            "Hi,\n\nMy card was charged ${amt} twice this month (invoice {inv}). Please look into the duplicate payment.",
            "Good morning,\n\nCould you resend invoice {inv}? Our accounting team cannot find it. The amount due is ${amt}.",
            "Hi there,\n\nThe VAT number is missing from invoice {inv} (${amt}). We need a corrected invoice for our records.",
        ],
    },
    "order_status": {
        "subjects": [
            "Where is my order {ord}?",
            "Order {ord} status",
            "Delivery update please",
            "Tracking number for {ord}",
            "Package has not arrived",
        ],
        "bodies": [
            "Hi,\n\nI placed order {ord} last week and the tracking page has not updated in five days. When will it be delivered?",
            "Hello,\n\nMy package for order {ord} still has not arrived. Could you send me the tracking number and an estimated delivery date?",
            "Hi team,\n\nCan you tell me the shipping status of order {ord}? It was supposed to ship on Monday.",
        ],
    },
    "tech_support": {
        "subjects": [
            "App keeps crashing on login",
            "Cannot sign in after the update",
            "Error when exporting a report",
            "Sync stopped working",
            "Bug: dashboard shows a blank page",
        ],
        "bodies": [
            "Hi,\n\nSince the latest update the app crashes every time I open the settings page. I reinstalled it but the error is still there. Version {ver}.",
            "Hello,\n\nI cannot sign in anymore. After entering my password I get an error message and the page reloads. Browser: {browser}.",
            "Hi support,\n\nExporting a report fails with an error and the download never starts. It worked fine last week. Version {ver}.",
            "Hello,\n\nSync stopped working on my phone and the dashboard shows a blank page. Restarting did not help.",
        ],
    },
    "sales_lead": {
        "subjects": [
            "Pricing for {n} seats",
            "Enterprise plan inquiry",
            "Request a demo",
            "Reseller partnership question",
            "Quote for an annual contract",
        ],
        "bodies": [
            "Hello,\n\nWe are evaluating tools for our team of {n} people and would like a quote and a short demo. Do you offer volume discounts?",
            "Hi,\n\nOur company is interested in the enterprise plan. Could you send pricing for {n} seats and details about annual contracts?",
            "Hello,\n\nWe run a small agency and would like to discuss becoming a reseller. Who should we talk to about partnership terms?",
        ],
    },
    "refund_request": {
        "subjects": [
            "Refund for order {ord}",
            "Please cancel and refund",
            "Return request for {ord}",
            "I want my money back",
        ],
        "bodies": [
            "Hi,\n\nI would like to return order {ord} and get a refund of ${amt}. The item arrived damaged.",
            "Hello,\n\nPlease cancel order {ord} and refund ${amt} to my original payment method. I changed my mind.",
            "Hi,\n\nThe product from order {ord} does not work as described. I want my money back (${amt}).",
        ],
    },
    "unsubscribe": {
        "subjects": [
            "Unsubscribe",
            "Remove me from your mailing list",
            "Please stop emailing me",
            "STOP",
        ],
        "bodies": [
            "Please remove me from your mailing list. I no longer want to receive promotional emails.",
            "Unsubscribe me from all marketing messages, please.",
            "Hello, please stop emailing me. I did not sign up for this newsletter.",
        ],
    },
}

# One short sentence per category that mentions another topic without changing the intent.
DISTRACTORS = {
    "billing": "My last invoice was fine, by the way.",
    "order_status": "My previous order arrived on time.",
    "tech_support": "The app also crashed once last month.",
    "sales_lead": "Also, what is the price of the premium plan?",
    "refund_request": "I may ask for a refund later if this is not resolved.",
    "unsubscribe": "I will unsubscribe from the newsletter if this continues.",
}

POOL_B = {
    "billing": {
        "subjects": ["Wrong amount on my statement", "Payment went through twice", "Can you send a receipt for {inv}",
                     "{inv} - question"],
        "bodies": [
            "Hey, I think there is a mistake on {inv}. I was billed ${amt} but our plan should cost less than that. Can someone take a look?",
            "Hi, I need an official receipt for my payment of ${amt} last month ({inv}) for my expense report. Thanks!",
            "Hello, the ${amt} payment went through twice on my bank statement ({inv}). Please fix it and confirm once done.",
        ],
    },
    "order_status": {
        "subjects": ["Still waiting on {ord}", "Has my parcel shipped yet?", "Late delivery", "Question on {ord}"],
        "bodies": [
            "Hi, it has been two weeks since I ordered ({ord}) and nothing has turned up. Could you let me know what is going on?",
            "Hello! Just checking whether my parcel has left your warehouse yet. Order {ord}. Thanks.",
            "Hi, the courier says a delivery was attempted but nobody came. Can you help me rebook? Order {ord}.",
        ],
    },
    "tech_support": {
        "subjects": ["Login loop", "Reports will not load", "Problem with the mobile app", "Everything is frozen"],
        "bodies": [
            "Hi, every time I try to log in it sends me straight back to the login page. Tried two browsers ({browser}). Help?",
            "Hello, the reports page just spins forever since yesterday. The console shows a 500 failure. Version {ver}.",
            "Hey, the mobile app freezes on the start screen after the latest release. Had to force quit three times.",
        ],
    },
    "sales_lead": {
        "subjects": ["Interested in your product", "Team plan cost?", "Can we get a walkthrough?", "Bulk licensing"],
        "bodies": [
            "Hi, we are a team of {n} and looking at your product for next quarter. What would the cost be, and could someone give us a walkthrough?",
            "Hello, do you have special rates for non-profits? We would need around {n} accounts.",
            "Hi there, I manage IT for a mid-size company. We would like to discuss licensing options for {n} users.",
        ],
    },
    "refund_request": {
        "subjects": ["Order {ord} - not what I expected", "Want to send this back", "Please reverse the payment"],
        "bodies": [
            "Hi, the item in {ord} is not what I expected and I would like to send it back for a full reimbursement of ${amt}.",
            "Hello, I would like my money returned for {ord} (${amt}). The product stopped working after two days.",
            "Hi, please reverse the ${amt} payment for {ord}. I no longer need it and have not opened the box.",
        ],
    },
    "unsubscribe": {
        "subjects": ["Take me off your list", "No more emails please", "Enough emails"],
        "bodies": [
            "Hi, please take me off your list. I get way too many emails from you.",
            "No more emails please. I never asked for these.",
            "Hello, I would like to opt out of all your messages. Thank you.",
        ],
    },
}
