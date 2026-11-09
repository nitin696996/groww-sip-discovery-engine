from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from app.db.models import get_db, upsert_extracted_insight, upsert_raw_document
from app.triage.signal_filter import score_document_signal


CURATED_REALISTIC_CORPUS: List[Dict[str, Any]] = [
    # --- 1. REDDIT: r/MutualfundsIndia & r/personalfinanceindia & r/IndiaInvestments ---
    {
        "external_id": "rd_mfi_101",
        "source": "reddit",
        "sub_source": "r/MutualfundsIndia",
        "author_handle": "u/fresher_blr_22",
        "title": "22M started ₹5k/month SIP on Groww after watching Ankur Warikoo, why is my portfolio in red after 4 months?",
        "content": (
            "I got my first IT job in Bangalore (₹42k in-hand salary) and immediately started 5 SIPs of ₹1,000 each on Groww "
            "after watching YouTube compounding reels that showed 15-18% annual returns. I picked Quant Small Cap, Nippon Small Cap, "
            "Motilal Midcap, HDFC Defence, and PSU fund. For the first two months I checked the Groww app 4 times a day at 10 PM when NAV updates. "
            "Now after 4 months my 1D return was -₹840 yesterday and overall XIRR is -6.4%. Honestly feeling cheated because in FD at least "
            "my principal never goes down. Should I pause all my SIPs and wait for the market to recover before restarting?"
        ),
        "url": "https://www.reddit.com/r/MutualfundsIndia/comments/1k9sip1/22m_started_5k_sip_on_groww_portfolio_in_red/",
        "rating": None,
        "upvotes": 148,
        "days_ago": 4,
        "insight": {
            "sip_journey_stage": "months_3_to_12_volatility",
            "emotional_state": "disillusioned_anxious",
            "trigger_and_expectation": "First IT salary + finfluencer compounding reels; expected linear 15-18% FD-like monthly positive returns without drawdowns.",
            "post_start_behavior_change": "Over-diversified into 5 high-beta small-cap/thematic funds and developed a 4x/day compulsive night-time NAV checking habit.",
            "pause_reduce_stop_driver": "Seeing -6.4% XIRR and negative 1D return after 4 months vs safety of bank FD principal.",
            "checking_frequency_and_metrics": "Checks 4x daily, specifically around 10 PM NAV update; fixates on 1D rupee change and short-term XIRR.",
            "in_app_confusion_or_worry": "App prominently surfaces 1D red loss and volatile XIRR on a 4-month-old SIP without contextualizing equity drawdowns.",
            "external_validation_behavior": "Posted screenshot on r/MutualfundsIndia asking strangers whether to pause SIPs and wait for recovery.",
            "retention_vs_dropoff_signal": "High drop-off risk: return-chasing thematic/small-cap selection + FD mental model + urge to pause during dips.",
            "unmet_need": "First Market Dip Reassurance Coach & Portfolio Overlap/Volatility Warning during SIP onboarding.",
            "unmet_need_category": "Behavioral Coaching & Expectation Setting",
            "verbatim_quote": "For the first two months I checked the Groww app 4 times a day at 10 PM when NAV updates. Now after 4 months my 1D return was -₹840 yesterday and overall XIRR is -6.4%. Honestly feeling cheated because in FD at least my principal never goes down.",
            "question_tags": ["q1", "q2", "q3", "q4", "q6", "q7", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "gen_z_18_24",
            "money_source": "monthly_salary",
            "primary_influencer": "youtube_finfluencer",
        },
    },
    {
        "external_id": "rd_pfi_102",
        "source": "reddit",
        "sub_source": "r/personalfinanceindia",
        "author_handle": "u/freelance_ui_rahi",
        "title": "Scared of HDFC bank ₹590 ECS/NACH bounce charges — cancelled all my Groww autopay mandates!",
        "content": (
            "I work as a freelance UI designer and my client payments come between the 8th and 22nd of every month. "
            "Last month my ₹10,000 Parag Parikh Flexi Cap SIP date was on the 5th. Even though I clicked 'Skip SIP' on Groww "
            "2 days before the 5th, the NACH bank mandate was already triggered and HDFC Bank charged me ₹590 incl GST as mandate return penalty! "
            "That ₹590 penalty wiped out 2 months of my gains. I immediately deleted my autopay mandate and paused my SIPs. "
            "Why doesn't Groww tell you clearly that skipping less than 4 days before SIP date still hits the bank NACH pipeline?"
        ),
        "url": "https://www.reddit.com/r/personalfinanceindia/comments/1k8nach/scared_of_hdfc_590_nach_bounce_charges_groww/",
        "rating": None,
        "upvotes": 312,
        "days_ago": 6,
        "insight": {
            "sip_journey_stage": "pause_reduce_stop",
            "emotional_state": "frustrated_betrayed",
            "trigger_and_expectation": "Started ₹10k Flexi Cap SIP expecting flexible control to skip months when freelance cashflow is delayed.",
            "post_start_behavior_change": "Deleted bank autopay mandate completely and shifted from automated investing to manual lump-sum hesitation.",
            "pause_reduce_stop_driver": "₹590 bank NACH/ECS bounce penalty triggered despite clicking Skip SIP 2 days before due date, plus irregular freelance cashflow.",
            "checking_frequency_and_metrics": "Checks bank balance vs upcoming SIP due dates anxiously around the 1st-5th of each month.",
            "in_app_confusion_or_worry": "Opaque T-4 day NACH bank presentation cutoff: app allowed 'Skip' UI action or didn't warn that bank debit was already locked in.",
            "external_validation_behavior": "Warned peers on r/personalfinanceindia and asked if manual UPI one-time investment is safer than SIP mandates.",
            "retention_vs_dropoff_signal": "Critical churn trigger for non-salaried users: rigid date-locked NACH mandates punish variable income earners.",
            "unmet_need": "Payday-Flexible SIP / UPI Pre-Debit Approval Nudge with Hard Bank-Lock Countdown Banner.",
            "unmet_need_category": "Mandate & Cashflow Flexibility",
            "verbatim_quote": "Even though I clicked 'Skip SIP' on Groww 2 days before the 5th, the NACH bank mandate was already triggered and HDFC Bank charged me ₹590 incl GST as mandate return penalty!",
            "question_tags": ["q3", "q5", "q6", "q7", "q8", "q9"],
            "income_stability": "freelance_gig",
            "age_cohort": "young_millennial_25_32",
            "money_source": "lumpy_bonus_savings",
            "primary_influencer": "self_researched_reddit",
        },
    },
    {
        "external_id": "rd_ii_103",
        "source": "reddit",
        "sub_source": "r/IndiaInvestments",
        "author_handle": "u/steady_compounder_34",
        "title": "What separated me continuing my SIPs for 6 years vs my 4 office friends who all quietly dropped off in 10 months",
        "content": (
            "Back in 2020, 5 of us in my Pune software team started SIPs on Groww together after a senior colleague explained index funds. "
            "Today I am the only one still running my SIP (stepped up from ₹8k to ₹35k/month). Why did the other 4 quietly stop? "
            "Two of them started 9 different SIPs in trending thematic/sectoral funds after watching YouTube videos, got overwhelmed tracking them, "
            "and stopped when midcaps corrected 12%. One paused for 2 months for his sister's wedding expenses and simply never opened the app to resume "
            "because the inertia is huge once you pause. The only reason I survived was keeping just 1 Nifty 50 Index fund + 1 Flexi Cap, linking it "
            "to my salary date (2nd of month), and turning off Groww notifications so I only check once a quarter."
        ),
        "url": "https://www.reddit.com/r/IndiaInvestments/comments/1k7stick/what_separated_me_continuing_sips_for_6_years/",
        "rating": None,
        "upvotes": 489,
        "days_ago": 9,
        "insight": {
            "sip_journey_stage": "long_term_compounding",
            "emotional_state": "confident_disciplined",
            "trigger_and_expectation": "Peer colleague discussion at workplace; realistic 7-10 year wealth compounding expectation.",
            "post_start_behavior_change": "Consolidated to 2 simple funds, aligned SIP date immediately after salary credit (2nd), and muted daily notifications.",
            "pause_reduce_stop_driver": "Friends dropped off due to: (1) 9-fund clutter fatigue, (2) 12% correction panic, and (3) temporary pause for family wedding turning into permanent inertia.",
            "checking_frequency_and_metrics": "Checks once per quarter; evaluates long-term XIRR and annual step-up target rather than 1D returns.",
            "in_app_confusion_or_worry": "Once a user pauses a SIP for a 1-2 month emergency, there is no frictionless 'Auto-Resume with gentle ramp-up' flow.",
            "external_validation_behavior": "Long-form reflection on r/IndiaInvestments comparing peer group behaviors.",
            "retention_vs_dropoff_signal": "Stickers use <=3 core funds, payday auto-debit, and low checking frequency; drop-offs collect >6 thematic funds or pause without auto-resume.",
            "unmet_need": "Smart Auto-Resume SIP Holiday (e.g., Pause for 2 months with automatic ₹1,000 gentle restart) & Calm Quarterly Mode.",
            "unmet_need_category": "Retention & Habit Recovery",
            "verbatim_quote": "One paused for 2 months for his sister's wedding expenses and simply never opened the app to resume because the inertia is huge once you pause.",
            "question_tags": ["q1", "q2", "q3", "q4", "q7", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "mature_33_plus",
            "money_source": "monthly_salary",
            "primary_influencer": "friends_colleagues",
        },
    },
    {
        "external_id": "rd_mfi_104",
        "source": "reddit",
        "sub_source": "r/MutualfundsIndia",
        "author_handle": "u/college_sip_arjun",
        "title": "19M student investing ₹500 from pocket money on Groww — why did ₹500 get cut on Friday and still 'Order in Progress' on Tuesday?",
        "content": (
            "I saved ₹500 from my hostel allowance to start my very first SIP in UTI Nifty 50 on Groww. "
            "Money was debited from my SBI account via UPI at 3:40 PM on Friday. Saturday, Sunday, Monday passed and even on Tuesday morning "
            "Groww still shows 'Order in progress - awaiting unit allotment from AMC'. Plus the market jumped 1.8% on Monday so which day's NAV "
            "will I get?! I called my elder brother in panic thinking my money is stuck in some glitch. Why doesn't the app show exact 2:00 PM "
            "SEBI cut-off rule and weekend T+2 settlement timeline clearly?"
        ),
        "url": "https://www.reddit.com/r/MutualfundsIndia/comments/1k5nav/19m_student_first_sip_order_in_progress_panic/",
        "rating": None,
        "upvotes": 94,
        "days_ago": 3,
        "insight": {
            "sip_journey_stage": "onboarding_mandate",
            "emotional_state": "panicked_confused",
            "trigger_and_expectation": "College student saving ₹500 hostel pocket money; expected instant e-commerce style delivery of mutual fund units upon UPI debit.",
            "post_start_behavior_change": "Repeatedly refreshed order status across 4 days and feared money was lost in transit.",
            "pause_reduce_stop_driver": "First-time trust shock when money leaves bank account on Friday afternoon and shows zero units until Tuesday.",
            "checking_frequency_and_metrics": "Checked order status screen 10+ times over the weekend tracking NAV date eligibility.",
            "in_app_confusion_or_worry": "Complete confusion over SEBI 2:00 PM realization cutoff, weekend non-business days, and T+1/T+2 AMC allotment pipeline.",
            "external_validation_behavior": "Called elder brother in panic and posted on Reddit to verify if Friday->Tuesday delay is normal.",
            "retention_vs_dropoff_signal": "Onboarding anxiety peak: 72-hour gap between bank debit and unit visibility scares first-time young investors.",
            "unmet_need": "Domino's-Style Live NAV & Unit Allotment Tracker explaining 2 PM Cut-off, ICCL Clearing, and exact AMC allotment timestamp.",
            "unmet_need_category": "In-App Transparency & Trust",
            "verbatim_quote": "Money was debited from my SBI account via UPI at 3:40 PM on Friday... even on Tuesday morning Groww still shows 'Order in progress'...",
            "question_tags": ["q1", "q4", "q5", "q6", "q8", "q9"],
            "income_stability": "student_pocket_money",
            "age_cohort": "gen_z_18_24",
            "money_source": "parent_allowance",
            "primary_influencer": "family",
        },
    },
    {
        "external_id": "rd_pfi_105",
        "source": "reddit",
        "sub_source": "r/personalfinanceindia",
        "author_handle": "u/sneha_hyd_dev",
        "title": "Have 11 active SIPs on Groww totaling ₹18,000/month — everyone on Reddit says my portfolio is a 'Mutual Fund of Mutual Funds'",
        "content": (
            "Whenever Groww showed 'Popular Funds' or 'High Return Small Cap' on the home tab over the last 8 months, I kept adding a new ₹1,500 SIP. "
            "Now I have 11 SIPs running across 4 small caps, 3 mid caps, 2 flexi caps, and 2 thematic funds. Yesterday I pasted my screenshot on "
            "r/MutualfundsIndia and people roasted me saying I have 68% stock overlap and I'm basically paying active expense ratios to buy the entire market. "
            "Now I want to clean it up and reduce to 3 funds, but I'm confused in Groww: if I stop 8 SIPs and redeem them, how much Exit Load and 20% STCG tax "
            "will I lose right now?"
        ),
        "url": "https://www.reddit.com/r/personalfinanceindia/comments/1k6overlap/11_active_sips_on_groww_portfolio_roast/",
        "rating": None,
        "upvotes": 215,
        "days_ago": 5,
        "insight": {
            "sip_journey_stage": "months_3_to_12_volatility",
            "emotional_state": "overwhelmed_hesitant",
            "trigger_and_expectation": "Triggered by in-app 'Popular / High 3Y Return' discovery carousels; thought adding more funds meant safer diversification.",
            "post_start_behavior_change": "Accumulated 11 overlapping SIPs over 8 months, then froze when trying to consolidate due to tax/exit-load fear.",
            "pause_reduce_stop_driver": "Stopped 8 SIPs after realizing 68% portfolio overlap, but stuck on whether to redeem existing units.",
            "checking_frequency_and_metrics": "Compares 3Y historical return rankings on the Explore screen and individual fund P&L.",
            "in_app_confusion_or_worry": "App nudges discovering new funds easily, but lacks pre-investment overlap warnings or an exact Exit-Load + STCG Tax impact calculator before consolidation.",
            "external_validation_behavior": "Shared portfolio screenshot on Reddit for peer audit and used third-party overlap tools.",
            "retention_vs_dropoff_signal": "Choice overload & clutter paralysis: investors with >7 funds experience high cognitive load and stop SIPs impulsively.",
            "unmet_need": "Pre-SIP Portfolio Overlap Check + One-Click 'Tax & Exit-Load Safe Consolidation' Simulator.",
            "unmet_need_category": "Portfolio Hygiene & Tax Clarity",
            "verbatim_quote": "Whenever Groww showed 'Popular Funds' or 'High Return Small Cap' on the home tab over the last 8 months, I kept adding a new ₹1,500 SIP. Now I have 11 SIPs running...",
            "question_tags": ["q1", "q2", "q3", "q5", "q6", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "young_millennial_25_32",
            "money_source": "monthly_salary",
            "primary_influencer": "app_nudge",
        },
    },

    # --- 2. GOOGLE PLAY STORE REVIEWS (High-Signal Behavioral Narratives) ---
    {
        "external_id": "gp_rev_201",
        "source": "play_store",
        "sub_source": "Google Play India (v18.42.1)",
        "author_handle": "Vikramaditya Sharma",
        "title": "2★ Google Play Review — Autopay ₹1,00,000 limit scared my father",
        "content": (
            "I was helping my 54-year-old father set up a simple ₹3,000 monthly SIP in HDFC Balanced Advantage Fund on Groww. "
            "When we reached the UPI Autopay / OTM mandate screen, the bank SMS said 'Approve mandate for up to ₹1,00,000'. "
            "My father immediately panicked thinking ₹1 Lakh will be deducted from his pension account and forced me to close the app! "
            "For first-time Indian families, seeing ₹1 Lakh max limit for a ₹3,000 SIP destroys trust immediately. Give an option to set exact mandate cap!"
        ),
        "url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_rev_201",
        "rating": 2,
        "upvotes": 87,
        "days_ago": 2,
        "insight": {
            "sip_journey_stage": "onboarding_mandate",
            "emotional_state": "distrustful_scared",
            "trigger_and_expectation": "Adult son onboarding father (pension/savings) into a conservative ₹3,000 Balanced Advantage SIP.",
            "post_start_behavior_change": "Abandoned SIP setup at the final mandate step due to ₹1,00,000 default OTM limit SMS.",
            "pause_reduce_stop_driver": "Onboarding drop-off caused by default ₹1 Lakh autopay ceiling mismatch with ₹3,000 SIP amount.",
            "checking_frequency_and_metrics": "Scrutinized bank SMS mandate limit during setup.",
            "in_app_confusion_or_worry": "Default ₹1,00,000 OTM/Autopay ceiling triggers scam/over-debit fear when the user only wants a ₹3,000 SIP.",
            "external_validation_behavior": "Family member stepped in and halted the transaction after reading bank SMS.",
            "retention_vs_dropoff_signal": "Silent onboarding drop-off: users abandon mandate authorization when default limit is 30x higher than their SIP.",
            "unmet_need": "Customizable Autopay Cap (e.g., Match exact SIP ₹3,000 or 2x buffer) + Plain-Language Bank SMS Preview.",
            "unmet_need_category": "Onboarding & Mandate Trust",
            "verbatim_quote": "When we reached the UPI Autopay / OTM mandate screen, the bank SMS said 'Approve mandate for up to ₹1,00,000'. My father immediately panicked thinking ₹1 Lakh will be deducted...",
            "question_tags": ["q1", "q3", "q5", "q7", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "mature_33_plus",
            "money_source": "lumpy_bonus_savings",
            "primary_influencer": "family",
        },
    },
    {
        "external_id": "gp_rev_202",
        "source": "play_store",
        "sub_source": "Google Play India (v18.40.0)",
        "author_handle": "Karthik Nair",
        "title": "3★ Google Play Review — Why did my SIP instalment not trigger when I paid manually 5 days early?",
        "content": (
            "When Nifty fell 2.5% last week, I used the 'Invest More' button on my existing SIP fund thinking it would count as this month's "
            "₹5,000 SIP installment at a lower NAV. Then 5 days later on my scheduled SIP date, Groww auto-debited ANOTHER ₹5,000 from my bank! "
            "Now ₹10,000 is gone from my salary account and my rent budget is tight. Beginners don't realize 'One-time top-up' and 'Monthly SIP installment' "
            "run on completely separate tracks."
        ),
        "url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_rev_202",
        "rating": 3,
        "upvotes": 63,
        "days_ago": 7,
        "insight": {
            "sip_journey_stage": "months_1_to_3_early",
            "emotional_state": "surprised_stressed",
            "trigger_and_expectation": "Tried to time a 2.5% market dip by paying monthly ₹5,000 installment manually 5 days early.",
            "post_start_behavior_change": "Attempted tactical dip-buying on an active SIP fund without understanding independent NACH scheduling.",
            "pause_reduce_stop_driver": "Accidental double deduction (₹10,000 instead of ₹5,000) disrupted monthly rent budget.",
            "checking_frequency_and_metrics": "Tracks Nifty daily drops and tries to manually buy dips inside existing SIP funds.",
            "in_app_confusion_or_worry": "Users confuse 'One-time Invest More on same folio' with 'Pay this month's SIP installment early'.",
            "external_validation_behavior": "Left detailed Play Store feedback warning other salaried beginners.",
            "retention_vs_dropoff_signal": "Cashflow shock from accidental double-debit leads users to disable autopay.",
            "unmet_need": "'Count this Top-Up as Upcoming Month's SIP' toggle when investing manually within 7 days of scheduled SIP date.",
            "unmet_need_category": "Mandate & Cashflow Flexibility",
            "verbatim_quote": "When Nifty fell 2.5% last week, I used the 'Invest More' button on my existing SIP fund thinking it would count as this month's ₹5,000 SIP installment... 5 days later Groww auto-debited ANOTHER ₹5,000!",
            "question_tags": ["q2", "q3", "q5", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "young_millennial_25_32",
            "money_source": "monthly_salary",
            "primary_influencer": "self_researched_reddit",
        },
    },
    {
        "external_id": "gp_rev_203",
        "source": "play_store",
        "sub_source": "Google Play India (v18.41.2)",
        "author_handle": "Pooja Deshmukh",
        "title": "4★ Google Play Review — External mutual fund tracking imported from CAMS shows wrong XIRR after switch",
        "content": (
            "I imported my older Regular mutual funds from PhonePe/bank into Groww using the external portfolio tracker and used Groww's "
            "'Switch to Direct' feature. While switching was easy, two of my folios still show outdated units from KFintech and my XIRR jumped to +84% "
            "which is obviously a calculation bug because it treated the switch date as fresh cost price without historical SIP dates. "
            "Whenever I feel unsure about Groww's XIRR number, I cross-check on ValueResearch and MFCentral."
        ),
        "url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_rev_203",
        "rating": 4,
        "upvotes": 41,
        "days_ago": 8,
        "insight": {
            "sip_journey_stage": "long_term_compounding",
            "emotional_state": "analytical_skeptical",
            "trigger_and_expectation": "Consolidated external Regular plans into Groww Direct plans to save 1% commission.",
            "post_start_behavior_change": "Switched from Regular to Direct funds after learning about expense ratio drag.",
            "pause_reduce_stop_driver": "Stopped Regular bank SIPs and migrated to Direct SIPs on Groww.",
            "checking_frequency_and_metrics": "Audits XIRR accuracy, cost-basis continuity, and folio sync across CAMS/KFintech.",
            "in_app_confusion_or_worry": "Switch-to-Direct resets holding period / XIRR baseline on imported external folios, making returns look artificially inflated.",
            "external_validation_behavior": "Cross-verifies portfolio XIRR and unit holdings on MFCentral and ValueResearch when Groww metrics look off.",
            "retention_vs_dropoff_signal": "High-retention savvy user: understands Direct vs Regular expense ratios, demands accurate XIRR accounting.",
            "unmet_need": "Grandfathered Cost-Basis XIRR toggle (Show original Regular SIP start-date XIRR vs Post-Switch Direct XIRR).",
            "unmet_need_category": "Portfolio Hygiene & Tax Clarity",
            "verbatim_quote": "My XIRR jumped to +84% which is obviously a calculation bug because it treated the switch date as fresh cost price... When unsure I cross-check on ValueResearch and MFCentral.",
            "question_tags": ["q2", "q4", "q5", "q6", "q7", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "young_millennial_25_32",
            "money_source": "monthly_salary",
            "primary_influencer": "self_researched_reddit",
        },
    },

    # --- 3. APPLE APP STORE REVIEWS (iOS India) ---
    {
        "external_id": "ios_rev_301",
        "source": "app_store",
        "sub_source": "Apple App Store India (v18.39)",
        "author_handle": "RohanK_Mumbai",
        "title": "F&O and Intraday tabs distract me every time I open Groww just to check my peaceful SIP",
        "content": (
            "I started on Groww purely as a disciplined first-time mutual fund SIP investor putting ₹15,000/month from my salary. "
            "In month 3, because I was opening the app every afternoon to check my mutual fund returns, I kept seeing the Stocks / F&O / Nifty Options "
            "movers right next to Mutual Funds. Out of curiosity I activated F&O, lost ₹28,000 in 3 weeks, and ended up pausing my ₹15,000 SIP "
            "to recover my savings! Please give a 'Mutual Fund Only / Wealth Mode' lock so long-term SIP investors aren't tempted into F&O trading."
        ),
        "url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703",
        "rating": 3,
        "upvotes": 52,
        "days_ago": 5,
        "insight": {
            "sip_journey_stage": "pause_reduce_stop",
            "emotional_state": "regretful_tempted",
            "trigger_and_expectation": "Started as a disciplined ₹15k/month salaried SIP investor aiming for long-term wealth.",
            "post_start_behavior_change": "Daily afternoon app checking exposed him to F&O/Intraday tabs; experimented with options trading and lost ₹28k.",
            "pause_reduce_stop_driver": "Paused ₹15,000 monthly SIP to plug cashflow hole caused by ₹28,000 F&O trading loss.",
            "checking_frequency_and_metrics": "Opened app during live market hours (afternoon) even though mutual fund NAV only updates once at night.",
            "in_app_confusion_or_worry": "Co-mingling high-dopamine intraday/F&O tickers alongside passive mutual fund SIP dashboards cannibalizes SIP discipline.",
            "external_validation_behavior": "Publicly requested a dedicated 'Mutual Fund Only Mode' on App Store.",
            "retention_vs_dropoff_signal": "Behavioral cannibalization: frequent daytime checking bridges passive SIP savers into speculative F&O losses and SIP churn.",
            "unmet_need": "'SIP-Only Zen Mode' (Hide F&O/Intraday tabs & daytime market noise for passive wealth builders).",
            "unmet_need_category": "Behavioral Coaching & Expectation Setting",
            "verbatim_quote": "Out of curiosity I activated F&O, lost ₹28,000 in 3 weeks, and ended up pausing my ₹15,000 SIP to recover my savings! Please give a 'Mutual Fund Only / Wealth Mode' lock...",
            "question_tags": ["q2", "q3", "q4", "q5", "q7", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "young_millennial_25_32",
            "money_source": "monthly_salary",
            "primary_influencer": "app_nudge",
        },
    },
    {
        "external_id": "ios_rev_302",
        "source": "app_store",
        "sub_source": "Apple App Store India (v18.41)",
        "author_handle": "Ananya_S_Gurgaon",
        "title": "Started ELSS Tax Saver SIP in February without knowing EVERY monthly SIP installment is locked for 3 years!",
        "content": (
            "My HR sent an email in February asking for 80C tax proofs, so I quickly searched 'Tax Saving SIP' on Groww and started a ₹12,000/month "
            "ELSS SIP. Eight months later I needed ₹50,000 for a medical emergency and tried to redeem, only to discover that EVERY SINGLE monthly "
            "SIP installment has its own separate 3-year lock-in from its investment date! I thought the 3-year lock-in starts from the day I opened the folio. "
            "I immediately stopped the ELSS SIP because my emergency money got trapped."
        ),
        "url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703",
        "rating": 2,
        "upvotes": 76,
        "days_ago": 11,
        "insight": {
            "sip_journey_stage": "pause_reduce_stop",
            "emotional_state": "trapped_frustrated",
            "trigger_and_expectation": "Last-minute February HR 80C tax-proof deadline; assumed 3-year ELSS lock-in applied once from folio creation date.",
            "post_start_behavior_change": "Stopped ELSS SIP at month 8 after discovering she couldn't withdraw funds during a medical emergency.",
            "pause_reduce_stop_driver": "Liquidity shock: realized each monthly ELSS installment is locked for 36 months individually, leaving zero emergency access.",
            "checking_frequency_and_metrics": "Checked 'Redeemable Units vs Locked Units' breakdown during emergency.",
            "in_app_confusion_or_worry": "First-time investors misunderstand rolling 36-month per-installment lock-in on ELSS SIPs vs lump-sum.",
            "external_validation_behavior": "Consulted HR/CA and posted warning review after failed redemption attempt.",
            "retention_vs_dropoff_signal": "Uninformed tax-saving SIPs without an emergency liquid buffer lead to forced SIP termination during life emergencies.",
            "unmet_need": "Visual Rolling Lock-In Timeline on ELSS SIPs + 'Do you have an Emergency Fund first?' pre-check.",
            "unmet_need_category": "In-App Transparency & Trust",
            "verbatim_quote": "I tried to redeem, only to discover that EVERY SINGLE monthly SIP installment has its own separate 3-year lock-in from its investment date! I thought the 3-year lock-in starts from the day I opened the folio.",
            "question_tags": ["q1", "q3", "q5", "q7", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "young_millennial_25_32",
            "money_source": "monthly_salary",
            "primary_influencer": "friends_colleagues",
        },
    },

    # --- 4. YOUTUBE COMMENTS (Personal Finance & Groww Tutorial Videos) ---
    {
        "external_id": "yt_comm_401",
        "source": "youtube",
        "sub_source": "YouTube (Pranjal Kamra — Mutual Fund SIP Masterclass)",
        "author_handle": "@SandeepVerma_Lucknow",
        "title": "Comment on: Best Mutual Funds for SIP 2026 | Beginner Mistakes to Avoid",
        "content": (
            "Sir I run a small Kirana/medical wholesale shop in Lucknow. My income is good during festival months (₹80k) and very low in monsoon (₹20k). "
            "Because of this fear of fixed monthly commitment, I started a ₹2,000 SIP on Groww, ran it for 3 months, then paused it in July and never "
            "restarted. Whenever I have ₹15,000 extra cash in hand, I feel scared to put lump sum because YouTubers say market is at All-Time High (ATH). "
            "So the money just sits idle in my savings account earning 2.7%."
        ),
        "url": "https://www.youtube.com/watch?v=groww_sip_masterclass_in",
        "rating": None,
        "upvotes": 194,
        "days_ago": 7,
        "insight": {
            "sip_journey_stage": "silent_dropoff",
            "emotional_state": "hesitant_paralyzed",
            "trigger_and_expectation": "Small business owner inspired by YouTube finance videos to beat 2.7% savings account interest.",
            "post_start_behavior_change": "Ran a small ₹2,000 SIP for 3 months, paused during monsoon slow business season, and drifted into permanent inactivity.",
            "pause_reduce_stop_driver": "Seasonal business income dip in July + All-Time High (ATH) lump-sum valuation fear prevented restarting.",
            "checking_frequency_and_metrics": "Watches Nifty ATH headlines on YouTube rather than checking portfolio metrics.",
            "in_app_confusion_or_worry": "Binary choice between 'Rigid monthly SIP' vs 'Scary one-shot Lump Sum at market peak' leaves variable-income earners stuck.",
            "external_validation_behavior": "Asks YouTube finance creators in comment sections how business owners with irregular cashflow should do SIPs.",
            "retention_vs_dropoff_signal": "Classic quiet drop-off archetype: seasonal income earner pauses for 1 slow month and never resumes.",
            "unmet_need": "Automated Micro-STP / 'Flexi-Cashflow SIP' (Park lumpy business cash in Liquid Fund & auto-drip weekly into Equity).",
            "unmet_need_category": "Mandate & Cashflow Flexibility",
            "verbatim_quote": "My income is good during festival months (₹80k) and very low in monsoon (₹20k)... I started a ₹2,000 SIP on Groww, ran it for 3 months, then paused it in July and never restarted.",
            "question_tags": ["q1", "q2", "q3", "q6", "q7", "q8", "q9"],
            "income_stability": "business_variable",
            "age_cohort": "mature_33_plus",
            "money_source": "lumpy_bonus_savings",
            "primary_influencer": "youtube_finfluencer",
        },
    },
    {
        "external_id": "yt_comm_402",
        "source": "youtube",
        "sub_source": "YouTube (Labour Law Advisor — How SIP Return Really Works)",
        "author_handle": "@Megha_Patel_24",
        "title": "Comment on: Why 80% Beginners Stop SIP in 1 Year",
        "content": (
            "100% relatable!! When I started my ₹3,000 SIP on Groww 6 months ago using my first salary, I used to open Groww every single morning at 9:30 AM "
            "like a stock trader and got confused why the number wasn't moving! Then when the market fell for 2 weeks in a row, I watched 5 YouTube videos "
            "with red crash thumbnails ('Nifty going to 18,000?!') and asked my office WhatsApp group. Two colleagues told me to redeem before profits vanish, "
            "so I reduced my SIP from ₹3,000 to ₹500. Only now I realize falling NAV means I was getting more units!"
        ),
        "url": "https://www.youtube.com/watch?v=sip_beginner_mistakes_lla",
        "rating": None,
        "upvotes": 267,
        "days_ago": 10,
        "insight": {
            "sip_journey_stage": "pause_reduce_stop",
            "emotional_state": "anxious_influenced",
            "trigger_and_expectation": "First salary starter; expected stock-like live ticking prices and uninterrupted positive gains.",
            "post_start_behavior_change": "Checked app at 9:30 AM daily, panicked during a 2-week dip, and slashed SIP by 83% (₹3,000 -> ₹500).",
            "pause_reduce_stop_driver": "Alarmist YouTube 'Market Crash' thumbnails combined with peer panic in office WhatsApp group.",
            "checking_frequency_and_metrics": "Checked daily at 9:30 AM expecting live movement; focused only on total rupee gain rather than accumulated units.",
            "in_app_confusion_or_worry": "App highlights rupee value drop in red during market dips instead of celebrating 'You accumulated +14% more units this month at a discount!'.",
            "external_validation_behavior": "Binged alarmist YouTube crash videos and polled office WhatsApp group during market volatility.",
            "retention_vs_dropoff_signal": "Unit-accumulation blindness: beginners who don't see 'discounted unit accumulation' reduce or stop SIPs precisely when rupee-cost averaging works best.",
            "unmet_need": "'Rupee-Cost Averaging Unit Visualizer' (Show 'Discounted Units Bought on Red Days' badge instead of scary red P&L).",
            "unmet_need_category": "Behavioral Coaching & Expectation Setting",
            "verbatim_quote": "I watched 5 YouTube videos with red crash thumbnails and asked my office WhatsApp group. Two colleagues told me to redeem before profits vanish, so I reduced my SIP from ₹3,000 to ₹500.",
            "question_tags": ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "gen_z_18_24",
            "money_source": "monthly_salary",
            "primary_influencer": "friends_colleagues",
        },
    },

    # --- 5. TRADINGQ&A (Discourse Investing Forum) ---
    {
        "external_id": "tq_disc_501",
        "source": "tradingqna",
        "sub_source": "TradingQ&A (Mutual Funds Category)",
        "author_handle": "nithin_follower_blr",
        "title": "Goal tagging & behavioral stickiness: Why untagged SIPs get raided for iPhones and Goa trips",
        "content": (
            "I have been tracking my own behavior and my younger cousins' accounts on Groww for the past 3 years. "
            "Whenever someone starts a generic '₹5,000/month SIP in Parag Parikh or Nifty 50' without attaching it to a specific life goal, "
            "the moment that corpus crosses ₹60,000–₹80,000 in Month 14, they see it as 'free spendable profit' and redeem it to buy an iPhone 16 "
            "or fund a vacation. In contrast, my SIP tagged '2032 Kid Education ₹25L' has never been touched even during emergencies. "
            "Right now on Groww, SIPs sit in a flat list of funds showing current value and 1D change, which subconsciously treats long-term wealth like a wallet balance."
        ),
        "url": "https://tradingqna.com/t/goal-tagging-and-behavioral-stickiness-in-sips/162410",
        "rating": None,
        "upvotes": 78,
        "days_ago": 12,
        "insight": {
            "sip_journey_stage": "long_term_compounding",
            "emotional_state": "reflective_strategic",
            "trigger_and_expectation": "Started SIPs for long-term wealth vs younger cousins who started generic untagged SIPs.",
            "post_start_behavior_change": "Untagged SIP investors treat accumulated ₹60k-₹80k corpus at Month 14 as windfall spending money and redeem prematurely.",
            "pause_reduce_stop_driver": "Premature temptation redemption (iPhone/vacation upgrade) once corpus reaches a visible ₹60k-₹80k milestone.",
            "checking_frequency_and_metrics": "Views total current corpus value like a liquid bank wallet balance.",
            "in_app_confusion_or_worry": "Flat fund list UI displays total redeemable cash value upfront without psychological goal partitioning or 'future wealth lost if redeemed today' friction.",
            "external_validation_behavior": "Discussed behavioral finance mechanics with experienced investors on TradingQ&A.",
            "retention_vs_dropoff_signal": "Strongest separator between 5-year compounders and 14-month drop-offs is explicit Goal-Bucket Envelope locking.",
            "unmet_need": "Goal-Locked SIP Vaults with 'Future Compounding Cost Warning' before premature lifestyle redemptions.",
            "unmet_need_category": "Retention & Habit Recovery",
            "verbatim_quote": "Whenever someone starts a generic ₹5,000/month SIP without attaching it to a specific life goal, the moment that corpus crosses ₹60,000–₹80,000 in Month 14, they see it as 'free spendable profit' and redeem it...",
            "question_tags": ["q1", "q2", "q3", "q4", "q5", "q7", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "mature_33_plus",
            "money_source": "monthly_salary",
            "primary_influencer": "self_researched_reddit",
        },
    },
    {
        "external_id": "tq_disc_502",
        "source": "tradingqna",
        "sub_source": "TradingQ&A (Taxation & Regulations)",
        "author_handle": "ca_rajesh_mumbai",
        "title": "First-time SIP investors panicking over ₹1.25L LTCG harvesting and STT/Stamp duty deductions on Groww",
        "content": (
            "Every March I get 20+ queries from young salaried clients using Groww. First, when their ₹5,000 SIP gets allotted, they see ₹4,999.75 "
            "invested and ask if Groww is secretly charging a platform fee (they have no idea about 0.005% government stamp duty). Second, after 2 years "
            "when they hear about ₹1.25 Lakh tax-free LTCG harvesting on YouTube, they blindly redeem their entire folio without realizing which SIP "
            "tranches have crossed 365 days (FIFO rule), triggering 20% STCG + 1% Exit Load on their last 11 monthly SIP installments!"
        ),
        "url": "https://tradingqna.com/t/first-time-sip-investors-ltcg-harvesting-fifo-mistake/164892",
        "rating": None,
        "upvotes": 112,
        "days_ago": 14,
        "insight": {
            "sip_journey_stage": "long_term_compounding",
            "emotional_state": "confused_cautious",
            "trigger_and_expectation": "Heard about 'Tax-Free ₹1.25L LTCG Harvesting' on YouTube and tried to redeem SIP units in March.",
            "post_start_behavior_change": "Attempted DIY tax harvesting without understanding FIFO (First-In-First-Out) tranche aging across monthly SIPs.",
            "pause_reduce_stop_driver": "Surprise 20% STCG tax + 1% exit load hit when redeeming recent <12-month SIP tranches alongside older >12-month units.",
            "checking_frequency_and_metrics": "Checks exact allotted rupee amount (₹4,999.75 vs ₹5,000) on Day 1 and tax reports in March.",
            "in_app_confusion_or_worry": "Two major blind spots: (1) 0.005% Stamp Duty looks like a hidden fee, and (2) redeeming units doesn't default to 'Redeem ONLY >365-day LTCG & Exit-Load-Free units'.",
            "external_validation_behavior": "Runs to Chartered Accountants (CAs) and TradingQ&A after accidentally triggering STCG/Exit load.",
            "retention_vs_dropoff_signal": "Long-term investors need tranche-level tax guardrails during redemption/rebalancing.",
            "unmet_need": "One-Tap 'Select Only Exit-Load-Free & LTCG (>1 Yr) Units' Redemption Filter + 0.005% Stamp Duty Tooltip.",
            "unmet_need_category": "Portfolio Hygiene & Tax Clarity",
            "verbatim_quote": "They blindly redeem their entire folio without realizing which SIP tranches have crossed 365 days (FIFO rule), triggering 20% STCG + 1% Exit Load on their last 11 monthly SIP installments!",
            "question_tags": ["q2", "q4", "q5", "q6", "q8", "q9"],
            "income_stability": "salaried_stable",
            "age_cohort": "young_millennial_25_32",
            "money_source": "monthly_salary",
            "primary_influencer": "youtube_finfluencer",
        },
    },

    # --- 6. LOW-SIGNAL NOISE SAMPLES (To demonstrate Local Signal Triage filtering 0-token noise) ---
    {
        "external_id": "gp_noise_901",
        "source": "play_store",
        "sub_source": "Google Play India",
        "author_handle": "Ramesh Kumar",
        "title": "5★ Review",
        "content": "Very good app nice UI",
        "url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww",
        "rating": 5,
        "upvotes": 0,
        "days_ago": 1,
        "insight": None,
    },
    {
        "external_id": "gp_noise_902",
        "source": "play_store",
        "sub_source": "Google Play India",
        "author_handle": "Amit S",
        "title": "5★ Review",
        "content": "Best app",
        "url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww",
        "rating": 5,
        "upvotes": 1,
        "days_ago": 1,
        "insight": None,
    },
    {
        "external_id": "ios_noise_903",
        "source": "app_store",
        "sub_source": "Apple App Store India",
        "author_handle": "User9921",
        "title": "Good",
        "content": "Super fast",
        "url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703",
        "rating": 5,
        "upvotes": 0,
        "days_ago": 2,
        "insight": None,
    },
    {
        "external_id": "gp_noise_904",
        "source": "play_store",
        "sub_source": "Google Play India",
        "author_handle": "Suresh P",
        "title": "1★ Review",
        "content": "OTP not coming",
        "url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww",
        "rating": 1,
        "upvotes": 2,
        "days_ago": 2,
        "insight": None,
    },
]


def seed_baseline_corpus() -> Dict[str, int]:
    """
    Seeds the SQLite database with the high-signal realistic Indian investor corpus
    plus low-signal noise examples so the workbench is immediately rich and verifiable.
    Idempotent via SHA-256 content hashes.
    """
    inserted_docs = 0
    seeded_insights = 0
    now = datetime.now(timezone.utc)

    for item in CURATED_REALISTIC_CORPUS:
        score, status, reasons = score_document_signal(item["title"], item["content"], item["source"])
        pub_dt = (now - timedelta(days=int(item.get("days_ago", 3)))).isoformat()

        doc_id = upsert_raw_document(
            {
                "external_id": item["external_id"],
                "source": item["source"],
                "sub_source": item["sub_source"],
                "author_handle": item["author_handle"],
                "title": item["title"],
                "content": item["content"],
                "url": item["url"],
                "rating": item["rating"],
                "upvotes": item["upvotes"],
                "published_at": pub_dt,
                "triage_score": score,
                "triage_status": status,
                "triage_reasons": reasons,
            }
        )

        if doc_id is not None:
            inserted_docs += 1
            if item.get("insight"):
                ins = dict(item["insight"])
                ins["document_id"] = doc_id
                ins["confidence_score"] = 0.94
                ins["extracted_by_provider"] = "curated_behavioral_benchmark"
                upsert_extracted_insight(ins)
                seeded_insights += 1

    if inserted_docs > 0:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_runs (source, mode, fetched_count, inserted_count, high_signal_count, low_signal_filtered, status, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "multi_source_baseline",
                    "curated-indian-sip-corpus",
                    len(CURATED_REALISTIC_CORPUS),
                    inserted_docs,
                    seeded_insights,
                    inserted_docs - seeded_insights,
                    "SUCCESS",
                    "Initialized realistic multi-platform Indian SIP behavioral corpus (Reddit, Play Store, App Store, YouTube, TradingQ&A)",
                    now.isoformat(),
                ),
            )

    return {"inserted_documents": inserted_docs, "seeded_insights": seeded_insights}
