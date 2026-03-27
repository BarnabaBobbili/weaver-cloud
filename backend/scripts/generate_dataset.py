"""
Dataset generator: creates ~2000 synthetic labeled samples for sensitivity classifier.
Run: python scripts/generate_dataset.py
Outputs: app/ml/models/dataset.csv
"""
from __future__ import annotations
import csv
import os
import random
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "ml", "models", "dataset.csv")


def gen_public(n: int = 500) -> list[tuple[str, str]]:
    samples = []
    templates = [
        lambda: f"{fake.company()} announces new partnership with {fake.company()} to expand market reach in {fake.country()}.",
        lambda: f"The annual report from {fake.year()} shows steady growth in the renewable energy sector.",
        lambda: f"Press release: {fake.name()} appointed as new CEO of {fake.company()}.",
        lambda: f"Breaking news: Scientists discover new species in the {fake.city()} region.",
        lambda: f"Event recap: {fake.company()} hosted their annual conference in {fake.city()} with over {random.randint(500,5000)} attendees.",
        lambda: (f"The city of {fake.city()} has announced plans for infrastructure development. "
                 f"The project, valued at ${random.randint(1,100)}M, will create {random.randint(100,5000)} jobs."),
        lambda: f"Product launch: {fake.company()} unveils new {fake.bs()} platform for enterprise customers.",
        lambda: f"FAQ: How to use our new dashboard? Click the menu icon and navigate to Settings.",
    ]
    for _ in range(n):
        text = random.choice(templates)()
        samples.append((text, "public"))
    return samples


def gen_internal(n: int = 500) -> list[tuple[str, str]]:
    samples = []
    templates = [
        lambda: (f"Team meeting notes - {fake.date_this_year()}: {fake.name()} discussed Q{random.randint(1,4)} roadmap. "
                 f"Action items assigned to {fake.name()} and {fake.name()}. Next meeting in 2 weeks."),
        lambda: (f"Internal memo: All employees must complete the mandatory security training by {fake.future_date()}. "
                 f"Contact {fake.name()} in HR for any issues."),
        lambda: (f"Project {fake.bs().title()} update: Phase 1 completed. "
                 f"Team velocity is {random.randint(20,60)} points/sprint. Budget utilization at {random.randint(40,90)}%."),
        lambda: (f"From: {fake.name()} <{fake.company_email()}>\n"
                 f"Subject: {fake.catch_phrase()}\n"
                 f"Please find attached the slides from our internal strategy session. "
                 f"This is for internal circulation only."),
        lambda: (f"Quarterly business review: {fake.company()} division achieved {random.randint(85,115)}% of target. "
                 f"Key risks identified: supply chain delays, hiring shortage."),
        lambda: (f"IT Notice: Scheduled maintenance on {fake.future_date()} from 2 AM to 4 AM. "
                 f"Services affected: email, VPN, internal wiki."),
    ]
    for _ in range(n):
        text = random.choice(templates)()
        samples.append((text, "internal"))
    return samples


def gen_confidential(n: int = 500) -> list[tuple[str, str]]:
    samples = []
    templates = [
        lambda: (f"Employee Performance Review - {fake.name()}\n"
                 f"Role: {fake.job()}\n"
                 f"Annual Salary: ${random.randint(50000,200000):,}\n"
                 f"Rating: {random.choice(['Exceeds Expectations','Meets Expectations','Needs Improvement'])}\n"
                 f"Bonus: ${random.randint(0,30000):,}"),
        lambda: (f"Contract Agreement between {fake.company()} and {fake.company()}.\n"
                 f"Contract value: ${random.randint(10000, 5000000):,}. "
                 f"Confidentiality clause: All terms are strictly confidential."),
        lambda: (f"Q{random.randint(1,4)} Financial Report - CONFIDENTIAL\n"
                 f"Revenue: ${random.randint(1,500)}M | EBITDA: {random.randint(10,40)}%\n"
                 f"Net profit: ${random.randint(1,100)}M. Not for external distribution."),
        lambda: (f"Legal notice from {fake.company()} to {fake.company()}.\n"
                 f"Re: Breach of Non-Disclosure Agreement dated {fake.past_date()}.\n"
                 f"Settlement amount: ${random.randint(10000,500000):,}."),
        lambda: (f"Merger & Acquisition analysis: Target company {fake.company()} valued at ${random.randint(10,500)}M. "
                 f"Due diligence findings enclosed. STRICTLY CONFIDENTIAL."),
        lambda: (f"Employee record: {fake.name()}, DOB: {fake.date_of_birth()}, "
                 f"Department: {fake.job()}, Hire date: {fake.past_date()}, "
                 f"Emergency contact: {fake.name()} — {fake.phone_number()}."),
    ]
    for _ in range(n):
        text = random.choice(templates)()
        samples.append((text, "confidential"))
    return samples


def gen_highly_sensitive(n: int = 500) -> list[tuple[str, str]]:
    samples = []
    templates = [
        lambda: (f"Patient Record - CONFIDENTIAL\n"
                 f"Name: {fake.name()}\n"
                 f"DOB: {fake.date_of_birth()}\n"
                 f"SSN: {fake.ssn()}\n"
                 f"Diagnosis: {random.choice(['Hypertension','Type 2 Diabetes','Cancer - Stage II','HIV positive'])}\n"
                 f"Medications: {fake.bs()}\n"
                 f"Insurance ID: {fake.bothify('??######')}"),
        lambda: (f"Credit Application\n"
                 f"Applicant: {fake.name()}\n"
                 f"SSN: {fake.ssn()}\n"
                 f"Credit Card: {fake.credit_card_number()}\n"
                 f"Expiry: {fake.credit_card_expire()}\n"
                 f"CVV: {fake.credit_card_security_code()}\n"
                 f"Annual Income: ${random.randint(30000,300000):,}"),
        lambda: (f"System credentials dump:\n"
                 f"admin_user: {fake.user_name()}\n"
                 f"password: {fake.password(length=16)}\n"
                 f"API_KEY: {fake.sha256()}\n"
                 f"DB_URL: postgresql://{fake.user_name()}:{fake.password()}@{fake.hostname()}/prod"),
        lambda: (f"Background check report for {fake.name()}\n"
                 f"SSN: {fake.ssn()}\n"
                 f"Date of Birth: {fake.date_of_birth()}\n"
                 f"Criminal record: {random.choice(['None','DUI 2019','Fraud 2018'])}\n"
                 f"Credit score: {random.randint(500,850)}"),
        lambda: (f"Wire transfer authorization\n"
                 f"From account: {fake.bban()}\n"
                 f"To account: {fake.bban()}\n"
                 f"Amount: ${random.randint(1000,1000000):,}\n"
                 f"Authorization code: {fake.bothify('AUTH-########')}\n"
                 f"Beneficiary SSN: {fake.ssn()}"),
        lambda: (f"Aadhaar verification record:\n"
                 f"Name: {fake.name()}\n"
                 f"Aadhaar: {fake.bothify('#### #### ####')}\n"
                 f"PAN: {fake.bothify('?????####?').upper()}\n"
                 f"DOB: {fake.date_of_birth()}\n"
                 f"Bank account: {fake.bban()}"),
    ]
    for _ in range(n):
        text = random.choice(templates)()
        samples.append((text, "highly_sensitive"))
    return samples


def generate():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    samples = gen_public() + gen_internal() + gen_confidential() + gen_highly_sensitive()
    random.shuffle(samples)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "label"])
        writer.writerows(samples)
    print(f"Dataset generated: {len(samples)} samples → {OUTPUT_PATH}")


if __name__ == "__main__":
    generate()
