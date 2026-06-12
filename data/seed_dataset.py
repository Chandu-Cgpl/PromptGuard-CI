import json
import os

test_cases = [
    # --- BILLING (13 cases) ---
    {
        "id": "case_bill_001",
        "input": "Hello, I noticed a double charge of $29 on my bank statement from your service this morning. Can you please check and refund the second charge?",
        "expected_category": "billing",
        "expected_summary": "Customer requests a refund for a duplicate charge of $29.",
        "expected_difficulty": "easy",
        "notes": "Standard double charge refund query."
    },
    {
        "id": "case_bill_002",
        "input": "Where can I download the PDF invoice for my payment on June 1st? I need it for my company expense report.",
        "expected_category": "billing",
        "expected_summary": "Customer requests download access for their PDF invoice.",
        "expected_difficulty": "easy",
        "notes": "Standard invoice retrieval request."
    },
    {
        "id": "case_bill_003",
        "input": "I am trying to update my credit card details on the billing page but it keeps telling me 'card declined' even though there are sufficient funds.",
        "expected_category": "billing",
        "expected_summary": "Customer encounters 'card declined' error when updating credit card details.",
        "expected_difficulty": "medium",
        "notes": "Payment card update failure. Contains 'card declined' trigger words."
    },
    {
        "id": "case_bill_004",
        "input": "Oh fantastic, I just love getting double billed for a service I cancelled last month. Truly outstanding customer care. Refund my money now.",
        "expected_category": "billing",
        "expected_summary": "Customer sarcastically reports a double charge after cancellation and demands a refund.",
        "expected_difficulty": "hard",
        "notes": "Sarcastic tone and cancellation mentioned. Tests if LLM captures the primary billing issue."
    },
    {
        "id": "case_bill_005",
        "input": "Hola! He recibido una factura de $49 pero no sé por qué. I thought I was on the free trial. Can you check my account?",
        "expected_category": "billing",
        "expected_summary": "Customer inquires in mixed languages about an unexpected $49 invoice during a free trial.",
        "expected_difficulty": "hard",
        "notes": "Mixed English and Spanish billing query."
    },
    {
        "id": "case_bill_006",
        "input": "What is the price difference between the annual plan and the monthly plan? Is there a discount for annual?",
        "expected_category": "billing",
        "expected_summary": "Customer inquires about plan pricing and discounts for annual billing.",
        "expected_difficulty": "easy",
        "notes": "Standard pricing policy inquiry."
    },
    {
        "id": "case_bill_007",
        "input": "I need to cancel my premium subscription immediately. I do not want to be billed next month.",
        "expected_category": "billing",
        "expected_summary": "Customer requests immediate cancellation of subscription to prevent future billing.",
        "expected_difficulty": "easy",
        "notes": "Standard cancellation request."
    },
    {
        "id": "case_bill_008",
        "input": "My bank details changed. How do I switch my payment method from credit card to direct debit/ACH?",
        "expected_category": "billing",
        "expected_summary": "Customer requests instructions to update payment method to ACH/direct debit.",
        "expected_difficulty": "medium",
        "notes": "Change payment method to bank debit."
    },
    {
        "id": "case_bill_009",
        "input": "I was charged for a seat that is inactive. Can you prorate our bill and issue a credit to our invoice?",
        "expected_category": "billing",
        "expected_summary": "Customer requests a credit for an inactive seat charge on their invoice.",
        "expected_difficulty": "medium",
        "notes": "Prorated seat adjustment query."
    },
    {
        "id": "case_bill_010",
        "input": "Your pricing page is very confusing. It says $10/user/month but my bill shows $12. Why?",
        "expected_category": "billing",
        "expected_summary": "Customer inquires about a discrepancy between listed pricing and their actual bill.",
        "expected_difficulty": "medium",
        "notes": "Price discrepancy query."
    },
    {
        "id": "case_bill_011",
        "input": "Is there a student or non-profit discount available for the Pro plan? We are a charity group.",
        "expected_category": "billing",
        "expected_summary": "Customer asks if student or non-profit discounts are available for the Pro plan.",
        "expected_difficulty": "easy",
        "notes": "Discount eligibility query."
    },
    {
        "id": "case_bill_012",
        "input": "I forgot to cancel before the trial ended, and just got charged. I haven't used the app since paying. Can you refund me?",
        "expected_category": "billing",
        "expected_summary": "Customer requests refund for accidental post-trial charge.",
        "expected_difficulty": "medium",
        "notes": "Refund request for forgotten trial cancel."
    },
    {
        "id": "case_bill_013",
        "input": "Refund please.",
        "expected_category": "billing",
        "expected_summary": "Customer demands refund in a very short message.",
        "expected_difficulty": "medium",
        "notes": "Extremely short message, tests classifier ability to infer billing category from minimal context."
    },

    # --- TECHNICAL (13 cases) ---
    {
        "id": "case_tech_001",
        "input": "Every time I try to import my CSV file, the upload spinner spins forever and then I get a 504 Gateway Timeout error. I've tried 3 times.",
        "expected_category": "technical",
        "expected_summary": "Customer reports 504 Gateway Timeout errors when attempting to upload a CSV file.",
        "expected_difficulty": "easy",
        "notes": "CSV import failure with timeout."
    },
    {
        "id": "case_tech_002",
        "input": "The API endpoint /v1/data is returning a 500 Internal Server Error when we send a POST request with nested JSON. Here is the payload...",
        "expected_category": "technical",
        "expected_summary": "Customer reports a 500 Internal Server Error on POST requests to the /v1/data API endpoint.",
        "expected_difficulty": "easy",
        "notes": "API bug report with endpoint and payload details."
    },
    {
        "id": "case_tech_003",
        "input": "I'm trying to log in but the screen is just completely blank. The console shows a bundle error: main.js:1042 Uncaught ReferenceError.",
        "expected_category": "technical",
        "expected_summary": "Customer reports a blank screen and bundle JS console error during login.",
        "expected_difficulty": "medium",
        "notes": "Front-end JS error. Mentions login, but is a technical issue, not an account recovery issue."
    },
    {
        "id": "case_tech_004",
        "input": "Your login screen is a masterclass in slow. been waiting 5 mins. page is frozen. grrrr.",
        "expected_category": "technical",
        "expected_summary": "Customer complains about a frozen, extremely slow-loading login page.",
        "expected_difficulty": "medium",
        "notes": "Informal language, sarcasm, performance complaint."
    },
    {
        "id": "case_tech_005",
        "input": "Hello! Webhook payloads for events 'user.created' are missing the 'created_at' timestamp field. It was there yesterday. Did something deploy?",
        "expected_category": "technical",
        "expected_summary": "Customer reports missing 'created_at' field in webhook payloads since a recent deployment.",
        "expected_difficulty": "medium",
        "notes": "API payload regression report."
    },
    {
        "id": "case_tech_006",
        "input": "I cann't log in. Scren goes withe! Pls fix it asap.",
        "expected_category": "technical",
        "expected_summary": "Customer reports a blank screen login failure using misspelt words.",
        "expected_difficulty": "medium",
        "notes": "Heavy typos ('cann't', 'Scren', 'withe'). Checks tolerance to spelling issues."
    },
    {
        "id": "case_tech_007",
        "input": "The iOS app crashes instantly on launch after the latest update (v4.2.1). I'm on iOS 17.2, iPhone 15.",
        "expected_category": "technical",
        "expected_summary": "Customer reports instant iOS app crash on launch after update v4.2.1.",
        "expected_difficulty": "easy",
        "notes": "Mobile app crash report."
    },
    {
        "id": "case_tech_008",
        "input": "We are getting rate limited on the search endpoint even though we are way below our API plan limits. Can you check if our headers are being ignored?",
        "expected_category": "technical",
        "expected_summary": "Customer reports incorrect rate-limiting on the API search endpoint.",
        "expected_difficulty": "medium",
        "notes": "API limit and rate limiting configuration issue."
    },
    {
        "id": "case_tech_009",
        "input": "The password reset email link redirects me to a 404 page. I tried it twice. Is the site down?",
        "expected_category": "technical",
        "expected_summary": "Customer reports a 404 error when clicking the password reset link.",
        "expected_difficulty": "medium",
        "notes": "Double-intent. Mentions 'password reset' (account word) but the core issue is a broken redirect link (technical 404)."
    },
    {
        "id": "case_tech_010",
        "input": "Our database connection sync is failing. The logs show: 'Connection timed out'. Can you check your database status?",
        "expected_category": "technical",
        "expected_summary": "Customer reports database connection timeout sync failure.",
        "expected_difficulty": "easy",
        "notes": "Sync server timeout report."
    },
    {
        "id": "case_tech_011",
        "input": "The layout on the dashboard is completely broken on Safari Mobile. The tables overlap and buttons are unclickable.",
        "expected_category": "technical",
        "expected_summary": "Customer reports broken UI layout and overlapping tables on Safari Mobile.",
        "expected_difficulty": "easy",
        "notes": "CSS layout compatibility bug."
    },
    {
        "id": "case_tech_012",
        "input": "Why is the search API returning cached results? We updated our data 20 minutes ago but GET queries still show old fields.",
        "expected_category": "technical",
        "expected_summary": "Customer reports caching latency issues with API search queries.",
        "expected_difficulty": "medium",
        "notes": "API caching strategy bug query."
    },
    {
        "id": "case_tech_013",
        "input": "It's broken again.",
        "expected_category": "technical",
        "expected_summary": "Customer reports vague system failure without details.",
        "expected_difficulty": "hard",
        "notes": "No details. LLM must capture it as general/technical issue, but typically 'broken' points to technical failure."
    },

    # --- ACCOUNT (12 cases) ---
    {
        "id": "case_acc_001",
        "input": "I want to delete my account and purge all personal information from your servers in compliance with GDPR. Please confirm when completed.",
        "expected_category": "account",
        "expected_summary": "Customer requests permanent account deletion and data purge under GDPR.",
        "expected_difficulty": "easy",
        "notes": "Standard account deletion request."
    },
    {
        "id": "case_acc_002",
        "input": "How can I invite my team members to our workspace? I am the admin but I don't see an invite button anywhere.",
        "expected_category": "account",
        "expected_summary": "Customer asks how to invite team members to their admin workspace.",
        "expected_difficulty": "easy",
        "notes": "Workspace user invitations help."
    },
    {
        "id": "case_acc_003",
        "input": "I no longer have access to my registered email address (john@oldcompany.com) as I left the firm. How can I transfer ownership to john@newcompany.com?",
        "expected_category": "account",
        "expected_summary": "Customer requests to transfer account ownership to a new email address due to employment change.",
        "expected_difficulty": "medium",
        "notes": "Ownership transfer and email change request."
    },
    {
        "id": "case_acc_004",
        "input": "I am trying to reset my password but I never receive the password reset email. I checked my spam folder too. Can you help reset it manually?",
        "expected_category": "account",
        "expected_summary": "Customer requests manual password reset due to non-receipt of system email.",
        "expected_difficulty": "easy",
        "notes": "Password reset email delivery problem."
    },
    {
        "id": "case_acc_005",
        "input": "I want to delete my account immediately. The billing is ridiculous, you charged me twice and your site crashed during payment. Awful tool.",
        "expected_category": "account",
        "expected_summary": "Customer requests account deletion due to frustration over billing errors and site crashes.",
        "expected_difficulty": "hard",
        "notes": "Triple-category intent! Billing issues and site crashes (technical) are listed, but the primary explicit request is account deletion."
    },
    {
        "id": "case_acc_006",
        "input": "How do I turn on two-factor authentication (2FA) for my account? I need to secure it.",
        "expected_category": "account",
        "expected_summary": "Customer asks for instructions to enable two-factor authentication (2FA).",
        "expected_difficulty": "easy",
        "notes": "Security configuration question."
    },
    {
        "id": "case_acc_007",
        "input": "Can I merge two accounts? I registered one under personal Gmail and one under my work email, and want to combine them.",
        "expected_category": "account",
        "expected_summary": "Customer asks if they can merge two accounts registered under different email addresses.",
        "expected_difficulty": "medium",
        "notes": "Account merging functionality query."
    },
    {
        "id": "case_acc_008",
        "input": "I need to change my account name and profile picture but the fields are locked. How do I edit them?",
        "expected_category": "account",
        "expected_summary": "Customer inquires about locked profile fields and how to update account details.",
        "expected_difficulty": "easy",
        "notes": "Profile editing guide request."
    },
    {
        "id": "case_acc_009",
        "input": "I got an email alert about a suspicious login from Russia. Was my account hacked? Can you check logs?",
        "expected_category": "account",
        "expected_summary": "Customer inquires about account security following a suspicious login alert.",
        "expected_difficulty": "medium",
        "notes": "Security incident query."
    },
    {
        "id": "case_acc_010",
        "input": "How do I upgrade my single-user account to a corporate team plan with 10 seats?",
        "expected_category": "account",
        "expected_summary": "Customer asks how to upgrade a single-user account to a corporate plan with 10 seats.",
        "expected_difficulty": "medium",
        "notes": "Plan upgrade process query. Involves seats (billing) but primary request is account type change."
    },
    {
        "id": "case_acc_011",
        "input": "Please remove my phone number from my profile. I do not want it stored.",
        "expected_category": "account",
        "expected_summary": "Customer requests removal of their phone number from profile settings.",
        "expected_difficulty": "easy",
        "notes": "Data removal query."
    },
    {
        "id": "case_acc_012",
        "input": "Locked out of my admin dashboard. Need immediate assistance.",
        "expected_category": "account",
        "expected_summary": "Customer requests recovery support for a locked admin account.",
        "expected_difficulty": "medium",
        "notes": "Account lockout inquiry."
    },

    # --- GENERAL (12 cases) ---
    {
        "id": "case_gen_001",
        "input": "Hi there! I absolutely love your product. It has saved my team hours of manual work. Do you have a public roadmap we can look at?",
        "expected_category": "general",
        "expected_summary": "Customer praises the product and asks for access to the public roadmap.",
        "expected_difficulty": "easy",
        "notes": "Positive feedback and feature roadmap request."
    },
    {
        "id": "case_gen_002",
        "input": "Hello, I am representing a technology consulting firm and would love to discuss a potential partnership or affiliate setup. Who is the best person to speak with?",
        "expected_category": "general",
        "expected_summary": "Business inquiry regarding partnership and affiliate program opportunities.",
        "expected_difficulty": "easy",
        "notes": "Business development/partnership query."
    },
    {
        "id": "case_gen_003",
        "input": "Is it possible to add a dark mode theme to the dashboard? Working at night is hurting my eyes.",
        "expected_category": "general",
        "expected_summary": "Customer requests the addition of a dark mode theme for nighttime use.",
        "expected_difficulty": "easy",
        "notes": "Standard feature request."
    },
    {
        "id": "case_gen_004",
        "input": "Hey guys, love the tool but the export button should support Excel, not just CSV. Just a suggestion!",
        "expected_category": "general",
        "expected_summary": "Customer suggests adding Excel support to the export feature.",
        "expected_difficulty": "easy",
        "notes": "Feature improvement recommendation."
    },
    {
        "id": "case_gen_005",
        "input": "I am writing a blog post about LLM operations and want to feature your tool. Do you have a press kit with official logos?",
        "expected_category": "general",
        "expected_summary": "Customer requests a press kit and logos to feature the product in a blog post.",
        "expected_difficulty": "easy",
        "notes": "Media/PR query."
    },
    {
        "id": "case_gen_006",
        "input": "Do you offer offline on-premise installation for enterprise customers, or is it strictly SaaS?",
        "expected_category": "general",
        "expected_summary": "Customer asks if enterprise on-premises installations are supported.",
        "expected_difficulty": "medium",
        "notes": "SaaS vs On-prem configuration question."
    },
    {
        "id": "case_gen_007",
        "input": "Hello! I am a student doing research on customer service automations. Can I ask your founder 3 questions?",
        "expected_category": "general",
        "expected_summary": "Student requests founder interview for academic research on customer service automation.",
        "expected_difficulty": "easy",
        "notes": "Interview request/general inquiry."
    },
    {
        "id": "case_gen_008",
        "input": "Just wanted to say keep up the good work. Your updates are amazing.",
        "expected_category": "general",
        "expected_summary": "Customer sends positive feedback praising updates.",
        "expected_difficulty": "easy",
        "notes": "Pure positive feedback/praise."
    },
    {
        "id": "case_gen_009",
        "input": "Are you guys hiring? I am a junior software engineer specializing in Python and React.",
        "expected_category": "general",
        "expected_summary": "Job seeker inquires about software engineering job openings.",
        "expected_difficulty": "easy",
        "notes": "Job application/hiring inquiry."
    },
    {
        "id": "case_gen_010",
        "input": "Where are your servers hosted? I need to check compliance standards.",
        "expected_category": "general",
        "expected_summary": "Customer inquires about hosting location for compliance validation.",
        "expected_difficulty": "medium",
        "notes": "General compliance/hosting question."
    },
    {
        "id": "case_gen_011",
        "input": "Your website doesn't load on my ancient Netscape browser. Just FYI.",
        "expected_category": "general",
        "expected_summary": "Customer sends a joke feedback about Netscape compatibility.",
        "expected_difficulty": "hard",
        "notes": "Could be technical, but since Netscape is obsolete and the tone is casual report, it sits as general feedback."
    },
    {
        "id": "case_gen_012",
        "input": "Hi.",
        "expected_category": "general",
        "expected_summary": "Customer sends a short greeting.",
        "expected_difficulty": "easy",
        "notes": "Simple greeting, no specific intent."
    }
]

def seed():
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    
    # Save the golden dataset as versioned JSON
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_dataset.json")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully generated {len(test_cases)} test cases in {data_path}")

if __name__ == "__main__":
    seed()
