import math
import re

from agentkit_mini import embed

# 50 FAQs from a small online shop: (id, question, answer)
FAQS = [
    ("refund-window", "Can I get a refund?", "Refunds are available within 30 days of delivery for unused items."),
    ("refund-time", "How long does a refund take to process?", "Refunds reach your card 5 to 10 business days after we receive the return."),
    ("refund-gift", "Can I return a gift?", "Gift returns get store credit, not cash, sent to the person who received it."),
    ("return-label", "Do you provide a return label?", "Yes. Print a prepaid return label from the Orders page."),
    ("return-sale", "Can I return sale items?", "Items bought on clearance are final sale and cannot be returned."),
    ("exchange", "Can I exchange an item for a different size?", "Yes. Start an exchange from the Orders page and we ship the new size free."),
    ("cancel-order", "How do I cancel an order?", "Orders can be cancelled within 1 hour of purchase from the Orders page."),
    ("cancel-sub", "How do I cancel my subscription?", "Go to Account, then Plan, then Cancel plan. You keep access until the period ends."),
    ("pause-sub", "Can I pause my subscription?", "You can pause a plan for up to 3 months from Account, then Plan."),
    ("delete-account", "How do I delete my account?", "Email privacy@shop.example and we delete your data within 30 days."),
    ("password-reset", "I forgot my password", "Use Forgot password on the login page and we email you a reset link."),
    ("2fa", "How do I turn on two-factor authentication?", "Open Account, then Security, and scan the QR code with an authenticator app."),
    ("locked", "Why is my account locked?", "After 5 failed login attempts the account locks for 15 minutes."),
    ("change-email", "How do I change my email address?", "Open Account, then Profile, and confirm the new address from your inbox."),
    ("shipping-time", "How long does shipping take?", "Standard delivery takes 3 to 5 business days. Express takes 1 to 2."),
    ("shipping-cost", "How much is shipping?", "Shipping is free over $50. Under $50 the fee is $4.99."),
    ("intl-shipping", "Do you ship internationally?", "We ship to 30 countries. Duties are paid by the customer at delivery."),
    ("track-order", "How can I track my order?", "Use the tracking link in your confirmation email or the Orders page."),
    ("lost-package", "My package is lost", "If tracking shows no movement for 7 days, contact us and we reship it."),
    ("wrong-address", "I entered the wrong address", "Contact us within 1 hour of ordering and we can update the address."),
    ("damaged-item", "What if my item arrives broken?", "Send a photo within 14 days and we replace defective items at no cost."),
    ("warranty", "Do products have a warranty?", "Electronics carry a 1-year warranty against manufacturing faults."),
    ("missing-part", "A part is missing from my box", "Tell us which part is missing and we post it within 2 business days."),
    ("double-charge", "Why was I charged twice?", "A pending authorization can look like a second charge. It drops off in 3 days."),
    ("payment-methods", "Which payment methods do you accept?", "We accept Visa, Mastercard, Amex, PayPal and Apple Pay."),
    ("invoice", "Can I get an invoice for my purchase?", "Download a PDF invoice from the Orders page."),
    ("price-match", "Do you price match?", "We match a lower price from a major retailer within 7 days of purchase."),
    ("promo-code", "My promo code does not work", "Codes are case sensitive, expire, and cannot be combined with sale prices."),
    ("tax", "Is sales tax included in the price?", "Tax is added at checkout based on the delivery address."),
    ("sub-price", "How much does the subscription cost?", "The plan costs $9 a month or $90 a year."),
    ("student", "Do you offer a student discount?", "Students get 15% off after verifying with a school email."),
    ("gift-card", "Do you sell gift cards?", "Digital gift cards from $10 to $500 are delivered by email."),
    ("gift-balance", "How do I check my gift card balance?", "Enter the card number on the Gift cards page to see the balance."),
    ("loyalty", "How does the rewards program work?", "Earn 1 point per dollar. 100 points is a $5 reward."),
    ("store-hours", "What are your store hours?", "Stores open 9am to 8pm Monday to Saturday and 10am to 6pm Sunday."),
    ("store-pickup", "Can I pick up my order in store?", "Choose Pickup at checkout. Orders are ready in about 2 hours."),
    ("contact", "How do I contact customer support?", "Chat with us 8am to 10pm, or email help@shop.example."),
    ("phone", "Do you have a phone number?", "Call 1-800-555-0100, Monday to Friday, 9am to 5pm."),
    ("size-guide", "How do I find my size?", "Each product page has a size chart with measurements in cm and inches."),
    ("restock", "When will an out of stock item be back?", "Click Notify me on the product page and we email you when it is restocked."),
    ("preorder", "Can I preorder upcoming products?", "Preorders charge your card when the item ships, not when you order."),
    ("bulk", "Do you offer bulk or wholesale orders?", "Orders of 50 units or more get volume pricing. Email sales@shop.example."),
    ("care", "How should I wash my jacket?", "Machine wash cold, hang dry, and do not iron the print."),
    ("materials", "Are your products sustainable?", "80% of our cotton is organic and our packaging is recyclable."),
    ("allergy", "Do your candles contain allergens?", "Ingredients are listed on each product page, including fragrance oils."),
    ("assembly", "Does furniture come assembled?", "Most furniture ships flat packed with tools and step-by-step instructions."),
    ("app", "Do you have a mobile app?", "Yes, on iOS and Android. Search for Shop Example."),
    ("newsletter", "How do I unsubscribe from emails?", "Click Unsubscribe at the bottom of any marketing email."),
    ("privacy", "Do you sell my data?", "No. We never sell personal data. See our privacy policy."),
    ("careers", "Are you hiring?", "Open roles are listed on our careers page."),
]

# Real customer wording, and the FAQ that answers it.
TESTS = [
    ("i can't log in", "password-reset"),
    ("the lamp arrived faulty", "damaged-item"),
    ("terminate membership", "cancel-sub"),
    ("reimbursed how fast", "refund-time"),
    ("price of the monthly plan", "sub-price"),
    ("billed twice this month", "double-charge"),
    ("package never arrived", "lost-package"),
    ("i want my money back", "refund-window"),
]

STOP = {"the", "a", "an", "is", "are", "to", "of", "and", "or", "i", "my", "how", "do", "can", "what", "for", "in", "on", "it", "me"}


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP}


def keyword_search(query, k=3):
    """Baseline: rank FAQs by how many words they share with the query."""
    q = words(query)
    scored = [(len(q & words(question + " " + answer)), fid) for fid, question, answer in FAQS]
    scored.sort(key=lambda x: -x[0])
    return [fid for score, fid in scored[:k] if score > 0]


def cosine(a, b):
    """Cosine similarity: the dot product divided by the product of the lengths."""
    # TODO: dot = sum of a[i] * b[i]; length = sqrt of the sum of squares.
    # Return dot / (length(a) * length(b)), or 0.0 if either length is 0.
    return 0.0


def build_index(faqs):
    """Embed each FAQ once (question and answer together). Returns a list of (id, vector)."""
    # TODO: for each (fid, question, answer), call embed(question + " " + answer)
    # and collect (fid, vector).
    return []


def semantic_search(query, index, k=3):
    """Embed the query and return the ids of the k most similar FAQs, best first."""
    # TODO: embed the query, score every (fid, vector) in the index with cosine,
    # sort highest first, and return the first k ids.
    return []


def hit_rate(search):
    """Share of test queries whose right FAQ is in the top 3."""
    return sum(1 for query, want in TESTS if want in search(query)) / len(TESTS)


index = build_index(FAQS)
print(f"Indexed {len(index)} FAQs" + (f", {len(index[0][1])} numbers each." if index else "."))
for query, want in TESTS:
    kw_ok = "hit " if want in keyword_search(query) else "miss"
    sem_ok = "hit " if want in semantic_search(query, index) else "miss"
    print(f"{query!r:30} keyword {kw_ok}  semantic {sem_ok}  (want {want})")
kw = hit_rate(keyword_search)
sem = hit_rate(lambda q: semantic_search(q, index))
print(f"\nHit rate in top 3: keyword {kw:.0%}, semantic {sem:.0%}")
