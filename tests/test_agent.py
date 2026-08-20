import unittest

from app.agent import NorthstarAgent


class NorthstarAgentTests(unittest.TestCase):
    def test_english_booking_success(self):
        agent = NorthstarAgent()
        first = agent.chat("I am interested in 3 BHK")
        session_id = first["session_id"]
        agent.chat("My budget is 1.8 crore", session_id)
        result = agent.chat("Book a site visit tomorrow 4 pm. My name is Rahul and my phone is 9876543210", session_id)

        self.assertTrue(result["ended"])
        self.assertIn("confirmed", result["reply"].lower())
        self.assertEqual(result["analytics"]["configuration"], "3 BHK")
        self.assertEqual(result["analytics"]["budget_fit"], "matches_starting_price")
        self.assertEqual(result["analytics"]["site_visit_status"], "confirmed")
        self.assertEqual(result["analytics"]["interest_level"], "high")

    def test_booking_failure(self):
        agent = NorthstarAgent()
        first = agent.chat("I want 2 BHK")
        session_id = first["session_id"]
        result = agent.chat("Book visit tonight 9 pm. My name is Ankit and phone is 9876543211", session_id)

        self.assertTrue(result["ended"])
        self.assertIn("could not book", result["reply"].lower())
        self.assertEqual(result["analytics"]["site_visit_status"], "failed")
        self.assertTrue(result["analytics"]["human_escalation_required"])
        self.assertTrue(result["analytics"]["follow_up_required"])

    def test_hinglish_price_and_later(self):
        agent = NorthstarAgent()
        first = agent.chat("price kya hai")
        self.assertIn("₹1.35 crore", first["reply"])
        self.assertEqual(first["analytics"]["language"], "hinglish")

        result = agent.chat("main busy hoon kal call karna", first["session_id"])
        self.assertTrue(result["ended"])
        self.assertTrue(result["analytics"]["follow_up_required"])
        self.assertEqual(result["analytics"]["interest_level"], "unknown")

    def test_stop_communication(self):
        agent = NorthstarAgent()
        result = agent.chat("Stop contacting me")

        self.assertTrue(result["ended"])
        self.assertTrue(result["analytics"]["do_not_contact"])
        self.assertEqual(result["analytics"]["interest_level"], "low")

    def test_unknown_question_does_not_invent(self):
        agent = NorthstarAgent()
        result = agent.chat("What is the carpet area and RERA number?")

        self.assertIn("do not have verified details", result["reply"])
        self.assertTrue(result["analytics"]["human_escalation_required"])
        self.assertIsNone(result["analytics"]["configuration"])

    def test_unsupported_configuration(self):
        agent = NorthstarAgent()
        result = agent.chat("do you have flat of 5 bhk")

        self.assertIn("2 BHK and 3 BHK", result["reply"])
        self.assertEqual(result["analytics"]["unsupported_requirement"], "5 BHK")
        self.assertIsNone(result["analytics"]["configuration"])

    def test_unrelated_question(self):
        agent = NorthstarAgent()
        result = agent.chat("Who won the cricket match yesterday?")

        self.assertIn("Northstar One", result["reply"])
        self.assertTrue(result["analytics"]["out_of_scope"])

    def test_timeline_accepts_two_months(self):
        agent = NorthstarAgent()
        first = agent.chat("3 BHK")
        session_id = first["session_id"]
        agent.chat("3 crore", session_id)
        agent.chat("self", session_id)
        result = agent.chat("2 months", session_id)

        self.assertEqual(result["analytics"]["timeline"], "2 months")
        self.assertIn("site visit", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
