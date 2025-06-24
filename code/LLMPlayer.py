import os
import json
import re # For stripping markdown
from player import player
from google import genai


class LLMPlayer(player):
    def __init__(self, playerName, playerColor, llm_type):
        super().__init__(playerName, playerColor)
        self.llm_type = llm_type
        self.thoughts = ""
        self.gemini_client = None # Changed from self.gemini_model

    def _strip_markdown_json(self, text_response):
        # Check if the response is wrapped in markdown JSON backticks
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text_response)
        if match:
            return match.group(1) # Extract the JSON content
        return text_response # Return original if no markdown wrapper

    def _construct_prompt(self, game_state_obj):
        game_state_json = game_state_obj.to_json() # Serialize here for the prompt content

        previous_action_feedback = ""
        if hasattr(game_state_obj, 'last_action_status') and game_state_obj.last_action_status:
            previous_action_feedback = f"Feedback on your last attempt: Status: {game_state_obj.last_action_status}."
            if hasattr(game_state_obj, 'last_action_error_details') and game_state_obj.last_action_error_details:
                previous_action_feedback += f" Details: {game_state_obj.last_action_error_details}."
            previous_action_feedback += " Please try a different valid action or correct your previous one.\n"

        # Communication Phase Related Instructions
        communication_instructions = ""
        private_chat_instructions = ""

        if hasattr(game_state_obj, 'private_chat_active') and game_state_obj.private_chat_active:
            # Determine who the other participant is. The private_chat_history should contain this.
            other_participant_name = "the other player"
            if game_state_obj.private_chat_history and game_state_obj.private_chat_history[0]["participants"]:
                current_player_name = game_state_obj.current_player_name
                participants = game_state_obj.private_chat_history[0]["participants"]
                other_participant_name = next((p for p in participants if p != current_player_name), "the other player")

            instructions = f"You are in a private chat with {other_participant_name}. Continue the conversation or end the chat. Focus on this private interaction."
            possible_actions = (f"Your possible actions are: send_private_message (to {other_participant_name}), "
                                f"accept_trade (if a trade was implicitly or explicitly offered and you agree), "
                                f"end_private_chat (with {other_participant_name}). "
                                "You can also propose a standard game action like 'propose_trade' if relevant to the discussion, "
                                "but 'send_private_message' is for general chat.")
            example_actions = [
                {"thoughts": "I need to clarify their offer.", "action": {"type": "send_private_message", "recipient_name": other_participant_name, "message": "Can you offer one more WHEAT?"}},
                {"thoughts": "Their last message makes sense, I will accept the trade they outlined.", "action": {"type": "accept_trade"}}, # Assuming trade context is clear
                {"thoughts": "I think we are done talking for now.", "action": {"type": "end_private_chat", "recipient_name": other_participant_name}}
            ]
            private_chat_instructions = "The game state includes 'private_chat_history' with your current conversation.\n"

        elif hasattr(game_state_obj, 'communication_phase_active') and game_state_obj.communication_phase_active:
            instructions = "It is the Communication Phase. You can send a global message to all players."
            possible_actions = "Your possible actions are: send_global_message, end_turn (to say nothing)."
            example_actions = [
                {"thoughts": "I want to announce my intentions.", "action": {"type": "send_global_message", "message": "Hello everyone! I am planning to expand towards the ore port."}},
                {"thoughts": "I have nothing to say right now.", "action": {"type": "end_turn"}}
            ]
            communication_instructions = "The game state includes 'global_chat_history' with the last 10 messages.\n"
        else: # Standard turn
            instructions = "Your turn to make a move. Analyze the game state and decide on the best action."
            possible_actions = ("Your possible actions are: build_road, build_settlement, build_city, buy_development_card, "
                                "trade_with_bank, propose_trade (this is for player-to-player trades outside of dedicated private chat), "
                                "initiate_private_chat (to start a 1-on-1 conversation with another LLM player for negotiation), "
                                "send_global_message, end_turn.")
            example_actions = [
                {"thoughts": "I should build a road to expand.", "action": {"type": "build_road", "v1_index": 0, "v2_index": 1}},
                {"thoughts": "I want to build a settlement at vertex 5.", "action": {"type": "build_settlement", "vertex_index": 5}},
                {"thoughts": "I want to discuss a trade with Player2-AI.", "action": {"type": "initiate_private_chat", "recipient_name": "Player2-AI-Name", "opening_message": "Hey, I'm interested in your ORE. What would you want for it?"}},
                {"thoughts": "I want to make a public statement.", "action": {"type": "send_global_message", "message": "I am looking for WHEAT, willing to trade ORE."}},
                {"thoughts": "I will end my turn.", "action": {"type": "end_turn"}}
            ]

        # Specific instructions based on game state take precedence (unless in communication or private chat phase where it's already handled)
        if not (hasattr(game_state_obj, 'private_chat_active') and game_state_obj.private_chat_active) and \
           not (hasattr(game_state_obj, 'communication_phase_active') and game_state_obj.communication_phase_active):
            if hasattr(game_state_obj, 'robber_movement_is_mandatory') and game_state_obj.robber_movement_is_mandatory:
                instructions = "A 7 was rolled and you MUST move the robber. This is your only action for this specific decision."
                possible_actions = "Your ONLY action for this decision must be: move_robber. Consult 'available_actions' in the game state for valid hex indices to move the robber to (generally any hex not currently occupied by the robber)."
            example_actions = [
                {"thoughts": "I need to move the robber. I'll choose hex 10 and target Player X if available.", "action": {"type": "move_robber", "hex_index": 10, "player_to_rob_name": "PlayerX_Name_Or_Null"}}
            ]
        elif hasattr(game_state_obj, 'discard_is_mandatory') and game_state_obj.discard_is_mandatory:
            num_to_discard = game_state_obj.num_cards_to_discard
            instructions = f"You rolled a 7 and have too many cards. You MUST discard {num_to_discard} resource cards in total. This is your only action for this specific decision."
            possible_actions = "Your ONLY action for this decision must be: discard_cards. Provide the resources to discard in a dictionary format, ensuring the sum of values equals the required discard number."

            # Construct a simple, generic example for the discard action's structure
            example_resource_breakdown = {}
            if num_to_discard == 1:
                example_resource_breakdown = {"WOOD": 1} # Or any single resource type
            elif num_to_discard == 2:
                example_resource_breakdown = {"WOOD": 1, "SHEEP": 1}
            elif num_to_discard > 2:
                # Example: discard 1 of two types, and the rest of a third, or similar simple structure
                example_resource_breakdown = {"WOOD": 1, "SHEEP": 1, "BRICK": num_to_discard - 2}
                if num_to_discard - 2 <= 0: # handles num_to_discard = 2 already covered, but as safeguard
                    example_resource_breakdown = {"WOOD": num_to_discard // 2, "SHEEP": num_to_discard - (num_to_discard // 2)}

            example_actions = [
                {"thoughts": f"I must discard {num_to_discard} cards. I will choose from the resources I currently possess (e.g., WOOD, SHEEP, BRICK), making sure the total number of cards discarded is exactly {num_to_discard}. The specific resources I choose will depend on what I have and my strategy.",
                 "action": {"type": "discard_cards", "resources": example_resource_breakdown }}
            ]

        elif hasattr(game_state_obj, 'trade_offer_pending') and game_state_obj.trade_offer_pending:
            offering_player = game_state_obj.trade_offering_player_name
            offered_res = game_state_obj.trade_resources_offered_to_you
            requested_res = game_state_obj.trade_resources_requested_from_you
            instructions = (f"Player {offering_player} has proposed a trade with you. "
                            f"They are offering you: {json.dumps(offered_res)}. "
                            f"They are requesting from you: {json.dumps(requested_res)}. "
                            "You must decide to 'accept_trade' or 'reject_trade'. This is your only action for this decision.")
            possible_actions = "Your ONLY actions for this decision are: accept_trade, reject_trade."
            example_actions = [
                {"thoughts": "This trade benefits me, I have the resources they want and need what they offer.", "action": {"type": "accept_trade"}},
                {"thoughts": "This trade is not good for me.", "action": {"type": "reject_trade"}}
            ]

        elif hasattr(game_state_obj, 'setup_road_placement_pending') and game_state_obj.setup_road_placement_pending and hasattr(game_state_obj, 'last_settlement_vertex_index'):
            last_settlement_v_idx = game_state_obj.last_settlement_vertex_index
            instructions = f"You have just placed a settlement at vertex {last_settlement_v_idx}. You MUST now build a road connected to this new settlement. This is your only action."
            possible_actions = "Your ONLY action for this decision must be: build_road."
            # Find a valid neighbor for the example. This is tricky without full board access here.
            # We'll use a placeholder. The LLM should use available_road_locations from game_state.
            example_v2_idx = "any_valid_neighbor_of_" + str(last_settlement_v_idx)
            # Try to get a valid neighbor from available_road_locations if present in game_state_obj
            if hasattr(game_state_obj, 'available_actions') and 'build_road' in game_state_obj.available_actions:
                if game_state_obj.available_actions['build_road']: # Check if list is not empty
                    # Assuming available_actions['build_road'] is a list of tuples like [(v1,v2), ...]
                    # And we need to find one where v1 or v2 is last_settlement_v_idx
                    for r_v1, r_v2 in game_state_obj.available_actions['build_road']:
                        if r_v1 == last_settlement_v_idx:
                            example_v2_idx = r_v2
                            break
                        elif r_v2 == last_settlement_v_idx:
                            # Ensure the example uses last_settlement_v_idx as v1_index if it's not already
                            # This is just for consistency in the example.
                            example_v2_idx = r_v1 # The other end of the road
                            break
            example_actions = [
                {"thoughts": f"I just built a settlement at vertex {last_settlement_v_idx}. Now I must build an adjacent road. I will connect it to vertex {example_v2_idx}.", "action": {"type": "build_road", "v1_index": last_settlement_v_idx, "v2_index": example_v2_idx}}
            ]


        # Construct example string
        example_str = "For example: " + json.dumps(example_actions[0])
        if len(example_actions) > 1:
            example_str += "\nAnother example: " + json.dumps(example_actions[1])


        return f"""
You are an expert Settlers of Catan player. Here is the current game state:
{game_state_json}

{previous_action_feedback}{communication_instructions}{private_chat_instructions}{instructions}
{possible_actions}
Refer to the 'available_actions' section within the game state JSON to see currently valid locations for building (if applicable to current phase).
The 'action_costs' section lists the resource costs for standard building actions (if applicable).
The 'current_player_bank_trade_ratios' section details your current exchange rates with the bank, including any port benefits. Use this when considering a 'trade_with_bank' action (if applicable).
Provide your reasoning in a 'thoughts' field and the chosen action in an 'action' field in JSON format.
{example_str}
Ensure your entire response is a single valid JSON object.
"""

    def get_llm_move(self, game_state): # game_state is an instance of modelState
        # Pass the game_state object directly to _construct_prompt
        prompt = self._construct_prompt(game_state)
        llm_response_json_str = None
        raw_llm_response_text_for_thoughts = "" # Store raw text for thoughts if JSON parsing fails

        if self.llm_type != 'gemini':
            # ... (existing placeholder logic for non-Gemini LLMs for mandatory actions) ...
            if hasattr(game_state, 'robber_movement_is_mandatory') and game_state.robber_movement_is_mandatory:
                self.thoughts = f"{self.llm_type} placeholder: Mandatory robber move. Moving to hex 10."
                other_player_name = None
                if hasattr(game_state, 'players'):
                    for p_state in game_state.players:
                        if p_state['name'] != self.name:
                            other_player_name = p_state['name']
                            break
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "move_robber", "hex_index": 10, "player_to_rob_name": other_player_name}})
            elif hasattr(game_state, 'discard_is_mandatory') and game_state.discard_is_mandatory:
                num_to_discard = game_state.num_cards_to_discard
                self.thoughts = f"{self.llm_type} placeholder: Must discard {num_to_discard} cards. Will pick randomly from own resources."

                my_resources_dict = {}
                if hasattr(game_state, 'players'):
                    for p_state in game_state.players:
                        if p_state['name'] == self.name:
                            my_resources_dict = p_state['resources']
                            break

                resources_to_discard_placeholder = {}
                if num_to_discard > 0 and my_resources_dict:
                    # Create a flat list of all available cards
                    available_cards_flat = []
                    for resource, count in my_resources_dict.items():
                        available_cards_flat.extend([resource] * count)

                    # Shuffle and pick num_to_discard
                    import random
                    random.shuffle(available_cards_flat)

                    cards_chosen_for_discard = available_cards_flat[:num_to_discard]

                    # Count them up for the JSON structure
                    for card in cards_chosen_for_discard:
                        resources_to_discard_placeholder[card] = resources_to_discard_placeholder.get(card, 0) + 1

                # Safety check: if somehow the above failed or not enough cards, this will result in an empty dict,
                # which AIGame.py's validation will catch and use _execute_random_discard.
                # This is better than the previous complex logic that might create invalid discards.
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "discard_cards", "resources": resources_to_discard_placeholder}})

        if llm_response_json_str is None: # Process this block if it's Gemini OR other LLM with no mandatory action
            if self.llm_type == 'gemini':
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    self.thoughts = "Gemini API Key not found. Please set GEMINI_API_KEY."
                    print(f"ERROR FOR {self.name}: {self.thoughts}")
                    llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})
                else:
                    if not self.gemini_client: # Initialize client if not already done
                        try:
                            # No genai.configure needed if using genai.Client directly with api_key
                            self.gemini_client = genai.Client(api_key=api_key)
                            print(f"Gemini client initialized for {self.name}")
                        except Exception as e:
                            self.thoughts = f"Failed to initialize Gemini client: {e}"
                            print(f"ERROR FOR {self.name}: {self.thoughts}")
                            llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})
                            self.gemini_client = None

                    if self.gemini_client:
                        print(f"Attempting Gemini API call for {self.name} using genai.Client pattern...")
                        try:
                            # Using client.models.generate_content as per user feedback
                            # Model name can be 'gemini-pro' or user's 'gemini-1.5-flash' (or 'gemini-1.5-pro-latest')
                            # For safety, stick to 'gemini-pro' if 'gemini-2.5-flash' is not a generally available model name.
                            # The google-generativeai library typically uses 'gemini-pro' or 'gemini-1.0-pro' or 'gemini-1.5-pro-latest'.
                            # Let's use 'gemini-pro' as a default.
                            current_gemini_model_name = "gemini-2.5-flash-lite-preview-06-17"
                            # print(f"GEMINI PROMPT for {self.name} (model: {current_gemini_model_name}):\n{prompt}") # For debugging
                            response = self.gemini_client.models.generate_content(
                                model=f"models/{current_gemini_model_name}", # Model name might need "models/" prefix
                                contents=[prompt], # Contents should be a listAdd commentMore actions
                                config={
                                    "response_mime_type": "application/json",
                                    "response_schema": {
                                        "type": "object",
                                        "properties": {
                                            "thoughts": {"type": "string"},
                                            "action": {
                                                "type": "object",
                                                "properties": {
                                                    "type": {"type": "string"},
                                                    "v1_index": {"type": "integer"}, # For roads
                                                    "v2_index": {"type": "integer"}, # For roads
                                                    "vertex_index": {"type": "integer"}, # For settlements/cities
                                                    "hex_index": {"type": "integer"}, # For robber
                                                    "player_to_rob_name": {"type": "string"}, # For robber
                                                    "resources": { # For discarding or trading
                                                        "type": "object",
                                                        "properties": {
                                                            "WOOD": {"type": "integer"},
                                                            "BRICK": {"type": "integer"},
                                                            "SHEEP": {"type": "integer"},
                                                            "WHEAT": {"type": "integer"},
                                                            "ORE": {"type": "integer"}
                                                        }
                                                    },
                                                    "resource_to_give": {"type": "string"}, # For bank trade
                                                    "resource_to_receive": {"type": "string"}, # For bank trade
                                                    "partner_player_name": {"type": "string"}, # For propose_trade
                                                    "resources_offered": {"type": "object"},   # For propose_trade
                                                    "resources_requested": {"type": "object"}, # For propose_trade
                                                    "recipient_name": {"type": "string"},      # For private chat actions
                                                    "opening_message": {"type": "string"},     # For initiate_private_chat
                                                    "message": {"type": "string"}              # For send_global_message, send_private_message
                                                },
                                                "required": ["type"]
                                            }
                                        },
                                        "required": ["thoughts", "action"]
                                    }
                                } # Contents should be a list
                            )

                            # Check for blocking (though structure might differ with genai.Client)
                            # Accessing prompt_feedback might be different.
                            # For now, let's assume if response object exists, it wasn't immediately blocked.
                            # If response.text is empty or an error, it will be caught by later checks or JSON parsing.
                            # A more robust check for specific block reasons might be needed after testing.

                            raw_llm_response_text_for_thoughts = response.text
                            llm_response_json_str = self._strip_markdown_json(raw_llm_response_text_for_thoughts)
                            self.thoughts = f"Gemini ({self.name}) response: {llm_response_json_str[:200]}..."
                            print(f"SUCCESS: Gemini API call for {self.name} completed using genai.Client.")
                        except Exception as e:
                            self.thoughts = f"Error during Gemini API call for {self.name} (genai.Client): {e}"
                            print(f"ERROR FOR {self.name}: {self.thoughts}")
                            llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})

            elif self.llm_type == 'chatgpt': # Fallback to other LLM placeholders
                self.thoughts = "ChatGPT placeholder: Thinking about building a road 0-1."
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "build_road", "v1_index": 0, "v2_index": 1}})
            # ... (other placeholders for claude, deepseek) ...
            elif self.llm_type == 'claude':
                self.thoughts = "Claude placeholder: I will buy a development card."
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "buy_development_card"}})
            elif self.llm_type == 'deepseek':
                self.thoughts = "Deepseek placeholder: Ending my turn as a default action."
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})
            else:
                self.thoughts = f"Unknown LLM type ({self.llm_type}). Ending turn by default."
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})

        # Parse the LLM's JSON response string (common for all LLMs)
        try:
            if llm_response_json_str is None:
                print(f"CRITICAL ERROR: llm_response_json_str is None for {self.name} before parsing.")
                self.thoughts = "Internal error: No response string generated."
                return {"type": "end_turn"}

            parsed_response = json.loads(llm_response_json_str)
            self.thoughts = parsed_response.get("thoughts", self.thoughts) # Update with parsed thoughts if available
            return parsed_response.get("action", {"type": "end_turn"})
        except json.JSONDecodeError:
            # If JSON decoding fails, self.thoughts should ideally contain the raw problematic string (raw_llm_response_text_for_thoughts for Gemini)
            # or the placeholder thought if it was a placeholder that failed.
            # The self.thoughts might have already been set by the Gemini API call block if it was a Gemini error.
            # If it was another LLM's placeholder that was malformed, this helps.
            error_message = f"Error decoding JSON from {self.llm_type}."
            if self.llm_type == 'gemini' and raw_llm_response_text_for_thoughts: # Specifically for Gemini, ensure raw response is in thoughts
                 self.thoughts = f"Gemini Error: Failed to decode JSON. Raw response: '{raw_llm_response_text_for_thoughts}'"
            elif llm_response_json_str: # For other LLMs or if raw_llm_response_text_for_thoughts was not set
                 self.thoughts = f"Error: Failed to decode JSON. Raw content: '{llm_response_json_str}'"
            else: # Should not happen if llm_response_json_str None check passed
                 self.thoughts = error_message

            print(f"{error_message} Raw content: '{llm_response_json_str}'")
            return {"type": "end_turn"}

if __name__ == '__main__':
    print("LLMPlayer class defined. Not intended for direct execution without a game context.")
    # Example usage would require mock modelState, player.py etc.
    # class MockModelState:
    #     def to_json(self):
    #         return json.dumps({"board": "mock_board_data", "players": [], "current_player_name": "Test", "game_phase": "main"})

    # test_player_chatgpt = LLMPlayer("ChatGPT-AI", "Red", "chatgpt")
    # mock_game_state = MockModelState()
    # action_obj = test_player_chatgpt.get_llm_move(mock_game_state)
    # print(f"Player: {test_player_chatgpt.name}, Thoughts: {test_player_chatgpt.thoughts}, Action: {action_obj}")

    # test_player_gemini = LLMPlayer("Gemini-AI", "Blue", "gemini")
    # action_obj = test_player_gemini.get_llm_move(mock_game_state)
    # print(f"Player: {test_player_gemini.name}, Thoughts: {test_player_gemini.thoughts}, Action: {action_obj}")
