import os
import json
import re # For stripping markdown
from player import player
import google.generativeai as genai

class LLMPlayer(player):
    def __init__(self, playerName, playerColor, llm_type):
        super().__init__(playerName, playerColor)
        self.llm_type = llm_type
        self.thoughts = ""
        self.gemini_model = None

    def _strip_markdown_json(self, text_response):
        # Check if the response is wrapped in markdown JSON backticks
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text_response)
        if match:
            return match.group(1) # Extract the JSON content
        return text_response # Return original if no markdown wrapper

    def _construct_prompt(self, game_state_obj):
        game_state_json = game_state_obj.to_json() # Serialize here for the prompt content

        instructions = "Your turn to make a move. Analyze the game state and decide on the best action."
        possible_actions = "Your possible actions are: build_road, build_settlement, build_city, buy_development_card, trade_with_bank, end_turn."
        example_actions = [
            {"thoughts": "I should build a road to expand.", "action": {"type": "build_road", "v1_index": 0, "v2_index": 1}},
            {"thoughts": "I will end my turn.", "action": {"type": "end_turn"}}
        ]

        if hasattr(game_state_obj, 'robber_movement_is_mandatory') and game_state_obj.robber_movement_is_mandatory:
            instructions = "A 7 was rolled and you must move the robber. This is your only action for this specific decision."
            possible_actions = "Your ONLY action for this decision must be: move_robber."
            example_actions = [
                {"thoughts": "I need to move the robber. I'll choose hex 10 and target Player X if available.", "action": {"type": "move_robber", "hex_index": 10, "player_to_rob_name": "PlayerX_Name_Or_Null"}}
            ]
        elif hasattr(game_state_obj, 'discard_is_mandatory') and game_state_obj.discard_is_mandatory:
            num_to_discard = game_state_obj.num_cards_to_discard
            instructions = f"You rolled a 7 and have too many cards. You MUST discard {num_to_discard} resources. This is your only action for this specific decision."
            possible_actions = "Your ONLY action for this decision must be: discard_cards."
            example_actions = [
                {"thoughts": f"I must discard {num_to_discard} cards. I'll discard some wood and sheep.", "action": {"type": "discard_cards", "resources": {"WOOD": 1, "SHEEP": 1}}} # Example, actual counts must sum to num_to_discard
            ]

        # Construct example string
        example_str = "For example: " + json.dumps(example_actions[0])
        if len(example_actions) > 1:
            example_str += "\nAnother example: " + json.dumps(example_actions[1])


        return f"""
You are an expert Settlers of Catan player. Here is the current game state:
{game_state_json}

{instructions}
{possible_actions}
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
                other_player_name = None; # ... (find other player logic as before)
                if hasattr(game_state, 'players'):
                    for p_state in game_state.players:
                        if p_state['name'] != self.name: other_player_name = p_state['name']; break
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "move_robber", "hex_index": 10, "player_to_rob_name": other_player_name}})
            elif hasattr(game_state, 'discard_is_mandatory') and game_state.discard_is_mandatory:
                num_to_discard = game_state.num_cards_to_discard
                self.thoughts = f"{self.llm_type} placeholder: Must discard {num_to_discard} cards."
                resources_to_discard_placeholder = {}; # ... (simplified discard placeholder logic as before) ...
                temp_discard_count = 0; my_resources = {}
                for p_state in game_state.players:
                    if p_state['name'] == self.name: my_resources = p_state['resources']; break
                for res, count in my_resources.items():
                    if count > 0 and temp_discard_count < num_to_discard : resources_to_discard_placeholder[res] = 1; temp_discard_count += 1
                    if temp_discard_count == num_to_discard: break
                if temp_discard_count < num_to_discard and resources_to_discard_placeholder:
                    first_res_key = list(resources_to_discard_placeholder.keys())[0]; resources_to_discard_placeholder[first_res_key] += (num_to_discard - temp_discard_count)
                if not resources_to_discard_placeholder and num_to_discard > 0 :
                     for res, count in my_resources.items():
                        if count >= num_to_discard: resources_to_discard_placeholder[res] = num_to_discard; break
                        elif count > 0 : resources_to_discard_placeholder[res] = count; break
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "discard_cards", "resources": resources_to_discard_placeholder}})


        if llm_response_json_str is None: # Process this block if it's Gemini OR other LLM with no mandatory action
            if self.llm_type == 'gemini':
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    self.thoughts = "Gemini API Key not found. Please set GEMINI_API_KEY."
                    print(f"ERROR FOR {self.name}: {self.thoughts}")
                    llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})
                else:
                    if not self.gemini_model:
                        try:
                            genai.configure(api_key=api_key)
                            self.gemini_model = genai.GenerativeModel(model_name='gemini-pro')
                            print(f"Gemini model initialized for {self.name}")
                        except Exception as e:
                            self.thoughts = f"Failed to initialize Gemini model: {e}"
                            print(f"ERROR FOR {self.name}: {self.thoughts}")
                            llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})
                            self.gemini_model = None

                    if self.gemini_model:
                        print(f"Attempting Gemini API call for {self.name}...")
                        try:
                            response = self.gemini_model.generate_content(prompt)

                            if response.prompt_feedback.block_reason:
                                self.thoughts = f"Gemini API call blocked. Reason: {response.prompt_feedback.block_reason}"
                                print(f"WARNING FOR {self.name}: {self.thoughts}")
                                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})
                            else:
                                # Robustly get text, preferring candidates if available
                                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                                    raw_llm_response_text_for_thoughts = response.candidates[0].content.parts[0].text
                                else:
                                    raw_llm_response_text_for_thoughts = response.text # Fallback if structure is simpler

                                llm_response_json_str = self._strip_markdown_json(raw_llm_response_text_for_thoughts)
                                # Store the (potentially stripped) response text for thoughts, might be updated by parsed JSON later
                                self.thoughts = f"Gemini ({self.name}) response: {llm_response_json_str[:200]}..."
                                print(f"SUCCESS: Gemini API call for {self.name} completed.")
                        except Exception as e:
                            self.thoughts = f"Error during Gemini API call for {self.name}: {e}"
                            print(f"ERROR FOR {self.name}: {self.thoughts}")
                            llm_response_json_str = json.dumps({"thoughts": self.thoughts, "action": {"type": "end_turn"}})

            # Fallback to other LLM placeholders if not Gemini and no mandatory action was handled above
            elif self.llm_type == 'chatgpt':
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
