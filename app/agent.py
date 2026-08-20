from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


PROJECT = {
    "company": "Northstar Homes",
    "project": "Northstar One",
    "location": "Sector 79, Gurugram",
    "configs": ["2 BHK", "3 BHK"],
    "prices": {
        "2 BHK": 1.35,
        "3 BHK": 1.75,
    },
}


def empty_memory() -> dict[str, Any]:
    return {
        "language": "english",
        "name": None,
        "phone": None,
        "configuration": None,
        "budget": None,
        "budget_crore": None,
        "budget_fit": None,
        "purpose": None,
        "timeline": None,
        "customer_location": None,
        "site_visit_status": "not_requested",
        "site_visit_slot": None,
        "follow_up_required": False,
        "follow_up_time": None,
        "human_escalation_required": False,
        "do_not_contact": False,
        "not_interested": False,
        "unsupported_requirement": None,
        "out_of_scope": False,
    }


@dataclass
class ConversationState:
    session_id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=empty_memory)
    ended: bool = False
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class NorthstarAgent:
    def __init__(self) -> None:
        self.sessions: dict[str, ConversationState] = {}

    def chat(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        state = self.get_state(session_id)
        text = message.strip()

        if state.ended:
            reply = self.pick(
                state,
                "This conversation is already closed. Please start a new chat if you need help again.",
                "Ye conversation close ho chuki hai. Dobara help chahiye to new chat start kar sakte hain.",
                "यह बातचीत बंद हो चुकी है। मदद चाहिए तो नया चैट शुरू कर सकते हैं।",
            )
            return self.make_result(state, reply)

        state.messages.append({"role": "customer", "content": text})
        self.update_memory(state, text)
        reply = self.build_reply(state, text)
        state.messages.append({"role": "assistant", "content": reply})
        return self.make_result(state, reply)

    def end(self, session_id: str) -> dict[str, Any]:
        state = self.get_state(session_id)
        state.ended = True
        reply = self.pick(
            state,
            "Thanks for your time. I have closed this conversation.",
            "Thank you. Main conversation close kar raha hoon.",
            "धन्यवाद। मैंने यह बातचीत बंद कर दी है।",
        )
        state.messages.append({"role": "assistant", "content": reply})
        return self.make_result(state, reply)

    def get_state(self, session_id: str | None) -> ConversationState:
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        new_session_id = session_id or str(uuid4())
        state = ConversationState(session_id=new_session_id)
        self.sessions[new_session_id] = state
        return state

    def make_result(self, state: ConversationState, reply: str) -> dict[str, Any]:
        return {
            "session_id": state.session_id,
            "reply": reply,
            "ended": state.ended,
            "memory": state.memory,
            "analytics": self.analytics(state),
        }

    def update_memory(self, state: ConversationState, text: str) -> None:
        memory = state.memory
        lower = text.lower()
        memory["language"] = detect_language(text, memory["language"])

        name = extract_name(text)
        if name:
            memory["name"] = name

        phone = extract_phone(text)
        if phone:
            memory["phone"] = phone

        config = extract_configuration(lower)
        if config:
            memory["configuration"] = config
            memory["unsupported_requirement"] = None

        unsupported = extract_unsupported_requirement(lower)
        if unsupported:
            memory["unsupported_requirement"] = unsupported

        budget, budget_crore = extract_budget(lower)
        if budget:
            memory["budget"] = budget
            memory["budget_crore"] = budget_crore

        purpose = extract_purpose(lower)
        if purpose:
            memory["purpose"] = purpose

        timeline = extract_timeline(lower)
        if timeline:
            memory["timeline"] = timeline

        customer_location = extract_customer_location(text)
        if customer_location:
            memory["customer_location"] = customer_location

        if wants_site_visit(lower):
            memory["site_visit_status"] = "requested"

        if memory["site_visit_status"] == "requested" or wants_site_visit(lower):
            slot = extract_slot(text)
            if slot:
                memory["site_visit_slot"] = slot

        if is_later_request(lower) or is_busy(lower):
            memory["follow_up_required"] = True
            memory["follow_up_time"] = extract_slot(text) or "customer asked to contact later"

        memory["budget_fit"] = budget_fit(memory)

    def build_reply(self, state: ConversationState, text: str) -> str:
        lower = text.lower()
        memory = state.memory

        if is_stop_request(lower):
            memory["do_not_contact"] = True
            state.ended = True
            return self.pick(
                state,
                "Understood. I will not contact you again about Northstar One. Thank you for your time.",
                "Samajh gaya. Northstar One ke baare mein main aapko dobara contact nahi karunga. Thank you.",
                "समझ गया। Northstar One के बारे में मैं आपसे दोबारा संपर्क नहीं करूँगा। धन्यवाद।",
            )

        if is_not_interested(lower):
            memory["not_interested"] = True
            state.ended = True
            return self.pick(
                state,
                "No problem. I will close this here. Thank you for your time.",
                "Koi baat nahi. Main yahin close kar deta hoon. Thank you.",
                "कोई बात नहीं। मैं बातचीत यहीं बंद कर देता हूँ। धन्यवाद।",
            )

        if is_busy(lower) or is_later_request(lower):
            state.ended = True
            return self.pick(
                state,
                f"Sure, I will mark a follow-up for {memory['follow_up_time']}. Thank you.",
                f"Theek hai, main {memory['follow_up_time']} ke liye follow-up mark kar deta hoon. Thank you.",
                f"ठीक है, मैं {memory['follow_up_time']} के लिए फॉलो-अप मार्क कर देता हूँ। धन्यवाद।",
            )

        if memory["unsupported_requirement"]:
            return self.pick(
                state,
                f"I only have verified information for 2 BHK and 3 BHK at Northstar One. I do not have verified details for {memory['unsupported_requirement']}. Would you like to know about 2 BHK or 3 BHK instead?",
                f"Mere paas Northstar One ke 2 BHK aur 3 BHK ki verified information hai. {memory['unsupported_requirement']} ke verified details mere paas nahi hain. Kya aap 2 BHK ya 3 BHK ke baare mein jaanna chahenge?",
                f"मेरे पास Northstar One के 2 BHK और 3 BHK की verified जानकारी है। {memory['unsupported_requirement']} की verified details मेरे पास नहीं हैं। क्या आप 2 BHK या 3 BHK के बारे में जानना चाहेंगे?",
            )

        if is_unrelated_question(lower):
            memory["out_of_scope"] = True
            return self.pick(
                state,
                "I can help with Northstar One by Northstar Homes. For this chat, I can answer project details, qualify your requirement, or help schedule a site visit.",
                "Main Northstar Homes ke Northstar One ke baare mein help kar sakta hoon. Is chat mein main project details, requirement qualification, ya site visit scheduling mein help karunga.",
                "मैं Northstar Homes के Northstar One के बारे में help कर सकता हूँ। इस chat में मैं project details, requirement qualification, या site visit scheduling में help करूँगा।",
            )

        if asks_human(lower):
            memory["human_escalation_required"] = True
            memory["follow_up_required"] = True
            if memory["phone"]:
                state.ended = True
                return self.pick(
                    state,
                    f"I have marked this for human follow-up. The Northstar Homes team will contact you on {memory['phone']}.",
                    f"Main human follow-up mark kar raha hoon. Northstar Homes team aapko {memory['phone']} par contact karegi.",
                    f"मैंने human follow-up मार्क कर दिया है। Northstar Homes टीम आपसे {memory['phone']} पर संपर्क करेगी।",
                )
            return self.pick(
                state,
                "Sure, I can connect you with the Northstar Homes team. Please share your phone number.",
                "Sure, main aapko Northstar Homes team se connect kara sakta hoon. Aap apna phone number share kar den.",
                "ज़रूर, मैं आपको Northstar Homes टीम से connect करा सकता हूँ। कृपया अपना फोन नंबर शेयर करें।",
            )

        if asks_unknown(lower):
            memory["human_escalation_required"] = True
            return self.pick(
                state,
                "I do not have verified details on that, so I should not guess. I can connect you with the Northstar Homes team for the exact information.",
                "Is detail ki verified information mere paas nahi hai, isliye main guess nahi karunga. Exact info ke liye main aapko Northstar Homes team se connect kara sakta hoon.",
                "मेरे पास इसकी verified जानकारी नहीं है, इसलिए मैं guess नहीं करूँगा। Exact जानकारी के लिए मैं आपको Northstar Homes टीम से connect करा सकता हूँ।",
            )

        if asks_price(lower):
            return self.pick(
                state,
                "Northstar One has 2 BHK starting at ₹1.35 crore onwards and 3 BHK starting at ₹1.75 crore onwards. Which configuration are you looking for?",
                "Northstar One mein 2 BHK ₹1.35 crore onwards hai aur 3 BHK ₹1.75 crore onwards hai. Aap 2 BHK dekh rahe hain ya 3 BHK?",
                "Northstar One में 2 BHK ₹1.35 crore onwards है और 3 BHK ₹1.75 crore onwards है। आप 2 BHK देख रहे हैं या 3 BHK?",
            )

        if asks_location(lower):
            return self.pick(
                state,
                "Northstar One is located in Sector 79, Gurugram. Are you looking for a 2 BHK or 3 BHK?",
                "Northstar One Sector 79, Gurugram mein located hai. Aap 2 BHK dekh rahe hain ya 3 BHK?",
                "Northstar One Sector 79, Gurugram में located है। आप 2 BHK देख रहे हैं या 3 BHK?",
            )

        if wants_site_visit(lower) or memory["site_visit_status"] == "requested":
            return self.handle_booking(state)

        if thanks_or_bye(lower):
            state.ended = True
            return self.pick(
                state,
                "Thank you for your time. Have a good day.",
                "Thank you. Aapka din achha rahe.",
                "धन्यवाद। आपका दिन अच्छा रहे।",
            )

        return self.next_qualification_reply(state)

    def handle_booking(self, state: ConversationState) -> str:
        memory = state.memory
        memory["site_visit_status"] = "requested"

        if not memory["name"]:
            return self.pick(
                state,
                "Sure, I can help with a site visit. Please share your name.",
                "Sure, main site visit mein help kar sakta hoon. Aap apna naam share kar den.",
                "ज़रूर, मैं site visit में help कर सकता हूँ। कृपया अपना नाम बताएं।",
            )

        if not memory["phone"]:
            return self.pick(
                state,
                f"Thanks, {memory['name']}. Please share your phone number for the site-visit booking.",
                f"Thanks, {memory['name']}. Site visit booking ke liye apna phone number share kar den.",
                f"धन्यवाद, {memory['name']}। Site visit booking के लिए कृपया अपना फोन नंबर शेयर करें।",
            )

        if not memory["site_visit_slot"]:
            return self.pick(
                state,
                "Please share your preferred date and time for the site visit.",
                "Aap site visit ke liye preferred date aur time share kar den.",
                "कृपया site visit के लिए अपनी preferred date और time बताएं।",
            )

        if slot_fails(memory["site_visit_slot"]):
            memory["site_visit_status"] = "failed"
            memory["follow_up_required"] = True
            memory["human_escalation_required"] = True
            state.ended = True
            return self.pick(
                state,
                "I could not book that slot because it looks unavailable for a site visit. I have marked this for human follow-up so the Northstar Homes team can suggest a better time.",
                "Main woh slot book nahi kar paaya kyunki site visit ke liye woh unavailable lag raha hai. Main human follow-up mark kar raha hoon taaki Northstar Homes team better time suggest kar sake.",
                "मैं वह slot book नहीं कर पाया क्योंकि site visit के लिए वह unavailable लग रहा है। मैंने human follow-up mark कर दिया है ताकि Northstar Homes team better time suggest कर सके।",
            )

        memory["site_visit_status"] = "confirmed"
        state.ended = True
        return self.pick(
            state,
            f"Your site visit for Northstar One is confirmed for {memory['site_visit_slot']}. Our team will contact you on {memory['phone']}. Thank you, {memory['name']}.",
            f"Aapki Northstar One site visit {memory['site_visit_slot']} ke liye confirm ho gayi hai. Hamari team aapko {memory['phone']} par contact karegi. Thank you, {memory['name']}.",
            f"आपकी Northstar One site visit {memory['site_visit_slot']} के लिए confirm हो गई है। हमारी team आपसे {memory['phone']} पर contact करेगी। धन्यवाद, {memory['name']}।",
        )

    def next_qualification_reply(self, state: ConversationState) -> str:
        memory = state.memory

        if not memory["configuration"]:
            return self.pick(
                state,
                "Are you looking for a 2 BHK or 3 BHK at Northstar One?",
                "Aap Northstar One mein 2 BHK dekh rahe hain ya 3 BHK?",
                "आप Northstar One में 2 BHK देख रहे हैं या 3 BHK?",
            )

        if not memory["budget"]:
            price = format_price(memory["configuration"])
            return self.pick(
                state,
                f"{memory['configuration']} starts from {price}. What budget range are you considering?",
                f"{memory['configuration']} {price} se start hota hai. Aapka budget range kya hai?",
                f"{memory['configuration']} {price} से start होता है। आपका budget range क्या है?",
            )

        if memory["budget_fit"] == "below_starting_price":
            return self.pick(
                state,
                f"The starting price for {memory['configuration']} is {format_price(memory['configuration'])}. Is your budget flexible, or should I arrange a human advisor call?",
                f"{memory['configuration']} ka starting price {format_price(memory['configuration'])} hai. Kya aapka budget flexible hai, ya main human advisor call arrange karun?",
                f"{memory['configuration']} का starting price {format_price(memory['configuration'])} है। क्या आपका budget flexible है, या मैं human advisor call arrange करूँ?",
            )

        if not memory["purpose"]:
            return self.pick(
                state,
                "Is this for self-use or investment?",
                "Ye self-use ke liye hai ya investment ke liye?",
                "यह self-use के लिए है या investment के लिए?",
            )

        if not memory["timeline"]:
            return self.pick(
                state,
                "By when are you planning to buy?",
                "Aap kab tak purchase plan kar rahe hain?",
                "आप कब तक purchase plan कर रहे हैं?",
            )

        return self.pick(
            state,
            "Thanks, this looks relevant. Would you like to schedule a site visit for Northstar One?",
            "Thanks, ye relevant lag raha hai. Kya aap Northstar One ki site visit schedule karna chahenge?",
            "धन्यवाद, यह relevant लग रहा है। क्या आप Northstar One की site visit schedule करना चाहेंगे?",
        )

    def analytics(self, state: ConversationState) -> dict[str, Any]:
        memory = state.memory
        interest_level = interest_level_for(memory)
        summary_parts = []

        if memory["configuration"]:
            summary_parts.append(f"interested in {memory['configuration']}")
        if memory["budget"]:
            summary_parts.append(f"budget {memory['budget']}")
        if memory["site_visit_status"] != "not_requested":
            summary_parts.append(f"site visit {memory['site_visit_status']}")
        if memory["follow_up_required"]:
            summary_parts.append("follow-up required")
        if memory["do_not_contact"]:
            summary_parts.append("do not contact")
        if memory["unsupported_requirement"]:
            summary_parts.append(f"asked for {memory['unsupported_requirement']}")
        if memory["out_of_scope"]:
            summary_parts.append("asked out-of-scope question")

        lead_summary = ", ".join(summary_parts) if summary_parts else "basic conversation only"

        return {
            "session_id": state.session_id,
            "ended": state.ended,
            "language": memory["language"],
            "name": memory["name"],
            "phone": memory["phone"],
            "configuration": memory["configuration"],
            "budget": memory["budget"],
            "budget_crore": memory["budget_crore"],
            "budget_fit": memory["budget_fit"],
            "purpose": memory["purpose"],
            "timeline": memory["timeline"],
            "customer_location": memory["customer_location"],
            "interest_level": interest_level,
            "site_visit_status": memory["site_visit_status"],
            "site_visit_slot": memory["site_visit_slot"],
            "follow_up_required": memory["follow_up_required"],
            "follow_up_time": memory["follow_up_time"],
            "human_escalation_required": memory["human_escalation_required"],
            "do_not_contact": memory["do_not_contact"],
            "unsupported_requirement": memory["unsupported_requirement"],
            "out_of_scope": memory["out_of_scope"],
            "lead_summary": lead_summary,
        }

    def pick(self, state: ConversationState, english: str, hinglish: str, hindi: str) -> str:
        language = state.memory.get("language", "english")
        if language == "hindi":
            return hindi
        if language == "hinglish":
            return hinglish
        return english


def detect_language(text: str, previous: str) -> str:
    lower = text.lower()
    if re.search(r"[\u0900-\u097f]", text):
        return "hindi"

    hinglish_words = {
        "kya",
        "hai",
        "haan",
        "nahi",
        "chahiye",
        "mujhe",
        "mera",
        "meri",
        "aap",
        "kal",
        "baad",
        "mein",
        "karna",
        "hoon",
        "batao",
    }
    words = set(re.findall(r"[a-z]+", lower))
    if words & hinglish_words:
        return "hinglish"

    return previous or "english"


def extract_name(text: str) -> str | None:
    patterns = [
        r"\bmy name is\s+([a-zA-Z][a-zA-Z ]{1,40})",
        r"\bi am\s+([a-zA-Z][a-zA-Z ]{1,40})",
        r"\bthis is\s+([a-zA-Z][a-zA-Z ]{1,40})",
        r"\bname\s+is\s+([a-zA-Z][a-zA-Z ]{1,40})",
        r"\bmera naam\s+([a-zA-Z][a-zA-Z ]{1,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            name = re.split(r"\s+(and|phone|number|mobile|budget|for)\b", match.group(1), flags=re.IGNORECASE)[0]
            return name.strip().title()
    return None


def extract_phone(text: str) -> str | None:
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 10:
        phone = digits[-10:]
        if phone[0] in "6789":
            return phone
    return None


def extract_configuration(lower: str) -> str | None:
    if re.search(r"\b(2|two)\s*-?\s*bhk\b|\b2bhk\b|दो", lower):
        return "2 BHK"
    if re.search(r"\b(3|three)\s*-?\s*bhk\b|\b3bhk\b|तीन", lower):
        return "3 BHK"
    return None


def extract_unsupported_requirement(lower: str) -> str | None:
    bhk_match = re.search(r"\b(\d+|one|four|five|six|seven|eight|nine|ten)\s*-?\s*bhk\b|\b(\d+)bhk\b", lower)
    if bhk_match:
        raw = next(group for group in bhk_match.groups() if group)
        words = {
            "one": "1",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
            "ten": "10",
        }
        value = words.get(raw, raw)
        if value not in {"2", "3"}:
            return f"{value} BHK"

    property_types = ["villa", "plot", "land", "studio", "penthouse", "independent house", "commercial"]
    for property_type in property_types:
        if property_type in lower:
            return property_type

    return None


def extract_budget(lower: str) -> tuple[str | None, float | None]:
    crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(cr|crore|crores|करोड़|करोड)", lower)
    if crore_match:
        value = float(crore_match.group(1))
        return f"{value:g} crore", value

    lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs)", lower)
    if lakh_match:
        value = float(lakh_match.group(1)) / 100
        return f"{float(lakh_match.group(1)):g} lakh", value

    return None, None


def extract_purpose(lower: str) -> str | None:
    if any(word in lower for word in ["self", "family", "live", "shift", "रहने"]):
        return "self-use"
    if any(word in lower for word in ["investment", "invest", "rental", "rent", "निवेश"]):
        return "investment"
    return None


def extract_timeline(lower: str) -> str | None:
    flexible_match = re.search(
        r"\b((?:within|in|next)\s+)?(\d{1,2})\s*(day|days|week|weeks|month|months|year|years)\b",
        lower,
    )
    if flexible_match:
        return flexible_match.group(0)

    patterns = [
        "immediate",
        "this month",
        "next month",
        "within 1 month",
        "within 3 months",
        "within 6 months",
        "3 months",
        "6 months",
        "this year",
        "अभी",
        "जल्दी",
    ]
    for pattern in patterns:
        if pattern in lower:
            return pattern
    return None


def extract_customer_location(text: str) -> str | None:
    match = re.search(r"\bfrom\s+([a-zA-Z][a-zA-Z ]{2,30})", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().title()
    return None


def extract_slot(text: str) -> str | None:
    lower = text.lower()
    slot_words = [
        "today",
        "tomorrow",
        "weekend",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "tonight",
        "morning",
        "evening",
        "kal",
        "aaj",
        "shaam",
        "subah",
        "रात",
        "कल",
        "आज",
    ]
    time_match = re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)\b", lower)
    date_match = re.search(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b", lower)
    if time_match or date_match or any(word in lower for word in slot_words):
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned[:120]
    return None


def wants_site_visit(lower: str) -> bool:
    return any(phrase in lower for phrase in ["site visit", "visit", "book", "schedule", "dekhna", "देखना", "विजिट"])


def is_stop_request(lower: str) -> bool:
    phrases = ["stop contacting", "do not contact", "don't contact", "unsubscribe", "remove my number", "no more calls", "mat call", "band karo"]
    return any(phrase in lower for phrase in phrases)


def is_not_interested(lower: str) -> bool:
    phrases = ["not interested", "no interest", "not looking", "nahi chahiye", "interested nahi", "मतलब नहीं"]
    return any(phrase in lower for phrase in phrases)


def is_busy(lower: str) -> bool:
    return any(word in lower for word in ["busy", "meeting", "driving", "kaam mein", "vyast", "busy hoon"])


def is_later_request(lower: str) -> bool:
    phrases = ["call later", "contact later", "later", "tomorrow call", "kal call", "baad mein", "bad me", "after some time"]
    return any(phrase in lower for phrase in phrases)


def asks_human(lower: str) -> bool:
    phrases = ["human", "sales person", "advisor", "agent", "representative", "call me", "team call", "connect me"]
    return any(phrase in lower for phrase in phrases)


def asks_unknown(lower: str) -> bool:
    topics = [
        "carpet",
        "floor plan",
        "floorplan",
        "possession",
        "rera",
        "maintenance",
        "discount",
        "offer",
        "availability",
        "available units",
        "payment plan",
        "emi",
        "loan",
        "amenities",
        "builder",
        "approval",
    ]
    return any(topic in lower for topic in topics)


def is_unrelated_question(lower: str) -> bool:
    topics = [
        "weather",
        "cricket",
        "movie",
        "song",
        "joke",
        "recipe",
        "food",
        "pizza",
        "politics",
        "stock market",
        "job opening",
        "interview question",
        "flight",
        "hotel",
    ]
    return any(topic in lower for topic in topics)


def asks_price(lower: str) -> bool:
    phrases = ["price", "cost", "rate", "budget", "kitna", "कितना", "कीमत"]
    return any(phrase in lower for phrase in phrases)


def asks_location(lower: str) -> bool:
    phrases = ["location", "where", "sector", "address", "located", "kahan", "कहाँ"]
    return any(phrase in lower for phrase in phrases)


def thanks_or_bye(lower: str) -> bool:
    return any(word in lower for word in ["thanks", "thank you", "bye", "goodbye", "dhanyawad", "shukriya"])


def budget_fit(memory: dict[str, Any]) -> str | None:
    config = memory.get("configuration")
    budget = memory.get("budget_crore")
    if not config or not budget:
        return None
    if budget >= PROJECT["prices"][config]:
        return "matches_starting_price"
    return "below_starting_price"


def format_price(config: str) -> str:
    if config == "2 BHK":
        return "₹1.35 crore onwards"
    return "₹1.75 crore onwards"


def slot_fails(slot: str) -> bool:
    lower = slot.lower()
    fail_words = ["fail", "unavailable", "full", "fully booked", "night", "tonight", "raat", "रात"]
    if any(word in lower for word in fail_words):
        return True
    return bool(re.search(r"\b(7|8|9|10|11|12)\s*(pm|p\.m\.)\b|\b(12|1|2|3|4|5|6)\s*(am|a\.m\.)\b", lower))


def interest_level_for(memory: dict[str, Any]) -> str:
    if memory["do_not_contact"] or memory["not_interested"]:
        return "low"
    if memory["site_visit_status"] == "confirmed":
        return "high"
    if memory["site_visit_status"] in {"requested", "failed"}:
        return "medium"
    if memory["configuration"] and memory["budget"]:
        return "medium"
    return "unknown"
