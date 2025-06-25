import os
import json
import re # For stripping markdown
from player import player
from google import genai


class LLMPlayer(player):
    def __init__(self, playerName, playerColor, llm_type, persona=None): # Added persona
        super().__init__(playerName, playerColor)
        self.llm_type = llm_type
        self.thoughts = ""
        self.gemini_client = None # Changed from self.gemini_model
        self.feedback_status_for_next_state = None
        self.feedback_details_for_next_state = None
        self.memory = [] # Added memory attribute
        self.persona = persona # Added persona attribute
        self.max_memory_entries = 5 # Max recent memories to include in prompt

    def add_memory_entry(self, entry_summary: str):
        """Adds a new memory entry and keeps the list to a maximum size."""
        self.memory.append(entry_summary)
        if len(self.memory) > self.max_memory_entries:
            self.memory.pop(0) # Remove the oldest entry

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
        negotiation_instructions_text = "" # For the final prompt assembly

        # --- Negotiation State Handling ---
        if hasattr(game_state_obj, 'negotiation_in_progress') and game_state_obj.negotiation_in_progress and \
           hasattr(game_state_obj, 'your_turn_to_negotiate') and game_state_obj.your_turn_to_negotiate:

            partner_name = game_state_obj.negotiation_partner_name if hasattr(game_state_obj, 'negotiation_partner_name') else "the other player"

            instructions = (f"You are in a trade negotiation with {partner_name}. "
                            "Analyze the negotiation history and your resources to decide your next move. "
                            "You can accept the last offer, propose a counter-offer, or end the negotiation.")

            possible_actions = ("Your possible actions are: accept_trade, propose_counter_offer, end_negotiation.")

            # Example resources for counter-offer, make them simple and generic
            example_offer_res = {"WOOD": 1}
            example_request_res = {"BRICK": 1}
            if hasattr(game_state_obj, 'players'): # Try to get some actual resources for a more realistic example
                current_player_state = next((p for p in game_state_obj.players if p['name'] == game_state_obj.current_player_name), None)
                if current_player_state and sum(current_player_state['resources'].values()) > 0:
                    # Find first resource current player has to offer
                    for res, count in current_player_state['resources'].items():
                        if count > 0:
                            example_offer_res = {res: 1}
                            break
                # Find a resource the partner might have (simplistic: just pick a different one)
                other_player_state = next((p for p in game_state_obj.players if p['name'] == partner_name), None)
                if other_player_state: # and sum(other_player_state['resources'].values()) > 0 : # Cannot see partner's resources directly
                    # Just pick a resource different from what current player offers, if possible
                    all_res_types = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
                    offered_res_type = list(example_offer_res.keys())[0]
                    potential_request_types = [r for r in all_res_types if r != offered_res_type]
                    if potential_request_types:
                        example_request_res = {potential_request_types[0]: 1}


            example_actions = [
                {"thoughts": f"The last offer from {partner_name} is acceptable.", "long_term_plan": "Secure resources for my next build.", "action": {"type": "accept_trade"}},
                {"thoughts": f"I need more than what {partner_name} offered. I will propose a counter.", "long_term_plan": "Get a better deal or walk away.", "action": {"type": "propose_counter_offer", "resources_offered": example_offer_res, "resources_requested": example_request_res}},
                {"thoughts": "This negotiation is not going anywhere.", "long_term_plan": "Focus on other strategies.", "action": {"type": "end_negotiation", "reason": "The terms are not favorable."}}
            ]

            negotiation_history_json = json.dumps(game_state_obj.negotiation_history, indent=2)
            # Ensure negotiation_instructions_text is set here to be included in the prompt
            negotiation_instructions_text = (f"You are in a trade negotiation with {partner_name}.\n"
                                             f"The negotiation history so far is:\n{negotiation_history_json}\n")

        elif hasattr(game_state_obj, 'private_chat_active') and game_state_obj.private_chat_active:
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
                                "trade_with_bank, propose_trade (starts a formal negotiation session with another LLM player), "
                                "initiate_private_chat (for quick, informal chat, not for formal trades), "
                                "send_global_message, "
                                "offer_non_binding_deal (e.g., promise future resources for favorable robber placement), "
                                "request_embargo (propose to other players to stop trading with a leader), "
                                "share_information (e.g., warn about someone's imminent Longest Road), "
                                "end_turn.")
            example_actions = [
                {"thoughts": "I should build a road to expand.", "turn_plan": ["build_road", "end_turn"], "action": {"type": "build_road", "v1_index": 0, "v2_index": 1}},
                {"thoughts": "I want to build a settlement at vertex 5.", "turn_plan": ["build_settlement", "end_turn"], "action": {"type": "build_settlement", "vertex_index": 5}},
                {"thoughts": "I want to formally negotiate a trade for ORE with Player2-AI.", "turn_plan": ["propose_trade", "end_turn"], "action": {"type": "propose_trade", "partner_player_name": "Player2-AI-Name", "resources_offered": {"WOOD":1}, "resources_requested": {"ORE":1}}},
                {"thoughts": "I want to make a public statement.", "turn_plan": ["send_global_message", "end_turn"], "action": {"type": "send_global_message", "message": "I am looking for WHEAT, willing to trade ORE."}},
                {"thoughts": "I will offer PlayerX a deal if they don't rob me.", "turn_plan": ["offer_non_binding_deal", "end_turn"], "action": {"type": "offer_non_binding_deal", "target_player_name": "PlayerX", "deal_description": "If you do not place the robber on my hexes this turn, I will give you 1 SHEEP on my next turn."}},
                {"thoughts": "PlayerZ is too far ahead, I should try to embargo them.", "turn_plan": ["request_embargo", "end_turn"], "action": {"type": "request_embargo", "target_player_name": "PlayerZ", "reasoning": "PlayerZ has 8 VP and is close to winning."}},
                {"thoughts": "I should warn others about PlayerY's road.", "turn_plan": ["share_information", "end_turn"], "action": {"type": "share_information", "information": "PlayerY is one road away from Longest Road."}},
                {"thoughts": "I will end my turn.", "turn_plan": ["end_turn"], "action": {"type": "end_turn"}}
            ]

        # Specific instructions based on game state take precedence (unless in communication or private chat phase where it's already handled)
        if not (hasattr(game_state_obj, 'private_chat_active') and game_state_obj.private_chat_active) and \
           not (hasattr(game_state_obj, 'communication_phase_active') and game_state_obj.communication_phase_active):
            if hasattr(game_state_obj, 'robber_movement_is_mandatory') and game_state_obj.robber_movement_is_mandatory:
                instructions = "A 7 was rolled and you MUST move the robber. This is your only action for this specific decision."
                possible_actions = "Your ONLY action for this decision must be: move_robber. Consult 'available_actions' in the game state for valid hex indices to move the robber to (generally any hex not currently occupied by the robber)."
                example_actions = [ # Ensure this specific example also has turn_plan
                    {"thoughts": "I need to move the robber. I'll choose hex 10 and target Player X if available.", "long_term_plan": "Disrupt Player X's resource income.", "turn_plan": ["move_robber"], "action": {"type": "move_robber", "hex_index": 10, "player_to_rob_name": "PlayerX_Name_Or_Null"}}
                ]
            elif hasattr(game_state_obj, 'discard_is_mandatory') and game_state_obj.discard_is_mandatory:
                num_to_discard = game_state_obj.num_cards_to_discard
                instructions = f"You rolled a 7 and have too many cards. You MUST discard {num_to_discard} resource cards in total. This is your only action for this specific decision."
                possible_actions = "Your ONLY action for this decision must be: discard_cards. Provide the resources to discard in a dictionary format, ensuring the sum of values equals the required discard number."
                example_resource_breakdown = {}
                if num_to_discard == 1: example_resource_breakdown = {"WOOD": 1}
                elif num_to_discard == 2: example_resource_breakdown = {"WOOD": 1, "SHEEP": 1}
                else:
                    example_resource_breakdown = {"WOOD": 1, "SHEEP": 1, "BRICK": num_to_discard - 2} if num_to_discard > 2 else {"WOOD": num_to_discard // 2, "SHEEP": num_to_discard - (num_to_discard // 2)}
                example_actions = [ # Ensure this specific example also has turn_plan
                    {"thoughts": f"I must discard {num_to_discard} cards. I will choose from what I have to keep my options open.", "long_term_plan": "Minimize loss of valuable resources for city building.", "turn_plan": ["discard_cards"], "action": {"type": "discard_cards", "resources": example_resource_breakdown }}
                ]
            # Removed trade_offer_pending as it's now part of NegotiationManager flow
            elif hasattr(game_state_obj, 'setup_road_placement_pending') and game_state_obj.setup_road_placement_pending and hasattr(game_state_obj, 'last_settlement_vertex_index'):
                last_settlement_v_idx = game_state_obj.last_settlement_vertex_index
                instructions = f"You placed a settlement at vertex {last_settlement_v_idx}. You MUST now build a road connected to it."
                possible_actions = "Your ONLY action must be: build_road."
                example_v2_idx = "any_valid_neighbor_of_" + str(last_settlement_v_idx)
                if hasattr(game_state_obj, 'available_actions') and game_state_obj.available_actions.get('build_road'):
                    for r_v1, r_v2 in game_state_obj.available_actions['build_road']:
                        if r_v1 == last_settlement_v_idx: example_v2_idx = r_v2; break
                        elif r_v2 == last_settlement_v_idx: example_v2_idx = r_v1; break
                example_actions = [ # Ensure this specific example also has turn_plan
                    {"thoughts": f"Must build a road from {last_settlement_v_idx}. I'll connect to {example_v2_idx}.", "long_term_plan": "Expand towards the best available hexes.", "turn_plan": ["build_road"], "action": {"type": "build_road", "v1_index": last_settlement_v_idx, "v2_index": example_v2_idx}}
                ]


        # Ensure all example_actions include 'long_term_plan' and 'turn_plan'
        updated_example_actions = []
        for ex_action in example_actions:
            if "long_term_plan" not in ex_action:
                if hasattr(game_state_obj, 'private_chat_active') and game_state_obj.private_chat_active:
                     ex_action["long_term_plan"] = "Successfully negotiate or conclude this private chat."
                elif hasattr(game_state_obj, 'communication_phase_active') and game_state_obj.communication_phase_active:
                     ex_action["long_term_plan"] = "Effectively communicate my intentions or gather information."
                else:
                     ex_action["long_term_plan"] = "Advance my position towards winning the game."
            if "turn_plan" not in ex_action: # Add a default turn_plan if missing
                # Default turn plan is just the action itself, followed by end_turn if not already end_turn
                if ex_action["action"]["type"] == "end_turn":
                    ex_action["turn_plan"] = ["end_turn"]
                else:
                    ex_action["turn_plan"] = [ex_action["action"]["type"], "end_turn"]
            updated_example_actions.append(ex_action)
        example_actions = updated_example_actions


        # Construct example string
        example_str = "For example: " + json.dumps(example_actions[0])
        if len(example_actions) > 1: # Ensure there's a second example to show
            # Attempt to pick a different example if possible, or just the next one.
            # This logic needs to be careful if example_actions has only one item after specific phase filtering.
            # The goal is to ensure the prompt shows diverse examples.
            # The previous logic selected example_actions[0] and example_actions[1] from potentially different lists.
            # Now, example_actions should be the final list of examples for the current context.
            if len(example_actions) > 1:
                 example_str += "\nAnother example: " + json.dumps(example_actions[1])
            elif len(example_actions) == 1 and game_state_obj.game_phase == "main" and not (hasattr(game_state_obj, 'private_chat_active') and game_state_obj.private_chat_active) and not (hasattr(game_state_obj, 'communication_phase_active') and game_state_obj.communication_phase_active) and not (hasattr(game_state_obj, 'robber_movement_is_mandatory') and game_state_obj.robber_movement_is_mandatory) and not (hasattr(game_state_obj, 'discard_is_mandatory') and game_state_obj.discard_is_mandatory) and not (hasattr(game_state_obj, 'trade_offer_pending') and game_state_obj.trade_offer_pending) and not (hasattr(game_state_obj, 'setup_road_placement_pending') and game_state_obj.setup_road_placement_pending):
                # If it's a general turn and we only have one example (e.g. end_turn was the only one constructed),
                # try to add a more complex one like build_road for better illustration.
                # This is a bit of a patch to make the general prompt more illustrative.
                # This specific example needs to be crafted carefully.
                generic_build_example = {"thoughts": "I should build a road to expand.", "long_term_plan": "Reach a good hex.", "action": {"type": "build_road", "v1_index": 0, "v2_index": 1}}
                if example_actions[0]['action']['type'] != "build_road": # Avoid duplicate example types
                    example_str += "\nAnother example: " + json.dumps(generic_build_example)



        # --- Memory and Persona Section ---
        memory_prompt_section = ""
        if self.memory:
            # self.memory already contains the last N entries due to add_memory_entry logic
            recent_memories_str = "\n".join([f"- {mem}" for mem in self.memory])
            memory_prompt_section = f"Your Recent History (last {len(self.memory)} actions/events):\n{recent_memories_str}\n\n"

        persona_prompt_section = ""
        if self.persona:
            persona_guidance = {
                "Aggressive": "You are an 'Aggressive' player. Prioritize actions that disrupt opponents or secure critical resources, even at some cost to yourself.",
                "Hoarder": "You are a 'Hoarder' player. Focus on accumulating resources and building up a large hand. Be more reluctant to trade unless it's very favorable for you.",
                "Diplomat": "You are a 'Diplomat' player. Favor negotiation and trading with other players. Try to maintain good relations but always aim for your benefit through deals.",
                "Risk-Averse": "You are a 'Risk-Averse' player. Prefer safer bets, avoid risky early development card purchases, and prioritize steady, defensible growth."
                # Can add more personas here
            }
            if self.persona in persona_guidance:
                persona_prompt_section = persona_guidance[self.persona] + "\n\n"
            else: # Generic if persona string is custom/unknown but provided
                persona_prompt_section = f"Your guiding persona is: '{self.persona}'. Let this influence your decisions and play style.\n\n"

        return f"""
You are an expert Settlers of Catan player.
{persona_prompt_section}Here is the current game state:
{game_state_json}

{memory_prompt_section}{previous_action_feedback}{communication_instructions}{private_chat_instructions}{negotiation_instructions_text}{instructions}
{possible_actions}
Refer to the 'available_actions' section within the game state JSON to see currently valid locations for building (if applicable to current phase).
The 'action_costs' section lists the resource costs for standard building actions (if applicable).
The 'current_player_bank_trade_ratios' section details your current exchange rates with the bank, including any port benefits. Use this when considering a 'trade_with_bank' action (if applicable).
Provide your reasoning in a 'thoughts' field, your strategic goals for the next 2-3 turns in a 'long_term_plan' field (e.g., 'Secure ore access, build a city, then aim for longest road'), a 'turn_plan' field listing the sequence of actions you intend for this turn (e.g., ["propose_trade", "build_road", "end_turn"]), and the chosen action in an 'action' field in JSON format. The 'action' field should correspond to the *first applicable action* from your 'turn_plan'.
When communicating (global or private chat), you must base any statement about your resources or game state strictly on the information provided in the JSON. Do not hallucinate or misrepresent your hand.
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
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Disrupt opponent.", "turn_plan": ["move_robber"], "action": {"type": "move_robber", "hex_index": 10, "player_to_rob_name": other_player_name}})
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
                    available_cards_flat = []
                    for resource, count in my_resources_dict.items():
                        available_cards_flat.extend([resource] * count)
                    import random
                    random.shuffle(available_cards_flat)
                    cards_chosen_for_discard = available_cards_flat[:num_to_discard]
                    for card in cards_chosen_for_discard:
                        resources_to_discard_placeholder[card] = resources_to_discard_placeholder.get(card, 0) + 1
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Minimize resource loss.", "turn_plan": ["discard_cards"], "action": {"type": "discard_cards", "resources": resources_to_discard_placeholder}})

        if llm_response_json_str is None: # Process this block if it's Gemini OR other LLM with no mandatory action
            if self.llm_type == 'gemini':
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    self.thoughts = "Gemini API Key not found. Please set GEMINI_API_KEY."
                    print(f"ERROR FOR {self.name}: {self.thoughts}")
                    llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Error handling.", "turn_plan": ["end_turn"], "action": {"type": "end_turn"}})
                else:
                    if not self.gemini_client:
                        try:
                            self.gemini_client = genai.Client(api_key=api_key)
                            print(f"Gemini client initialized for {self.name}")
                        except Exception as e:
                            self.thoughts = f"Failed to initialize Gemini client: {e}"
                            print(f"ERROR FOR {self.name}: {self.thoughts}")
                            llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Error handling.", "turn_plan": ["end_turn"], "action": {"type": "end_turn"}})
                            self.gemini_client = None

                    if self.gemini_client:
                        print(f"Attempting Gemini API call for {self.name} using genai.Client pattern...")
                        try:
                            current_gemini_model_name = "gemini-2.5-flash" # User specified, ensure this model exists or use "gemini-1.5-flash-latest" / "gemini-1.5-pro-latest"
                            response = self.gemini_client.models.generate_content(
                                model=f"models/{current_gemini_model_name}",
                                contents=[prompt],
                                config={
                                    "response_mime_type": "application/json",
                                    "response_schema": {
                                        "type": "object",
                                        "properties": {
                                            "thoughts": {"type": "string"},
                                            "long_term_plan": {"type": "string"},
                                    "turn_plan": {"type": "array", "items": {"type": "string"}},
                                            "action": {
                                                "type": "object",
                                                "properties": {
                                                    "type": {"type": "string"},
                                            "v1_index": {"type": "integer"}, "v2_index": {"type": "integer"},
                                            "vertex_index": {"type": "integer"}, "hex_index": {"type": "integer"},
                                                    "player_to_rob_name": {"type": "string"},
                                            "resources": {"type": "object", "additionalProperties": {"type": "integer"}},
                                            "resource_to_give": {"type": "string"}, "resource_to_receive": {"type": "string"},
                                                    "partner_player_name": {"type": "string"},
                                            "resources_offered": {"type": "object", "additionalProperties": {"type": "integer"}},
                                            "resources_requested": {"type": "object", "additionalProperties": {"type": "integer"}},
                                            "recipient_name": {"type": "string"}, "opening_message": {"type": "string"},
                                            "message": {"type": "string"},
                                            # For advanced diplomatic actions
                                            "target_player_name": {"type": "string"}, # For offer_non_binding_deal, request_embargo
                                            "deal_description": {"type": "string"},   # For offer_non_binding_deal
                                            "reasoning": {"type": "string"},          # For request_embargo
                                            "information": {"type": "string"}         # For share_information
                                                },
                                                "required": ["type"]
                                            }
                                        },
                                "required": ["thoughts", "long_term_plan", "turn_plan", "action"]
                                    }
                                }
                            )
                            raw_llm_response_text_for_thoughts = response.text
                            llm_response_json_str = self._strip_markdown_json(raw_llm_response_text_for_thoughts)
                    self.thoughts = f"Gemini ({self.name}) response: {llm_response_json_str[:200]}..." # Truncate for print
                            print(f"SUCCESS: Gemini API call for {self.name} completed using genai.Client.")
                        except Exception as e:
                            self.thoughts = f"Error during Gemini API call for {self.name} (genai.Client): {e}"
                            print(f"ERROR FOR {self.name}: {self.thoughts}")
                            llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Error handling.", "turn_plan": ["end_turn"], "action": {"type": "end_turn"}})

            elif self.llm_type == 'chatgpt':
                self.thoughts = "ChatGPT placeholder: Thinking about building a road 0-1."
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Expand.", "turn_plan": ["build_road", "end_turn"], "action": {"type": "build_road", "v1_index": 0, "v2_index": 1}})
            elif self.llm_type == 'claude':
                self.thoughts = "Claude placeholder: I will buy a development card."
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Get VP cards.", "turn_plan": ["buy_development_card", "end_turn"], "action": {"type": "buy_development_card"}})
            elif self.llm_type == 'deepseek':
                self.thoughts = "Deepseek placeholder: Ending my turn as a default action."
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Save resources.", "turn_plan": ["end_turn"], "action": {"type": "end_turn"}})
            else:
                self.thoughts = f"Unknown LLM type ({self.llm_type}). Ending turn by default."
                llm_response_json_str = json.dumps({"thoughts": self.thoughts, "long_term_plan": "Default end turn.", "turn_plan": ["end_turn"], "action": {"type": "end_turn"}})

        try:
            if llm_response_json_str is None:
                # This case should ideally be caught by the API key / client init checks for Gemini,
                # or by placeholder logic for other LLMs.
                print(f"CRITICAL ERROR: llm_response_json_str is None for {self.name} before parsing. This indicates a failure in prior LLM call or placeholder logic.")
                self.thoughts = "Internal error: No response string generated by LLM or placeholder."
                # Return a minimal valid JSON structure to avoid crashing AIGame.py further down the line
                return {"type": "end_turn"}

            parsed_response = json.loads(llm_response_json_str)
            self.thoughts = parsed_response.get("thoughts", self.thoughts) # Keep thoughts if parsing fails but thoughts were set
            # We don't store turn_plan on self.player as it's per-move, but it's in the parsed_response
            return parsed_response.get("action", {"type": "end_turn"}) # Default to end_turn if action is missing
        except json.JSONDecodeError:
            error_message = f"Error decoding JSON from {self.llm_type}."
            # Use the most specific raw response available for debugging
            raw_content_for_debug = raw_llm_response_text_for_thoughts if self.llm_type == 'gemini' and raw_llm_response_text_for_thoughts else llm_response_json_str

            self.thoughts = f"JSON Decode Error: Failed to decode. Raw content: '{raw_content_for_debug}'"
            print(f"{error_message} Raw content for {self.name}: '{raw_content_for_debug}'")
            return {"type": "end_turn"}

if __name__ == '__main__':
    print("LLMPlayer class defined. Not intended for direct execution without a game context.")
