#Settlers of Catan
#Gameplay class with pygame with AI players

from board import *
from gameView import *
from player import *
from heuristicAIPlayer import *
from modelState import modelState
from LLMPlayer import LLMPlayer
from negotiation import NegotiationManager
from gamelogic import GameLogicManager # Added import
import queue
import numpy as np
import sys, pygame
import matplotlib.pyplot as plt

from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

#Class to implement an only AI
class catanAIGame():
    #Create new gameboard
    def __init__(self):
        print("Initializing Settlers of Catan with only AI Players...")
        self.board = catanBoard()

        #Game State variables
        self.gameOver = False
        self.maxPoints = 10
        self.numPlayers = 0

        while(self.numPlayers not in [3,4]): #Only accept 3 and 4 player games
            try:
                self.numPlayers = int(input("Enter Number of Players (3 or 4):"))
            except:
                print("Please input a valid number")

        print("Initializing game with {} players...".format(self.numPlayers))
        print("Note that Player 1 goes first, Player 2 second and so forth.")
        
        #Initialize blank player queue
        self.playerQueue = queue.Queue(self.numPlayers)
        self.gameSetup = True #Boolean to take care of setup phase
        self.player_to_move_robber = None # New flag: stores the player object

        # Chat histories
        self.global_chat_history = []
        self.private_chat_histories = {}
        self.communication_phase_active = False
        self.active_private_chat_participants = None

        # Negotiation Manager
        self.current_negotiation = None

        # Reputation System
        self.reputation = {}

        #Dictionary to keep track of dice statistics
        self.diceStats = {roll: 0 for roll in range(2, 13)}
        self.diceStats_list = []

        #Initialize GameLogicManager
        # Pass a lambda that can be called to get the current player list from the queue
        self.gameLogic = GameLogicManager(self.board, lambda: list(self.playerQueue.queue))

        #Initialize boardview object
        self.boardView = catanGameView(self.board, self)

        #Function to go through initial set up
        self.build_initial_settlements() # This will populate playerQueue
        self.playCatan()

        #Plot diceStats histogram
        plt.hist(self.diceStats_list, bins = 11)
        plt.show()

        return None
    

    #Function to initialize players + build initial settlements for players
    def build_initial_settlements(self):
        playerColors = ['black', 'darkslateblue', 'magenta4', 'orange1']

        # Define available AI types for user selection
        available_ai_types = {
            "1": {"name": "ChatGPT (LLM)", "type": "llm", "llm_type": "chatgpt"},
            "2": {"name": "Gemini (LLM)", "type": "llm", "llm_type": "gemini"},
            "3": {"name": "Claude (LLM)", "type": "llm", "llm_type": "claude"},
            "4": {"name": "Deepseek (LLM)", "type": "llm", "llm_type": "deepseek"},
            "5": {"name": "Heuristic AI", "type": "heuristic"}
        }
        ai_type_prompt_string = "Choose AI type for Player {}:\n" +                                 "\n".join([f"  {key}: {val['name']}" for key, val in available_ai_types.items()]) +                                 "\nEnter choice (1-5): "

        available_personas = ["Aggressive", "Hoarder", "Diplomat", "Risk-Averse", "None"]
        persona_prompt_string = "Choose Persona for LLM Player {}:\n" +                                 "\n".join([f"  {idx+1}: {p_name}" for idx, p_name in enumerate(available_personas)]) +                                 "\nEnter choice (1-{}): ".format(len(available_personas))


        # Ensure playerQueue is empty before adding new players
        while not self.playerQueue.empty():
            self.playerQueue.get()

        created_players = [] # Temporary list to hold players before putting them in queue

        for i in range(self.numPlayers):
            chosen_ai_details = None
            while chosen_ai_details is None:
                try:
                    print("--------------------")
                    choice = input(ai_type_prompt_string.format(i + 1))
                    if choice in available_ai_types:
                        chosen_ai_details = available_ai_types[choice]
                    else:
                        print("Invalid choice. Please enter a number from 1 to 5.")
                except EOFError: # Handle environments where input might not be available (e.g. some test runners)
                    print("EOFError encountered during input. Defaulting to Heuristic AI for remaining players.")
                    # Default to heuristic if input fails
                    chosen_ai_details = available_ai_types["5"]

            newPlayer = None
            player_color = playerColors[i % len(playerColors)] # Cycle colors if numPlayers > 4

            if chosen_ai_details["type"] == "llm":
                llm_type = chosen_ai_details["llm_type"]
                playerName = f"{llm_type.capitalize()}-AI-{i+1}"

                # Persona Selection
                chosen_persona = None
                if llm_type in ["gemini", "chatgpt", "claude", "deepseek"]: # Assuming all LLMs can have personas
                    while chosen_persona is None:
                        try:
                            persona_choice_idx = input(persona_prompt_string.format(i+1)).strip()
                            persona_idx = int(persona_choice_idx) -1
                            if 0 <= persona_idx < len(available_personas):
                                chosen_persona = available_personas[persona_idx]
                                if chosen_persona == "None": chosen_persona = None # Set to None if "None" is chosen
                            else:
                                print(f"Invalid persona choice. Please enter a number from 1 to {len(available_personas)}.")
                        except ValueError:
                            print("Invalid input. Please enter a number.")
                        except EOFError:
                            print("EOFError encountered during persona input. Defaulting to no persona.")
                            chosen_persona = None # Default to no persona
                            break

                print(f"Creating LLM Player: {playerName} with color {player_color}, type {llm_type}, and persona: {chosen_persona if chosen_persona else 'Default'}")
                newPlayer = LLMPlayer(playerName, player_color, llm_type, persona=chosen_persona)

            elif chosen_ai_details["type"] == "heuristic":
                playerName = f"Heuristic-AI-{i+1}"
                print(f"Creating Heuristic Player: {playerName} with color {player_color}")
                newPlayer = heuristicAIPlayer(playerName, player_color)
                newPlayer.updateAI() # This is specific to heuristicAIPlayer to set up its resources/flags

            if newPlayer:
                created_players.append(newPlayer)

        # Add players to the queue (original order for first setup round)
        for p in created_players:
            self.playerQueue.put(p)

        # Initialize reputation scores for all player pairs to 0
        player_names = [p.name for p in created_players]
        for p1_name in player_names:
            self.reputation[p1_name] = {}
            for p2_name in player_names:
                if p1_name != p2_name:
                    self.reputation[p1_name][p2_name] = 0
        print(f"Initialized Reputation Matrix: {self.reputation}")


        playerList = list(self.playerQueue.queue) # Now correctly refers to players from the queue

        print("\n--- Initial Setup Phase ---")
        # First round of placements (e.g., P1, P2, P3, P4)
        for player_i in playerList: 
            print(f"\nSetup Turn 1: {player_i.name}")
            if isinstance(player_i, LLMPlayer):
                # --- LLM places first settlement ---
                print(f"{player_i.name} to place first settlement.")
                settlement_placed_successfully = False
                settlement_placement_attempts = 0
                max_settlement_placement_attempts = 3
                # last_s_status, last_s_error removed, will use player_i attributes
                placed_settlement_v_idx = None

                while not settlement_placed_successfully and settlement_placement_attempts < max_settlement_placement_attempts:
                    settlement_placement_attempts += 1
                    if settlement_placement_attempts > 1:
                        print(f"Re-prompting {player_i.name} for settlement (attempt {settlement_placement_attempts})")
                        # Ensure feedback is set on player_i for the modelState to pick up
                        # player_i.feedback_status_for_next_state = last_s_status_for_retry
                        # player_i.feedback_details_for_next_state = last_s_error_for_retry
                        # These last_s_status_for_retry would be set in the else clauses below.

                    current_model_state_settlement = modelState(self, player_i) # Will pick up feedback from player_i

                    action_settlement = player_i.get_llm_move(current_model_state_settlement)
                    print(f"{player_i.name} (Thoughts for settlement: {player_i.thoughts}) -> Action: {action_settlement}")
                    action_type = action_settlement.get("type")
                    v_idx = action_settlement.get("vertex_index")

                    if action_type == "build_settlement" and v_idx is not None:
                        if v_idx in current_model_state_settlement.available_actions.get("build_settlement", []):
                            v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                            # player.build_settlement needs a setup_phase flag or similar, or direct board update
                            # For now, direct update as in catanGame.py's handle_llm_setup_placement
                            self.board.boardGraph[v_coord].state['Player'] = player_i
                            self.board.boardGraph[v_coord].state['Settlement'] = True
                            self.board.boardGraph[v_coord].isColonised = True
                            player_i.buildGraph['SETTLEMENTS'].append(v_coord)
                            player_i.settlementsLeft -= 1
                            player_i.victoryPoints += 1 # VP for setup settlements
                            if((self.board.boardGraph[v_coord].port != False) and (self.board.boardGraph[v_coord].port not in player_i.portList)):
                                player_i.portList.append(self.board.boardGraph[v_coord].port)

                            print(f"{player_i.name} built initial settlement at {v_idx}.")
                            player_i.last_placed_settlement_v_idx = v_idx # Store for road prompt
                            placed_settlement_v_idx = v_idx
                            settlement_placed_successfully = True
                            player_i.feedback_status_for_next_state = "success" # For the next action (road placement)
                            player_i.feedback_details_for_next_state = f"Successfully placed settlement at {v_idx}."
                        else:
                            player_i.feedback_status_for_next_state = "error_invalid_placement"
                            player_i.feedback_details_for_next_state = f"Vertex {v_idx} is not a valid setup settlement location (e.g. occupied, too close, or rule violation). Valid are: {current_model_state_settlement.available_actions.get('build_settlement', [])}"
                    else:
                        player_i.feedback_status_for_next_state = "error_invalid_action_type"
                        player_i.feedback_details_for_next_state = f"Expected 'build_settlement' action with 'vertex_index'. Got: {action_settlement}"

                if not settlement_placed_successfully:
                    print(f"CRITICAL: {player_i.name} failed to place first settlement after {max_settlement_placement_attempts} attempts. Halting setup for this player.")
                    # Ensure feedback reflects the final failure if loop exhausted
                    # player_i.feedback_status_for_next_state and player_i.feedback_details_for_next_state will have the last error
                    # In a real game, might need to skip player or exit. For now, we'll just not place the road.
                    player_i.last_placed_settlement_v_idx = None # Ensure it's None

                self.boardView.displayGameScreen()
                pygame.time.delay(500)

                # --- LLM places first road ---
                if placed_settlement_v_idx is not None: # Only proceed if settlement was placed successfully
                    print(f"{player_i.name} to place first road connected to settlement at {placed_settlement_v_idx}.")

                    # The following line caused the error if player_i.buildGraph['SETTLEMENTS'] was empty.
                    # last_settlement_pixel_coord = player_i.buildGraph['SETTLEMENTS'][-1]
                    # This coord is not strictly needed if we rely on placed_settlement_v_idx for modelState.

                    road_placement_attempts = 0
                    road_placed_successfully = False
                    # max_road_placement_attempts = 2 # Allow one re-prompt (original value)
                    max_road_placement_attempts = 3 # Increased to align with settlement attempts, as per example in prompt

                    # last_r_status, last_r_error removed, will use player_i attributes

                    while not road_placed_successfully and road_placement_attempts < max_road_placement_attempts:
                        road_placement_attempts += 1
                        if road_placement_attempts > 1:
                            print(f"Re-prompting {player_i.name} for road placement (attempt {road_placement_attempts}).")
                            # Feedback for retry is already on player_i from previous failed attempt in this loop

                        current_model_state_road = modelState(self, player_i, # Will pick up feedback
                                                              setup_road_placement_pending=True,
                                                              last_settlement_vertex_index=placed_settlement_v_idx)

                        action_road = player_i.get_llm_move(current_model_state_road)
                        print(f"{player_i.name} (Thoughts for road: {player_i.thoughts}) -> Action: {action_road}")
                        action_type_road = action_road.get("type")
                        v1_idx_road = action_road.get("v1_index")
                        v2_idx_road = action_road.get("v2_index")

                        if action_type_road == "build_road" and v1_idx_road is not None and v2_idx_road is not None:
                            chosen_road_pair = tuple(sorted((v1_idx_road, v2_idx_road)))
                            # Validate connection to the new settlement
                            if not (v1_idx_road == placed_settlement_v_idx or v2_idx_road == placed_settlement_v_idx):
                                player_i.feedback_status_for_next_state = "error_invalid_placement"
                                player_i.feedback_details_for_next_state = f"Road {chosen_road_pair} must connect to the new settlement at vertex {placed_settlement_v_idx}."
                            elif chosen_road_pair in current_model_state_road.available_actions.get("build_road", []):
                                v1_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx_road)
                                v2_coord = self.board.vertex_index_to_pixel_dict.get(v2_idx_road)
                                if player_i.build_road(v1_coord, v2_coord, self.board, setup_phase=True):
                                    print(f"{player_i.name} built initial road from {v1_idx_road} to {v2_idx_road}.")
                                    road_placed_successfully = True
                                    player_i.feedback_status_for_next_state = "success" # For the next player or phase
                                    player_i.feedback_details_for_next_state = f"Successfully built road {chosen_road_pair}."
                                else:
                                    player_i.feedback_status_for_next_state = "error_unknown_build_failure"
                                    player_i.feedback_details_for_next_state = "player.build_road returned False for setup road unexpectedly. Ensure road rules are met."
                            else:
                                player_i.feedback_status_for_next_state = "error_invalid_placement"
                                player_i.feedback_details_for_next_state = f"Road {chosen_road_pair} is not a valid setup road. Valid roads are: {current_model_state_road.available_actions.get('build_road', [])}"
                        else:
                            player_i.feedback_status_for_next_state = "error_invalid_action_type"
                            player_i.feedback_details_for_next_state = f"Expected 'build_road' action with 'v1_index' and 'v2_index'. Got: {action_road}"

                    if not road_placed_successfully:
                        print(f"CRITICAL: {player_i.name} failed to place first road after {max_road_placement_attempts} attempts.")
                        # player_i feedback will retain the last error message.
                # else:
                    # print(f"{player_i.name} did not place a settlement, so no road will be placed.")
                    # If settlement failed, player_i.feedback... will have that error. If it was successful, it'll have road success/failure.

            elif isinstance(player_i, heuristicAIPlayer): # Heuristic AI setup
                print(f"{player_i.name} (Heuristic AI) performing initial setup (1st round).")
                player_i.initial_setup(self.board) # Heuristic AI places one settlement and one road

            pygame.event.pump()
            self.boardView.displayGameScreen()
            pygame.time.delay(1000)

        # Second round of placements (e.g., P4, P3, P2, P1)
        playerList.reverse() # Reverse order for second round
        for player_i in playerList:
            print(f"\nSetup Turn 2: {player_i.name}")
            if isinstance(player_i, LLMPlayer):
                # --- LLM places second settlement ---
                print(f"{player_i.name} to place second settlement.")
                settlement_placed_successfully = False
                settlement_placement_attempts = 0
                max_settlement_placement_attempts = 3
                # last_s_status, last_s_error removed
                placed_settlement_v_idx = None

                while not settlement_placed_successfully and settlement_placement_attempts < max_settlement_placement_attempts:
                    settlement_placement_attempts += 1
                    if settlement_placement_attempts > 1:
                        print(f"Re-prompting {player_i.name} for 2nd settlement (attempt {settlement_placement_attempts})")
                        # Feedback for retry is on player_i

                    current_model_state_settlement = modelState(self, player_i) # Will pick up feedback

                    action_settlement = player_i.get_llm_move(current_model_state_settlement)
                    print(f"{player_i.name} (Thoughts for 2nd settlement: {player_i.thoughts}) -> Action: {action_settlement}")
                    action_type = action_settlement.get("type")
                    v_idx = action_settlement.get("vertex_index")

                    if action_type == "build_settlement" and v_idx is not None:
                        if v_idx in current_model_state_settlement.available_actions.get("build_settlement", []):
                            v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                            # Direct board update for setup settlement
                            self.board.boardGraph[v_coord].state['Player'] = player_i
                            self.board.boardGraph[v_coord].state['Settlement'] = True
                            self.board.boardGraph[v_coord].isColonised = True
                            player_i.buildGraph['SETTLEMENTS'].append(v_coord)
                            player_i.settlementsLeft -= 1
                            player_i.victoryPoints += 1
                            if((self.board.boardGraph[v_coord].port != False) and (self.board.boardGraph[v_coord].port not in player_i.portList)):
                                player_i.portList.append(self.board.boardGraph[v_coord].port)

                            print(f"{player_i.name} built 2nd initial settlement at {v_idx}.")
                            player_i.last_placed_settlement_v_idx = v_idx
                            placed_settlement_v_idx = v_idx
                            settlement_placed_successfully = True
                            player_i.feedback_status_for_next_state = "success"
                            player_i.feedback_details_for_next_state = f"Successfully placed 2nd settlement at {v_idx}."
                        else:
                            player_i.feedback_status_for_next_state = "error_invalid_placement"
                            player_i.feedback_details_for_next_state = f"Vertex {v_idx} is not a valid setup settlement location for 2nd settlement. Valid are: {current_model_state_settlement.available_actions.get('build_settlement', [])}"
                    else:
                        player_i.feedback_status_for_next_state = "error_invalid_action_type"
                        player_i.feedback_details_for_next_state = f"Expected 'build_settlement' action with 'vertex_index' for 2nd settlement. Got: {action_settlement}"

                if not settlement_placed_successfully:
                    print(f"CRITICAL: {player_i.name} failed to place 2nd settlement after {max_settlement_placement_attempts} attempts. Halting setup.")
                    # Feedback on player_i obj will have the last error
                    player_i.last_placed_settlement_v_idx = None

                self.boardView.displayGameScreen()
                pygame.time.delay(500)

                # --- LLM places second road ---
                if placed_settlement_v_idx is not None: # Only proceed if settlement was placed successfully
                    print(f"{player_i.name} to place second road connected to settlement at {placed_settlement_v_idx}.")
                    road_placement_attempts = 0
                    road_placed_successfully = False
                    max_road_placement_attempts = 3
                    # last_r_status, last_r_error removed

                    while not road_placed_successfully and road_placement_attempts < max_road_placement_attempts:
                        road_placement_attempts += 1
                        if road_placement_attempts > 1:
                            print(f"Re-prompting {player_i.name} for 2nd road (attempt {road_placement_attempts})")
                            # Feedback for retry is on player_i

                        current_model_state_road = modelState(self, player_i, # Will pick up feedback
                                                              setup_road_placement_pending=True,
                                                              last_settlement_vertex_index=placed_settlement_v_idx)

                        action_road = player_i.get_llm_move(current_model_state_road)
                        print(f"{player_i.name} (Thoughts for 2nd road: {player_i.thoughts}) -> Action: {action_road}")
                        action_type_road = action_road.get("type")
                        v1_idx_road = action_road.get("v1_index")
                        v2_idx_road = action_road.get("v2_index")

                        if action_type_road == "build_road" and v1_idx_road is not None and v2_idx_road is not None:
                            chosen_road_pair = tuple(sorted((v1_idx_road, v2_idx_road)))
                            if not (v1_idx_road == placed_settlement_v_idx or v2_idx_road == placed_settlement_v_idx):
                                player_i.feedback_status_for_next_state = "error_invalid_placement"
                                player_i.feedback_details_for_next_state = f"Road {chosen_road_pair} for 2nd settlement must connect to it at vertex {placed_settlement_v_idx}."
                            elif chosen_road_pair in current_model_state_road.available_actions.get("build_road", []):
                                v1_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx_road)
                                v2_coord = self.board.vertex_index_to_pixel_dict.get(v2_idx_road)
                                if player_i.build_road(v1_coord, v2_coord, self.board, setup_phase=True):
                                    print(f"{player_i.name} built 2nd initial road from {v1_idx_road} to {v2_idx_road}.")
                                    road_placed_successfully = True
                                    player_i.feedback_status_for_next_state = "success"
                                    player_i.feedback_details_for_next_state = f"Successfully built 2nd road {chosen_road_pair}."
                                else:
                                    player_i.feedback_status_for_next_state = "error_unknown_build_failure"
                                    player_i.feedback_details_for_next_state = "player.build_road returned False for 2nd setup road unexpectedly. Ensure road rules are met."
                            else:
                                player_i.feedback_status_for_next_state = "error_invalid_placement"
                                player_i.feedback_details_for_next_state = f"Road {chosen_road_pair} is not a valid 2nd setup road. Valid roads are: {current_model_state_road.available_actions.get('build_road', [])}"
                        else:
                            player_i.feedback_status_for_next_state = "error_invalid_action_type"
                            player_i.feedback_details_for_next_state = f"Expected 'build_road' action with 'v1_index' and 'v2_index' for 2nd road. Got: {action_road}"

                    if not road_placed_successfully:
                        print(f"CRITICAL: {player_i.name} failed to place 2nd road after {max_road_placement_attempts} attempts.")
                        # player_i feedback will have the last error.
                # else:
                    # print(f"{player_i.name} did not place second settlement, so no second road will be placed.")

            elif isinstance(player_i, heuristicAIPlayer): # Heuristic AI setup
                print(f"{player_i.name} (Heuristic AI) performing initial setup (2nd round).")
                player_i.initial_setup(self.board) # Heuristic AI places one settlement and one road

            pygame.event.pump()
            self.boardView.displayGameScreen()
            pygame.time.delay(1000)

            # Initial resource generation for the second settlement for ALL player types
            print(f"Player {player_i.name} built their second settlement. Collecting initial resources.")
            if player_i.buildGraph['SETTLEMENTS']: # Check if settlements list is not empty
                last_settlement_coord = player_i.buildGraph['SETTLEMENTS'][-1]
                for adjacentHex_idx in self.board.boardGraph[last_settlement_coord].adjacentHexList:
                    hex_tile = self.board.hexTileDict[adjacentHex_idx]
                    resourceGenerated = hex_tile.resource.type
                    if resourceGenerated != 'DESERT':
                        player_i.resources[resourceGenerated] = player_i.resources.get(resourceGenerated, 0) + 1
                        print(f"{player_i.name} collects 1 {resourceGenerated} from second settlement.")
            else:
                print(f"WARNING: {player_i.name} has no settlements after second setup round to collect resources from.")
        
        pygame.time.delay(2000)
        self.gameSetup = False
        print("\n--- Initial Setup Complete ---")

    def execute_random_setup_settlement(self, player_obj):
        # Fallback: very basic random valid settlement placement
        # This is a simplified version of heuristicAIPlayer's initial_setup settlement logic
        possible_vertices = self.board.get_setup_settlements(player_obj)
        if not possible_vertices:
            print(f"CRITICAL: No valid setup settlement spots for {player_obj.name}. This shouldn't happen.")
            # Potentially raise an error or find any vertex
            first_available = next(iter(self.board.boardGraph.keys()))
            player_obj.build_settlement(first_available, self.board) # Risky
            return

        # Extremely basic: pick the first valid one
        # A better random would involve np.random.choice(list(possible_vertices.keys()))
        # Ensure the chosen spot also respects the distance rule for subsequent placements
        chosen_v_coord = None
        for v_coord_option in possible_vertices.keys():
            valid_placement = True
            # Check distance rule relative to ALL existing settlements on the board
            for v_pixel_existing, v_obj_existing in self.board.boardGraph.items():
                if v_obj_existing.isColonised: # If there's any settlement
                    # Check if v_coord_option is a direct neighbor of v_pixel_existing
                    if v_coord_option in self.board.boardGraph[v_pixel_existing].edgeList:
                        valid_placement = False
                        break
            if valid_placement:
                chosen_v_coord = v_coord_option
                break

        if chosen_v_coord:
            player_obj.build_settlement(chosen_v_coord, self.board)
            print(f"{player_obj.name} (random fallback) built settlement at {chosen_v_coord}.")
        else: # If all spots are too close (e.g. in a very crowded late setup for some reason)
            # This case should be rare in initial setup. Pick first possible if nothing else.
            chosen_v_coord = list(possible_vertices.keys())[0]
            player_obj.build_settlement(chosen_v_coord, self.board)
            print(f"{player_obj.name} (random fallback, relaxed distance) built settlement at {chosen_v_coord}.")


    def execute_random_setup_road(self, player_obj):
        # Fallback: very basic random valid road placement
        if not player_obj.buildGraph['SETTLEMENTS']:
            print(f"CRITICAL: {player_obj.name} has no settlements to build a road from in random setup.")
            return

        possible_roads = self.board.get_setup_roads(player_obj) # Needs player's last settlement
        if not possible_roads:
            print(f"CRITICAL: No valid setup road spots for {player_obj.name}. This shouldn't happen.")
            # This implies the last settlement has no available road spots, which is unlikely.
            return

        # Extremely basic: pick the first valid one
        v1_coord, v2_coord = list(possible_roads.keys())[0]
        player_obj.build_road(v1_coord, v2_coord, self.board)
        print(f"{player_obj.name} (random fallback) built road from {v1_coord} to {v2_coord}.")


    #Function to roll dice - Now uses GameLogicManager
    # def rollDice(self):
    #     dice_1 = np.random.randint(1,7)
    #     dice_2 = np.random.randint(1,7)
    #     diceRoll = dice_1 + dice_2
    #     print("Dice Roll = ", diceRoll, "{", dice_1, dice_2, "}")

    #     return diceRoll

    #Function to update resources for all players
    def update_playerResources(self, diceRoll, currentPlayer):
        if diceRoll != 7: # Collect resources if not a 7
            self.gameLogic.distribute_resources(diceRoll) # Use GameLogicManager
        else: # Dice roll is 7
            print("---------------------------------------------------------------------------")
            print("Dice roll is 7! Robber activates. Players with >7 cards must discard.")
            print("---------------------------------------------------------------------------")


            for p in list(self.playerQueue.queue):
                p.pending_discard_count = 0 # Initialize/reset for all players first
                total_resources = sum(p.resources.values())
                if total_resources > 7:
                    cards_to_discard_count = total_resources // 2
                    print(f"Player {p.name} has {total_resources} resources and must discard {cards_to_discard_count}.")
                    p.pending_discard_count = cards_to_discard_count # Set it on the player object

            # Robber movement decision is now deferred to playCatan for LLMs
            if isinstance(currentPlayer, heuristicAIPlayer):
                print(f"{currentPlayer.name} (Heuristic) is moving the robber (will be handled after discards).")
                # Heuristic will move robber after discards in its own way if this flag is checked by it.
                # For now, the robber movement for heuristic is also part of its .move() or a specific call.
                # The original call to currentPlayer.heuristic_move_robber(self.board) is removed from here.
                # Instead, it will be handled in the playCatan sequence.
                self.player_to_move_robber = currentPlayer # Heuristic also uses this flag now for sequence.
            elif isinstance(currentPlayer, LLMPlayer):
                print(f"{currentPlayer.name} (LLM) must move the robber. Action will be decided in their turn.")
                self.player_to_move_robber = currentPlayer
            else:
                self.player_to_move_robber = None


    #function to check if a player has the longest road - Now uses GameLogicManager
    # def check_longest_road(self, player_i):
    #     if(player_i.maxRoadLength >= 5): #Only eligible if road length is at least 5
    #         longestRoad = True
    #         for p in list(self.playerQueue.queue):
    #             if(p.maxRoadLength >= player_i.maxRoadLength and p != player_i): #Check if any other players have a longer road
    #                 longestRoad = False
            
    #         if(longestRoad and player_i.longestRoadFlag == False): #if player_i takes longest road and didn't already have longest road
    #             #Set previous players flag to false and give player_i the longest road points
    #             prevPlayer = ''
    #             for p in list(self.playerQueue.queue):
    #                 if(p.longestRoadFlag):
    #                     p.longestRoadFlag = False
    #                     p.victoryPoints -= 2
    #                     prevPlayer = 'from Player ' + p.name
    
    #             player_i.longestRoadFlag = True
    #             player_i.victoryPoints += 2

    #             print("Player {} takes Longest Road {}".format(player_i.name, prevPlayer))

    #function to check if a player has the largest army - Now uses GameLogicManager
    # def check_largest_army(self, player_i):
    #     if(player_i.knightsPlayed >= 3): #Only eligible if at least 3 knights are player
    #         largestArmy = True
    #         for p in list(self.playerQueue.queue):
    #             if(p.knightsPlayed >= player_i.knightsPlayed and p != player_i): #Check if any other players have more knights played
    #                 largestArmy = False
            
    #         if(largestArmy and player_i.largestArmyFlag == False): #if player_i takes largest army and didn't already have it
    #             #Set previous players flag to false and give player_i the largest points
    #             prevPlayer = ''
    #             for p in list(self.playerQueue.queue):
    #                 if(p.largestArmyFlag):
    #                     p.largestArmyFlag = False
    #                     p.victoryPoints -= 2
    #                     prevPlayer = 'from Player ' + p.name
    
    #             player_i.largestArmyFlag = True
    #             player_i.victoryPoints += 2

    #             print("Player {} takes Largest Army {}".format(player_i.name, prevPlayer))



    def _get_player_by_name(self, name_to_find):
        for p_obj in list(self.playerQueue.queue):
            if p_obj.name == name_to_find:
                return p_obj
        return None

    def _execute_random_discard(self, player_obj, num_to_discard):
        print(f"{player_obj.name} (Fallback) randomly discarding {num_to_discard} cards.")
        discarded_count = 0
        # Create a flat list of available resources to make random choice easier
        available_for_discard = []
        for resource, count in player_obj.resources.items():
            available_for_discard.extend([resource] * count)

        if not available_for_discard or len(available_for_discard) < num_to_discard:
            print(f"Error: {player_obj.name} does not have enough cards to discard for random fallback.")
            # This state should ideally not be reached if logic is correct.
            # As a last resort, discard all cards if less than num_to_discard.
            num_to_discard = len(available_for_discard)

        np.random.shuffle(available_for_discard) # Shuffle for randomness

        resources_actually_discarded = {}
        for i in range(num_to_discard):
            if available_for_discard: # Should always be true if logic is correct
                card_to_discard = available_for_discard.pop()
                player_obj.resources[card_to_discard] -= 1
                resources_actually_discarded[card_to_discard] = resources_actually_discarded.get(card_to_discard, 0) + 1
                discarded_count += 1
        print(f"{player_obj.name} (Fallback) discarded: {resources_actually_discarded}")


    def _execute_random_robber_move(self, player_who_moves_robber):
        print(f"{player_who_moves_robber.name} (LLM Fallback) making a random robber move.")
        # Simplified random robber placement logic (less sophisticated than heuristic's)
        possible_hexes = [h_idx for h_idx, h_tile in self.board.hexTileDict.items() if not h_tile.robber]
        if not possible_hexes: # Should not happen
            print("Error: No valid hexes to move robber to.")
            return

        target_hex_idx = np.random.choice(possible_hexes)

        # Find players on the target hex (simplified)
        players_on_hex = []
        # Need to import or access polygon_corners if it's not directly in self.board
        # Assuming self.board.polygon_corners exists or is accessible
        # For now, let's assume it's part of board or a utility function
        # from hexLib import polygon_corners # This might be needed at top of file if not already via 'from board import *'

        # The following line might cause an error if polygon_corners is not found
        # This part of the code is complex to get right without running the game
        # and depends on exact structure of board/hexLib.
        # For now, we'll simplify the player search to avoid crashing here.
        # A more robust way would be to iterate player.settlements/cities and check hex adjacency.
        # target_hex_vertices = polygon_corners(self.board.flat, self.board.hexTileDict[target_hex_idx].hex)
        # for v_coord in target_hex_vertices:
        #     vertex_obj = self.board.boardGraph.get(v_coord)
        #     if vertex_obj and vertex_obj.state.get('Player') and vertex_obj.state.get('Player') != player_who_moves_robber:
        #         # Check if player has resources, simplified here
        #         player_candidate = vertex_obj.state['Player']
        #         if sum(player_candidate.resources.values()) > 0:
        #             if player_candidate not in players_on_hex:
        #                  players_on_hex.append(player_candidate)

        # Simplified player search: iterate all players, check if any of their buildings are on the target hex
        for p_other in list(self.playerQueue.queue):
            if p_other == player_who_moves_robber:
                continue
            if sum(p_other.resources.values()) == 0: # Cannot rob player with no resources
                continue
            for settlement_coord in p_other.buildGraph['SETTLEMENTS']:
                # A settlement_coord is a key to self.board.boardGraph, which gives a Vertex object
                # The Vertex object has an adjacentHexList (list of hex indices)
                if target_hex_idx in self.board.boardGraph[settlement_coord].adjacentHexList:
                    if p_other not in players_on_hex: players_on_hex.append(p_other)
                    break # Found this player via one of their settlements, no need to check other settlements for same player
            if p_other in players_on_hex: continue # Already found this player (e.g. via a settlement), skip checking their cities for list append
            for city_coord in p_other.buildGraph['CITIES']:
                if target_hex_idx in self.board.boardGraph[city_coord].adjacentHexList:
                    if p_other not in players_on_hex: players_on_hex.append(p_other)
                    break # Found this player via one of their cities

        player_to_rob_obj = None
        if players_on_hex:
            player_to_rob_obj = np.random.choice(players_on_hex)
            print(f"Robber randomly moved to hex {target_hex_idx}, targeting {player_to_rob_obj.name}.")
        else:
            print(f"Robber randomly moved to hex {target_hex_idx}, no one to rob there.")

        outcome = player_who_moves_robber.move_robber(target_hex_idx, self.board, player_to_rob_obj)
        if player_to_rob_obj and outcome: # Successfully robbed
            self.update_reputation(player_who_moves_robber.name, player_to_rob_obj.name, -3)
        # No reputation change if no one was robbed or target had no resources

    def handle_private_chat(self, initiator, recipient, opening_message):
        self.active_private_chat_participants = tuple(sorted((initiator.name, recipient.name)))
        chat_key = self.active_private_chat_participants # Use the sorted tuple directly

        if chat_key not in self.private_chat_histories:
            self.private_chat_histories[chat_key] = []

        # Add opening message
        self.private_chat_histories[chat_key].append({"player": initiator.name, "message": opening_message})
        print(f"[Private Chat | {initiator.name} to {recipient.name}]: {opening_message}")
        self.boardView.displayGameScreen() # Update GUI to show chat status

        current_speaker = recipient # Recipient gets to respond first
        other_speaker = initiator
        max_exchanges = 4 # Max 4 exchanges (initiator -> recipient -> initiator -> recipient -> initiator -> recipient -> initiator -> recipient) = 8 messages total (incl opener)

        for exchange_num in range(max_exchanges * 2 -1): # Max messages after opener
            # Create a modelState indicating a private chat is active
            # The modelState needs to be created for the 'current_speaker'
            chat_state = modelState(self, current_speaker, private_chat_active=True, communication_phase_active=False)

            print(f"--- Private Chat: {current_speaker.name}'s turn to speak to {other_speaker.name} ---")
            response_action = current_speaker.get_llm_move(chat_state)
            action_type = response_action.get("type")
            message_content = response_action.get("message") # For send_private_message

            if action_type == "send_private_message" and message_content:
                self.private_chat_histories[chat_key].append({"player": current_speaker.name, "message": message_content})
                print(f"[Private Chat | {current_speaker.name} to {other_speaker.name}]: {message_content}")
                # Swap speaker for next turn
                current_speaker, other_speaker = other_speaker, current_speaker

            elif action_type == "accept_trade":
                 # TODO: Handle the trade logic. This is complex.
                 # Need to know what was proposed. This might require the LLM to re-state the trade.
                 # Or, the private chat context should make the trade clear.
                 print(f"[Private Chat | {current_speaker.name}]: Accepted trade with {other_speaker.name}! (Trade execution logic TBD). Exiting chat.")
                 # Potentially, the LLM that accepts should then make a formal "propose_trade" or "accept_trade" action
                 # that the game loop can process with resource validation.
                 # For now, just end the chat.
                 break

            elif action_type == "end_private_chat":
                print(f"[Private Chat | {current_speaker.name}]: Ended chat with {other_speaker.name}.")
                break

            else: # Any other action, or invalid action, ends the chat.
                print(f"[Private Chat | {current_speaker.name}]: Action ({action_type}) ended chat with {other_speaker.name}.")
                break

            self.boardView.displayGameScreen() # Update GUI
            pygame.time.delay(200) # Small delay for readability

        print(f"--- Private Chat between {initiator.name} and {recipient.name} concluded. ---")
        self.active_private_chat_participants = None # Clear active chat participants
        self.boardView.displayGameScreen() # Final update

    def handle_negotiation(self, initiator_player, target_player, numTurns_at_start):
        """
        Manages the negotiation loop between two players using NegotiationManager.
        """
        if not self.current_negotiation or not self.current_negotiation.is_active():
            print("Error: No active negotiation to handle.")
            return False

        print(f"--- Negotiation Resumed with {self.current_negotiation.active_negotiator.name} ---")
        max_negotiation_actions = 6 # Max total actions (offers/counters/accept/reject) in a negotiation session
        actions_taken_this_session = 0

        while self.current_negotiation.is_active() and actions_taken_this_session < max_negotiation_actions:
            current_llm_negotiator = self.current_negotiation.active_negotiator
            other_llm_negotiator = self.current_negotiation.initiator if current_llm_negotiator == self.current_negotiation.target else self.current_negotiation.target

            actions_taken_this_session +=1
            print(f"Negotiation Action {actions_taken_this_session}: {current_llm_negotiator.name}'s turn.")

            # modelState will now use self.current_negotiation.get_context_for_player()
            negotiation_model_state = modelState(self, current_llm_negotiator)
                                           # is_negotiation_turn=True, # No longer needed directly for modelState
                                           # negotiation_partner_name=other_llm_negotiator.name) # No longer needed

            action = current_llm_negotiator.get_llm_move(negotiation_model_state)
            action_type = action.get("type")
            print(f"{current_llm_negotiator.name} (Negotiation Thoughts: {current_llm_negotiator.thoughts}) -> Action: {action}")

            if action_type == "accept_trade":
                last_offer = self.current_negotiation.get_last_offer()
                if not last_offer:
                    print(f"Error: {current_llm_negotiator.name} tried to accept, but no valid last offer found in history.")
                    current_llm_negotiator.feedback_status_for_next_state = "error_negotiation_no_offer_to_accept"
                    current_llm_negotiator.feedback_details_for_next_state = "There was no valid previous offer to accept."
                    self.current_negotiation.end_negotiation_by_system("Error: Tried to accept non-existent offer.", game_turn=numTurns_at_start + actions_taken_this_session)
                    break

                # Determine who gives what based on the last_offer
                # current_llm_negotiator is the one accepting.
                # The player who made the last_offer is last_offer['from_player']
                proposer_of_last_offer = self._get_player_by_name(last_offer['from_player'])

                resources_acceptor_gives = last_offer.get('resources_requested', {}) # What acceptor (current_llm_negotiator) gives
                resources_acceptor_receives = last_offer.get('resources_offered', {})   # What acceptor receives

                can_acceptor_give = all(current_llm_negotiator.resources.get(res, 0) >= count for res, count in resources_acceptor_gives.items())
                can_proposer_give = all(proposer_of_last_offer.resources.get(res, 0) >= count for res, count in resources_acceptor_receives.items())

                if can_acceptor_give and can_proposer_give:
                    if self.current_negotiation.accept_offer(current_llm_negotiator, game_turn=numTurns_at_start + actions_taken_this_session):
                        # Execute trade
                        for res, count in resources_acceptor_gives.items():
                            current_llm_negotiator.resources[res] -= count
                            proposer_of_last_offer.resources[res] += count
                        for res, count in resources_acceptor_receives.items():
                            proposer_of_last_offer.resources[res] -= count
                            current_llm_negotiator.resources[res] += count

                        print(f"Trade Accepted & Executed! Offer: {last_offer}")
                        print(f"{current_llm_negotiator.name} resources: {current_llm_negotiator.resources}")
                        print(f"{proposer_of_last_offer.name} resources: {proposer_of_last_offer.resources}")

                        # Update reputation for accepted trade
                        self.update_reputation(current_llm_negotiator.name, proposer_of_last_offer.name, 2)
                        self.update_reputation(proposer_of_last_offer.name, current_llm_negotiator.name, 2)

                        current_llm_negotiator.feedback_status_for_next_state = "success_trade_accepted"
                        current_llm_negotiator.feedback_details_for_next_state = f"You accepted the trade with {proposer_of_last_offer.name}."
                        proposer_of_last_offer.feedback_status_for_next_state = "success_trade_accepted_by_partner"
                        proposer_of_last_offer.feedback_details_for_next_state = f"Your trade offer was accepted by {current_llm_negotiator.name}."
                    # NegotiationManager handles state change to ACCEPTED, loop will terminate.
                else:
                    error_msg = "Trade acceptance failed due to insufficient resources. "
                    # ... (feedback setting as before) ...
                    current_llm_negotiator.feedback_status_for_next_state = "error_accept_trade_failed_resources"
                    current_llm_negotiator.feedback_details_for_next_state = error_msg + " Your attempt to accept has been logged as a rejection of this offer."
                    # Treat as implicit rejection for this offer, allow negotiation to continue or be ended by LLM.
                    # The NegotiationManager itself doesn't auto-reject on failed validation here, AIGame does.
                    # For simplicity, let's have the game inform the manager it's a rejection due to this.
                    self.current_negotiation.reject_offer(current_llm_negotiator, f"System rejection: resource check failed for acceptance. Details: {error_msg}", game_turn=numTurns_at_start + actions_taken_this_session)
                    # This will change state to REJECTED and loop will end.

            elif action_type == "propose_counter_offer":
                offered_by_llm = action.get("resources_offered", {})
                requested_from_partner_llm = action.get("resources_requested", {})
                can_llm_offer = all(current_llm_negotiator.resources.get(res,0) >= count for res, count in offered_by_llm.items())

                if not offered_by_llm or not requested_from_partner_llm:
                    current_llm_negotiator.feedback_status_for_next_state = "error_invalid_counter_offer"
                    current_llm_negotiator.feedback_details_for_next_state = "Counter-offer was invalid (missing details)."
                    self.current_negotiation.end_negotiation_by_system("Invalid counter-offer (missing details)", game_turn=numTurns_at_start + actions_taken_this_session)
                elif not can_llm_offer:
                    current_llm_negotiator.feedback_status_for_next_state = "error_counter_offer_insufficient_resources"
                    current_llm_negotiator.feedback_details_for_next_state = "You cannot afford your counter-offer."
                    self.current_negotiation.end_negotiation_by_system("Counter-offer resources unaffordable", game_turn=numTurns_at_start + actions_taken_this_session)
                else:
                    counter_offer_obj = {
                        "from_player": current_llm_negotiator.name, "to_player": other_llm_negotiator.name,
                        "resources_offered": offered_by_llm, "resources_requested": requested_from_partner_llm,
                        "turn": numTurns_at_start + actions_taken_this_session, "type": "counter_offer"
                    }
                    if self.current_negotiation.add_counter_offer(current_llm_negotiator, counter_offer_obj, game_turn=numTurns_at_start + actions_taken_this_session):
                        current_llm_negotiator.feedback_status_for_next_state = "success_counter_offer_proposed"
                        current_llm_negotiator.feedback_details_for_next_state = f"Counter-offer proposed to {other_llm_negotiator.name}."
                        # active_negotiator is switched by manager
                    else: # Should not happen if logic is correct
                        current_llm_negotiator.feedback_status_for_next_state = "error_counter_offer_failed_manager"
                        current_llm_negotiator.feedback_details_for_next_state = "Failed to register counter-offer with NegotiationManager."
                        self.current_negotiation.end_negotiation_by_system("Manager failed to add counter", game_turn=numTurns_at_start + actions_taken_this_session)

            elif action_type == "end_negotiation":
                reason = action.get("reason", "No reason given.")
                self.current_negotiation.end_negotiation_by_player(current_llm_negotiator, reason, game_turn=numTurns_at_start + actions_taken_this_session)
                current_llm_negotiator.feedback_status_for_next_state = "info_negotiation_ended"
                current_llm_negotiator.feedback_details_for_next_state = f"You ended negotiation with {other_llm_negotiator.name}."
                other_llm_negotiator.feedback_status_for_next_state = "info_negotiation_ended_by_partner"
                other_llm_negotiator.feedback_details_for_next_state = f"{current_llm_negotiator.name} ended negotiation with you."
                # Loop will terminate as is_active() becomes false.

            else: # Invalid action
                invalid_action_reason = f"Invalid action '{action_type}' during negotiation."
                self.current_negotiation.end_negotiation_by_system(invalid_action_reason, game_turn=numTurns_at_start + actions_taken_this_session)
                current_llm_negotiator.feedback_status_for_next_state = "error_invalid_action_in_negotiation"
                current_llm_negotiator.feedback_details_for_next_state = invalid_action_reason
                other_llm_negotiator.feedback_status_for_next_state = "info_negotiation_ended_by_system_error"
                other_llm_negotiator.feedback_details_for_next_state = f"Negotiation with {current_llm_negotiator.name} ended due to their invalid action."
                # Loop will terminate.

            self.boardView.displayGameScreen() # Update view after each negotiation step
            pygame.time.delay(200)

            if not self.current_negotiation.is_active():
                break # Exit if manager state changed to a non-active one

        # --- Post-Negotiation Session ---
        if self.current_negotiation.is_active() and actions_taken_this_session >= max_negotiation_actions:
            self.current_negotiation.end_negotiation_by_system("Max actions reached in session.", game_turn=numTurns_at_start + actions_taken_this_session)
            # Feedback for players if max actions reached
            self.current_negotiation.active_negotiator.feedback_status_for_next_state = "info_negotiation_ended_max_actions"
            self.current_negotiation.active_negotiator.feedback_details_for_next_state = "Negotiation ended: max actions for session reached."
            # Inform other player too
            other_player = self.current_negotiation.initiator if self.current_negotiation.active_negotiator == self.current_negotiation.target else self.current_negotiation.target
            other_player.feedback_status_for_next_state = "info_negotiation_ended_max_actions"
            other_player.feedback_details_for_next_state = "Negotiation ended: max actions for session reached."


        final_negotiation_state = self.current_negotiation.current_state
        print(f"--- Negotiation Session Concluded. Final State: {final_negotiation_state} ---")

        negotiation_was_successful = (final_negotiation_state == "ACCEPTED")

        # Clear current_negotiation if it's no longer active (accepted, rejected, ended)
        if not self.current_negotiation.is_active():
            # Archive or log self.current_negotiation.history if needed
            self.current_negotiation = None

        self.boardView.displayGameScreen()
        return negotiation_was_successful

    def update_reputation(self, player1_name, player2_name, change):
        """Updates reputation score between two players."""
        if player1_name in self.reputation and player2_name in self.reputation[player1_name]:
            self.reputation[player1_name][player2_name] += change
            print(f"Reputation updated: {player1_name}'s rep with {player2_name} is now {self.reputation[player1_name][player2_name]}.")
        else:
            print(f"Warning: Could not update reputation. Player names not found in matrix: {player1_name}, {player2_name}")
        # Symmetric change for player2's reputation with player1 could also be added if desired,
        # but the spec implies one-way changes for some actions (e.g. robber).
        # For accepted trade, it should be symmetric.

    #Function that runs the main game loop with all players and pieces
    def playCatan(self):
        numTurns = 0
        while not self.gameOver:
            # --- Communication Phase (before any player takes their turn) ---
            if not self.gameSetup: # No communication phase during initial setup
                print("--- Communication Phase ---")
                self.communication_phase_active = True
                for player_speaker in list(self.playerQueue.queue):
                    if isinstance(player_speaker, LLMPlayer):
                        # Create a modelState specifically for this communication phase
                        comm_state = modelState(self, player_speaker,
                                                private_chat_active=False,
                                                communication_phase_active=self.communication_phase_active)

                        # Modify modelState to indicate communication phase.
                        # This is a bit of a hack; ideally, modelState would take a phase parameter.
                        # For now, we'll set a temporary attribute on comm_state if modelState doesn't directly support this.
                        # Or, ensure LLMPlayer prompt construction correctly uses self.communication_phase_active from game.
                        # The modelState now has private_chat_active, let's add communication_phase_active for clarity.
                        # We will need to modify modelState to accept 'communication_phase_active'
                        # For now, let's assume modelState correctly uses game.communication_phase_active via the 'self' (catan_game) passed.
                        # The LLMPlayer's _construct_prompt already checks game_state_obj.communication_phase_active

                        comm_action = player_speaker.get_llm_move(comm_state) # LLM decides if it wants to speak

                        if comm_action and comm_action.get("type") == "send_global_message":
                            message = comm_action.get("message")
                            if message: # Ensure message is not empty
                                print(f"[Global Chat | {player_speaker.name}]: {message}")
                                self.global_chat_history.append({"player": player_speaker.name, "message": message})
                                # self.boardView.displayGameScreen() # Update GUI - may cause too many updates if frequent
                        elif comm_action and comm_action.get("type") != "end_turn":
                             print(f"[Communication Phase | {player_speaker.name}]: Chose not to speak or invalid action ({comm_action.get('type')}).")
                        # else: player chose end_turn (i.e. to say nothing) or action was None

                self.communication_phase_active = False # Reset flag after phase
                self.boardView.displayGameScreen() # Update GUI once after communication phase

            for currPlayer in list(self.playerQueue.queue): # Iterate on a copy if queue is modified
                numTurns += 1
                print("---------------------------------------------------------------------------")
                # print(f"Current Player: {currPlayer.name} (Color: {currPlayer.color})") # Moved to after communication phase print
                print(f"--- {currPlayer.name}'s Turn (Color: {currPlayer.color}) ---")

                currPlayer.updateDevCards()
                currPlayer.devCardPlayedThisTurn = False

                # Initialize feedback for the current player's turn
                current_turn_last_action_status = None
                current_turn_last_action_error_details = None

                pygame.event.pump()
                diceNum = self.gameLogic.roll_dice() # Use GameLogicManager
                self.boardView.displayDiceRoll(diceNum) # Display dice roll on GUI if applicable

                # update_playerResources now sets pending_discard_count on players and player_to_move_robber on self
                self.update_playerResources(diceNum, currPlayer) # update_playerResources now uses gameLogic.distribute_resources
                self.diceStats[diceNum] += 1; self.diceStats_list.append(diceNum)

                # --- Card Discarding Phase (if a 7 was rolled) ---
                if diceNum == 7:
                    print("--- Card Discarding Phase ---")
                    for p_discarding in list(self.playerQueue.queue):
                        if hasattr(p_discarding, 'pending_discard_count') and p_discarding.pending_discard_count > 0:
                            required_discard_num = p_discarding.pending_discard_count
                            print(f"Player {p_discarding.name} must discard {required_discard_num} cards.")
                            if isinstance(p_discarding, LLMPlayer):
                                state_for_discard = modelState(self, p_discarding, discard_is_mandatory=True, num_cards_to_discard=required_discard_num)
                                discard_action = p_discarding.get_llm_move(state_for_discard)
                                print(f"{p_discarding.name} (Discard Thoughts: {p_discarding.thoughts}) -> Discard Action: {discard_action}")

                                executed_discard = False
                                if discard_action.get("type") == "discard_cards":
                                    resources_to_discard = discard_action.get("resources", {})
                                    actual_discarded_sum = sum(resources_to_discard.values())

                                    valid_discard = True
                                    if actual_discarded_sum != required_discard_num:
                                        print(f"Error: {p_discarding.name} LLM proposed discarding {actual_discarded_sum} cards, but {required_discard_num} required.")
                                        valid_discard = False
                                    else:
                                        for res, count in resources_to_discard.items():
                                            if p_discarding.resources.get(res, 0) < count:
                                                print(f"Error: {p_discarding.name} LLM tried to discard {count} {res}, but only has {p_discarding.resources.get(res, 0)}.")
                                                valid_discard = False; break

                                    if valid_discard:
                                        for res, count in resources_to_discard.items():
                                            p_discarding.resources[res] -= count
                                        print(f"{p_discarding.name} (LLM) discarded: {resources_to_discard}")
                                        executed_discard = True

                                if not executed_discard: # Fallback if LLM action was invalid or wrong type
                                    self._execute_random_discard(p_discarding, required_discard_num)

                            elif isinstance(p_discarding, heuristicAIPlayer):
                                print(f"{p_discarding.name} (Heuristic) discarding...")
                                p_discarding.heuristic_discard() # Assumes it handles its own resource reduction

                            p_discarding.pending_discard_count = 0
                            self.boardView.displayGameScreen()
                            pygame.time.delay(100) # Small delay after each player discards
                    print("--- Card Discarding Phase Complete ---")


                # --- Robber Movement Phase (if a 7 was rolled and pending for currPlayer) ---
                if self.player_to_move_robber == currPlayer: # currPlayer is the one who rolled the 7
                    print(f"{currPlayer.name} must move the robber.")
                    if isinstance(currPlayer, LLMPlayer):
                        state_for_robber = modelState(self, currPlayer, robber_movement_is_mandatory=True)
                        robber_action = currPlayer.get_llm_move(state_for_robber)
                        print(f"{currPlayer.name} (Robber Thoughts: {currPlayer.thoughts}) -> Robber Action: {robber_action}")
                        # ... (rest of robber execution logic from previous step, including fallback)
                        executed_robber_move = False
                        if robber_action.get("type") == "move_robber":
                            hex_idx = robber_action.get("hex_index")
                            player_name_to_rob = robber_action.get("player_to_rob_name")
                            player_to_rob_object = None
                            if player_name_to_rob: player_to_rob_object = self._get_player_by_name(player_name_to_rob)

                            if hex_idx is not None:
                                # The move_robber method now calls steal_resource, which returns the stolen resource or None
                                outcome = currPlayer.move_robber(hex_idx, self.board, player_to_rob_object) # player.py's move_robber calls steal_resource
                                if player_to_rob_object and outcome: # If a player was specified and steal_resource returned a stolen item
                                    print(f"{currPlayer.name} moved robber to hex {hex_idx} and robbed {player_name_to_rob}.")
                                    self.update_reputation(currPlayer.name, player_to_rob_object.name, -3)
                                elif player_to_rob_object and not outcome:
                                    print(f"{currPlayer.name} moved robber to hex {hex_idx}, attempted to rob {player_name_to_rob} but they had no resources.")
                                else: # No player to rob or other outcome
                                    print(f"{currPlayer.name} moved robber to hex {hex_idx}.")
                                executed_robber_move = True
                            else:
                                current_turn_last_action_status = "error_missing_input" # For feedback if this action fails
                                current_turn_last_action_error_details = "Missing hex_index for move_robber."


                        if not executed_robber_move: # Fallback if LLM action was invalid or move failed
                            print(f"{currPlayer.name} (LLM) failed to provide valid 'move_robber' action or it failed. Randomly placing.")
                            # _execute_random_robber_move itself calls move_robber, which calls steal_resource.
                            # So, reputation update for fallback will be handled inside _execute_random_robber_move.
                            self._execute_random_robber_move(currPlayer)

                    elif isinstance(currPlayer, heuristicAIPlayer):
                        print(f"{currPlayer.name} (Heuristic) moving robber...")
                        # Heuristic's choose_player_to_rob returns (hex_idx, player_to_rob_obj)
                        # We need to capture that to update reputation.
                        # This requires refactoring heuristic_move_robber or how it's called.
                        # For now, let's assume heuristic_move_robber will internally call an update or we modify it later.
                        # A simpler approach for now:
                        original_robber_hex = self.board.robber_hex # Store before heuristic moves it
                        player_robbed_by_heuristic = currPlayer.heuristic_move_robber(self.board) # Modify to return player_robbed
                        if player_robbed_by_heuristic:
                             self.update_reputation(currPlayer.name, player_robbed_by_heuristic.name, -3)


                    self.player_to_move_robber = None # Reset flag
                    self.boardView.displayGameScreen(); pygame.time.delay(300)

                # --- Main Turn Actions ---
                if isinstance(currPlayer, LLMPlayer):
                    print(f"{currPlayer.name} taking main turn actions...")
                    actions_this_turn = 0
                    max_actions_per_turn = 10 # Safety break for LLM action loop

                    while actions_this_turn < max_actions_per_turn:
                        actions_this_turn += 1
                        # Create modelState for the current action. It picks up feedback from the *previous action in this turn*
                        # or from mandatory actions (discard/robber) if this is the first action in the multi-action loop.
                        state_for_current_action = modelState(self, currPlayer, private_chat_active=False, communication_phase_active=False)
                        action = currPlayer.get_llm_move(state_for_current_action)
                        print(f"{currPlayer.name} (Turn Action {actions_this_turn}, Thoughts: {currPlayer.thoughts}) -> Action: {action}")

                        action_type = action.get("type")
                        current_turn_last_action_status = "no_action_taken" # Default for this specific action
                        current_turn_last_action_error_details = "Action not processed or player ended turn."

                        if action_type == "end_turn":
                            current_turn_last_action_status = "success_end_turn"
                            current_turn_last_action_error_details = "Player chose to end their turn."
                            print(f"{currPlayer.name} ends their turn after {actions_this_turn-1} action(s).")
                            currPlayer.feedback_status_for_next_state = current_turn_last_action_status
                            currPlayer.feedback_details_for_next_state = current_turn_last_action_error_details
                            break # Exit the multi-action while loop for this player's turn

                        elif action_type == "send_global_message":
                            message = action.get("message")
                            if message:
                                print(f"[Global Chat | {currPlayer.name}]: {message}")
                                self.global_chat_history.append({"player": currPlayer.name, "message": message})
                                current_turn_last_action_status = "success"
                                current_turn_last_action_error_details = "Global message sent."
                            else:
                                current_turn_last_action_status = "error_missing_input"
                                current_turn_last_action_error_details = "Send_global_message action had no message content."

                        elif action_type == "initiate_private_chat":
                            recipient_name = action.get("recipient_name")
                            opening_message = action.get("opening_message")
                            recipient_player = self._get_player_by_name(recipient_name)

                            if recipient_player and isinstance(recipient_player, LLMPlayer) and recipient_player != currPlayer:
                                if opening_message:
                                    print(f"{currPlayer.name} is starting a private chat with {recipient_name}.")
                                    self.handle_private_chat(currPlayer, recipient_player, opening_message)
                                    current_turn_last_action_status = "success"
                                    current_turn_last_action_error_details = f"Private chat with {recipient_name} was conducted."
                                else:
                                    current_turn_last_action_status = "error_missing_input"
                                    current_turn_last_action_error_details = f"Tried to initiate chat with {recipient_name} but no opening message."
                            elif recipient_player == currPlayer:
                                current_turn_last_action_status = "error_invalid_target"
                                current_turn_last_action_error_details = "Cannot initiate chat with oneself."
                            elif not isinstance(recipient_player, LLMPlayer):
                                current_turn_last_action_status = "error_invalid_target_type"
                                current_turn_last_action_error_details = f"Cannot initiate chat with {recipient_name}, not an LLM player."
                            else:
                                current_turn_last_action_status = "error_invalid_target"
                                current_turn_last_action_error_details = f"Player {recipient_name} not found for private chat."

                        elif action_type == "offer_non_binding_deal":
                            target_name = action.get("target_player_name")
                            deal_desc = action.get("deal_description")
                            if target_name and deal_desc:
                                log_message = f"[Diplomacy | {currPlayer.name} to {target_name}]: Offers non-binding deal: \"{deal_desc}\"."
                                print(log_message)
                                self.global_chat_history.append({"player": currPlayer.name, "type": "diplomatic_offer", "target": target_name, "message": log_message})
                                current_turn_last_action_status = "success_diplomatic_action_logged"
                                current_turn_last_action_error_details = "Non-binding deal offer logged."
                            else:
                                current_turn_last_action_status = "error_missing_input_diplomacy"
                                current_turn_last_action_error_details = "Missing target_player_name or deal_description for offer_non_binding_deal."

                        elif action_type == "request_embargo":
                            target_name = action.get("target_player_name")
                            reason = action.get("reasoning")
                            if target_name and reason:
                                log_message = f"[Diplomacy | {currPlayer.name}]: Proposes an embargo against {target_name}. Reason: \"{reason}\"."
                                print(log_message)
                                self.global_chat_history.append({"player": currPlayer.name, "type": "diplomatic_embargo_request", "target": target_name, "message": log_message})
                                current_turn_last_action_status = "success_diplomatic_action_logged"
                                current_turn_last_action_error_details = "Embargo request logged."
                            else:
                                current_turn_last_action_status = "error_missing_input_diplomacy"
                                current_turn_last_action_error_details = "Missing target_player_name or reasoning for request_embargo."

                        elif action_type == "share_information":
                            info = action.get("information")
                            if info:
                                log_message = f"[Diplomacy | {currPlayer.name}]: Shares information: \"{info}\"."
                                print(log_message)
                                self.global_chat_history.append({"player": currPlayer.name, "type": "diplomatic_info_share", "message": log_message})
                                current_turn_last_action_status = "success_diplomatic_action_logged"
                                current_turn_last_action_error_details = "Information shared and logged."
                            else:
                                current_turn_last_action_status = "error_missing_input_diplomacy"
                                current_turn_last_action_error_details = "Missing information for share_information."

                        elif action_type == "build_road":
                            v1_idx, v2_idx = action.get("v1_index"), action.get("v2_index")
                            required_resources = state_for_current_action.action_costs["build_road"]
                        can_afford = all(currPlayer.resources.get(res, 0) >= count for res, count in required_resources.items())

                        if v1_idx is None or v2_idx is None:
                            current_turn_last_action_status = "error_missing_input"
                            current_turn_last_action_error_details = "Missing v1_index or v2_index for build_road."
                        elif not can_afford:
                            missing_res_list = [f"{count} {res}" for res, count in required_resources.items() if currPlayer.resources.get(res, 0) < count]
                            current_turn_last_action_status = "error_insufficient_resources"
                            current_turn_last_action_error_details = f"Cannot build road: Insufficient resources. You have {currPlayer.resources}, need {required_resources}. Missing: {', '.join(missing_res_list)}."
                        else:
                            v1_coord, v2_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx), self.board.vertex_index_to_pixel_dict.get(v2_idx)
                            if not v1_coord or not v2_coord:
                                current_turn_last_action_status = "error_invalid_input"
                                current_turn_last_action_error_details = f"Invalid vertex indices for build_road: {v1_idx}, {v2_idx}. They do not exist on board."
                            # Check if chosen road is in available_actions from the state the LLM used
                            elif tuple(sorted((v1_idx, v2_idx))) not in state_for_current_action.available_actions.get("build_road", []):
                                current_turn_last_action_status = "error_invalid_placement"
                                current_turn_last_action_error_details = f"Road from {v1_idx} to {v2_idx} is not a valid placement according to available_actions. Valid roads: {state_for_current_action.available_actions.get('build_road', [])}."
                            elif currPlayer.build_road(v1_coord, v2_coord, self.board): # player.build_road also checks resources again
                                self.gameLogic.check_longest_road(currPlayer) # Use GameLogicManager
                                current_turn_last_action_status = "success"
                                current_turn_last_action_error_details = f"Successfully built road from {v1_idx} to {v2_idx}."
                            else:
                                current_turn_last_action_status = "error_rule_violation"
                                current_turn_last_action_error_details = f"Failed to build road from {v1_idx} to {v2_idx}. Ensure it's connected and path is clear. Player.build_road returned false."

                        elif action_type == "build_settlement":
                            v_idx = action.get("vertex_index")
                            required_resources = state_for_current_action.action_costs["build_settlement"]
                        can_afford = all(currPlayer.resources.get(res, 0) >= count for res, count in required_resources.items())

                        if v_idx is None:
                            current_turn_last_action_status = "error_missing_input"
                            current_turn_last_action_error_details = "Missing vertex_index for build_settlement."
                        elif not can_afford:
                            missing_res_list = [f"{count} {res}" for res, count in required_resources.items() if currPlayer.resources.get(res, 0) < count]
                            current_turn_last_action_status = "error_insufficient_resources"
                            current_turn_last_action_error_details = f"Cannot build settlement: Insufficient resources. You have {currPlayer.resources}, need {required_resources}. Missing: {', '.join(missing_res_list)}."
                        else:
                            v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                            if not v_coord:
                                current_turn_last_action_status = "error_invalid_input"
                                current_turn_last_action_error_details = f"Invalid vertex index for build_settlement: {v_idx}. Does not exist on board."
                            elif v_idx not in state_for_current_action.available_actions.get("build_settlement", []):
                                current_turn_last_action_status = "error_invalid_placement"
                                current_turn_last_action_error_details = f"Settlement at {v_idx} is not a valid placement. Valid locations: {state_for_current_action.available_actions.get('build_settlement', [])}."
                            elif currPlayer.build_settlement(v_coord, self.board):
                                current_turn_last_action_status = "success"
                                current_turn_last_action_error_details = f"Successfully built settlement at {v_idx}."
                            else:
                                current_turn_last_action_status = "error_rule_violation"
                                current_turn_last_action_error_details = f"Failed to build settlement at {v_idx}. Check distance rules and existing structures. Player.build_settlement returned false."

                        elif action_type == "build_city":
                            v_idx = action.get("vertex_index")
                            required_resources = state_for_current_action.action_costs["build_city"]
                        can_afford = all(currPlayer.resources.get(res, 0) >= count for res, count in required_resources.items())

                        if v_idx is None:
                            current_turn_last_action_status = "error_missing_input"
                            current_turn_last_action_error_details = "Missing vertex_index for build_city."
                        elif not can_afford:
                            missing_res_list = [f"{count} {res}" for res, count in required_resources.items() if currPlayer.resources.get(res, 0) < count]
                            current_turn_last_action_status = "error_insufficient_resources"
                            current_turn_last_action_error_details = f"Cannot build city: Insufficient resources. You have {currPlayer.resources}, need {required_resources}. Missing: {', '.join(missing_res_list)}."
                        else:
                            v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                            if not v_coord:
                                current_turn_last_action_status = "error_invalid_input"
                                current_turn_last_action_error_details = f"Invalid vertex index for build_city: {v_idx}. Does not exist on board."
                            elif v_idx not in state_for_current_action.available_actions.get("build_city", []):
                                current_turn_last_action_status = "error_invalid_placement"
                                current_turn_last_action_error_details = f"City at {v_idx} is not a valid placement (must be on existing settlement). Valid locations: {state_for_current_action.available_actions.get('build_city', [])}."
                            elif currPlayer.build_city(v_coord, self.board): # Assumes player.build_city checks if it's a settlement of the player
                                current_turn_last_action_status = "success"
                                current_turn_last_action_error_details = f"Successfully built city at {v_idx}."
                            else:
                                current_turn_last_action_status = "error_rule_violation"
                                current_turn_last_action_error_details = f"Failed to build city at {v_idx}. Ensure you have a settlement there. Player.build_city returned false."

                        elif action_type == "buy_development_card":
                            required_resources = state_for_current_action.action_costs["buy_development_card"]
                        can_afford = all(currPlayer.resources.get(res,0) >= count for res, count in required_resources.items())
                        if not self.board.devCardStack: # Check if deck is empty
                            current_turn_last_action_status = "error_no_dev_cards_left"
                            current_turn_last_action_error_details = "Cannot buy development card: Deck is empty."
                        elif not can_afford:
                            missing_res_list = [f"{count} {res}" for res, count in required_resources.items() if currPlayer.resources.get(res, 0) < count]
                            current_turn_last_action_status = "error_insufficient_resources"
                            current_turn_last_action_error_details = f"Cannot buy development card: Insufficient resources. You have {currPlayer.resources}, need {required_resources}. Missing: {', '.join(missing_res_list)}."
                        elif currPlayer.draw_devCard(self.board):
                            current_turn_last_action_status = "success"
                            current_turn_last_action_error_details = "Successfully bought a development card."
                        else: # Should not happen if previous checks pass unless draw_devCard has other logic
                            current_turn_last_action_status = "error_unknown_failure"
                            current_turn_last_action_error_details = "Failed to buy development card for an unknown reason."

                        elif action_type == "trade_with_bank":
                            res_give, res_receive = action.get("resource_to_give", "").upper(), action.get("resource_to_receive", "").upper()
                            res_types = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
                            if not res_give or not res_receive or res_give not in res_types or res_receive not in res_types:
                                current_turn_last_action_status = "error_invalid_input"
                                current_turn_last_action_error_details = f"Invalid or missing resources for trade_with_bank. Got give:'{res_give}', receive:'{res_receive}'. Must be valid resource types."
                            else:
                                # Determine actual trade ratio for res_give
                                ratio = 4
                                if state_for_current_action.current_player_bank_trade_ratios["has_general_3_to_1_port"]:
                                    ratio = 3
                                if state_for_current_action.current_player_bank_trade_ratios["specific_2_to_1_ports"].get(res_give):
                                    ratio = 2

                                if currPlayer.resources.get(res_give, 0) < ratio:
                                    current_turn_last_action_status = "error_insufficient_resources"
                                    current_turn_last_action_error_details = f"Cannot trade with bank: Insufficient {res_give}. You have {currPlayer.resources.get(res_give, 0)}, need {ratio} for 1 {res_receive}."
                                elif currPlayer.trade_with_bank(res_give, res_receive): # player.trade_with_bank should use the correct ratio
                                    current_turn_last_action_status = "success"
                                    current_turn_last_action_error_details = f"Successfully traded {ratio} {res_give} for 1 {res_receive} with the bank."
                                else: # player.trade_with_bank returned false
                                    current_turn_last_action_status = "error_unknown_failure"
                                    current_turn_last_action_error_details = f"Bank trade of {res_give} for {res_receive} failed. Player.trade_with_bank returned false."

                        elif action_type == "propose_trade":
                            partner_name = action.get("partner_player_name")
                            offered = action.get("resources_offered", {})
                            requested = action.get("resources_requested")
                            if not partner_name or not offered or not requested:
                                current_turn_last_action_status = "error_missing_input"
                                current_turn_last_action_error_details = f"Invalid propose_trade: Missing partner_player_name, resources_offered, or resources_requested. Got: partner='{partner_name}', offered='{offered}', requested='{requested}'"
                            else:
                                print(f"{currPlayer.name} proposes a trade with {partner_name}. Offering: {offered}, Requesting: {requested}.")
                                target_player = self._get_player_by_name(partner_name)
                                if not target_player:
                                    current_turn_last_action_status = "error_invalid_target"
                                    current_turn_last_action_error_details = f"Trade failed: Player {partner_name} not found."
                                elif target_player == currPlayer:
                                    current_turn_last_action_status = "error_invalid_target"
                                    current_turn_last_action_error_details = "Trade failed: Player cannot trade with themselves."
                                # Check if proposer has the resources to offer
                                elif not all(currPlayer.resources.get(res, 0) >= count for res, count in offered.items()):
                                    missing_offered_res = [f"{count} {res}" for res, count in offered.items() if currPlayer.resources.get(res,0) < count]
                                    current_turn_last_action_status = "error_insufficient_resources"
                                    current_turn_last_action_error_details = f"Cannot propose trade: You don't have the resources you're offering. Missing: {', '.join(missing_offered_res)}."
                                else:
                                    if isinstance(target_player, LLMPlayer):
                                        print(f"Prompting {target_player.name} to respond to the trade offer...")
                                        # Feedback for the target_player will be handled by their own modelState generation
                                        # when they are prompted for the trade_response_action.
                                        # So, no direct feedback setting here for target_player from proposer's action.

                                        # --- START OF NEGOTIATION INITIATION using NegotiationManager ---
                                        print(f"Initiating negotiation between {currPlayer.name} and {target_player.name} using NegotiationManager.")
                                        self.current_negotiation = NegotiationManager(game_turn_started=numTurns)
                                        initial_offer_details_nm = {
                                            "from_player": currPlayer.name,
                                            "to_player": target_player.name,
                                            "resources_offered": offered,
                                            "resources_requested": requested,
                                            "turn": numTurns, # Game turn number
                                            "type": "initial_offer" # Explicitly type it
                                        }
                                        if self.current_negotiation.start_negotiation(currPlayer, target_player, initial_offer_details_nm, game_turn=numTurns):
                                            # --- CALL REFACTORED HANDLE_NEGOTIATION ---
                                            # The handle_negotiation now uses self.current_negotiation
                                            trade_was_successful = self.handle_negotiation(currPlayer, target_player, numTurns) # Pass current turn

                                            if trade_was_successful:
                                                current_turn_last_action_status = "success_negotiation_trade_accepted"
                                                current_turn_last_action_error_details = f"Negotiation with {target_player.name} was successful and trade completed."
                                            else:
                                                # Feedback for initiator (currPlayer) if negotiation ended without acceptance
                                                # (handle_negotiation should set feedback on players involved based on how it ended)
                                                # This part is tricky, as handle_negotiation now sets feedback.
                                                # We rely on currPlayer.feedback_status_for_next_state being set correctly by handle_negotiation.
                                                # If it's not explicitly "success_negotiation_trade_accepted", assume it ended otherwise.
                                                if currPlayer.feedback_status_for_next_state != "success_negotiation_trade_accepted":
                                                    current_turn_last_action_status = currPlayer.feedback_status_for_next_state if currPlayer.feedback_status_for_next_state else "info_negotiation_ended_no_trade"
                                                    current_turn_last_action_error_details = currPlayer.feedback_details_for_next_state if currPlayer.feedback_details_for_next_state else f"Negotiation with {target_player.name} ended without a trade agreement."
                                        else:
                                            current_turn_last_action_status = "error_negotiation_start_failed"
                                            current_turn_last_action_error_details = "Failed to start negotiation with NegotiationManager."
                                            self.current_negotiation = None # Clear if start failed

                                    elif isinstance(target_player, heuristicAIPlayer):
                                        print(f"Heuristic AI {target_player.name} automatically rejects trade with {currPlayer.name} for now.")
                                        current_turn_last_action_status = "info_trade_rejected_heuristic"
                                        current_turn_last_action_error_details = f"Trade with Heuristic AI {target_player.name} was automatically rejected."
                                    else:
                                        current_turn_last_action_status = "error_invalid_target_type"
                                        current_turn_last_action_error_details = f"Trade proposed to non-LLM/non-Heuristic player {target_player.name}. Not handled."

                        elif action_type == "play_knight_card":
                            # Basic check: does player have a knight card?
                            if currPlayer.devCards.get("KNIGHT", 0) > 0:
                                # currPlayer.playKnightCard(self.board) # This method needs to exist and handle robber movement prompt
                                # For now, just acknowledge and set placeholder feedback
                                print(f"{currPlayer.name} wants to play a KNIGHT card.")
                                current_turn_last_action_status = "info_knight_played_concept" # Placeholder
                                current_turn_last_action_error_details = "Knight card play initiated (robber movement part not fully detailed here for LLM feedback yet)."
                                # This is a simplification. Full implementation of play_knight_card is complex.
                                # Example of how it might work IF player.play_dev_card exists and handles knight logic:
                                # if currPlayer.play_dev_card(self, 'KNIGHT'): # Assuming such a method
                                #    current_turn_last_action_status = "success"
                                #    current_turn_last_action_error_details = "Successfully played Knight card. Robber phase will follow if applicable."
                                #    self.gameLogic.check_largest_army(currPlayer) # Use GameLogicManager
                                #    self.player_to_move_robber = currPlayer # Trigger robber movement by this player
                                # else:
                                #    current_turn_last_action_status = "error_play_knight_failed"
                                #    current_turn_last_action_error_details = "Failed to play Knight card (e.g., already played dev card this turn)."
                            else:
                                current_turn_last_action_status = "error_no_knight_card"
                                current_turn_last_action_error_details = "Cannot play Knight card: You do not have one."
                        # Removed "elif action_type == "end_turn":" because it's handled at the top of the loop
                        else: # Handles unknown actions
                            current_turn_last_action_status = "error_unknown_action"
                            current_turn_last_action_error_details = f"Unknown or unsupported main action type: '{action_type}'. Action ignored."
                            print(f"Unknown or unsupported main action type: {action_type} for {currPlayer.name}. Action ignored, player can try another action or end turn.")

                        # Store feedback for the LLM player's next modelState generation (within this turn's loop)
                        # This feedback is for the *next action decision* by the LLM in the same turn.
                        currPlayer.feedback_status_for_next_state = current_turn_last_action_status
                        currPlayer.feedback_details_for_next_state = current_turn_last_action_error_details

                        # Add memory entry for LLMPlayer
                        action_summary_for_memory = f"Action: {action_type}"
                        if action_type == "build_road": action_summary_for_memory += f" ({action.get('v1_index')}-{action.get('v2_index')})"
                        elif action_type in ["build_settlement", "build_city"]: action_summary_for_memory += f" at {action.get('vertex_index')}"
                        elif action_type == "propose_trade": action_summary_for_memory += f" with {action.get('partner_player_name')}"
                        # Add more details for other actions if useful for memory

                        memory_entry = (f"Turn {numTurns}: My action was {action_summary_for_memory}. "
                                        f"Outcome: {current_turn_last_action_status} "
                                        f"({current_turn_last_action_error_details if current_turn_last_action_error_details else 'No details'}).")
                        currPlayer.add_memory_entry(memory_entry)

                        # Print the feedback that will be available for the next state
                        print(f"Feedback for {currPlayer.name}'s next state: Status='{currPlayer.feedback_status_for_next_state}', Details='{currPlayer.feedback_details_for_next_state}'")
                        # print(f"Memory for {currPlayer.name}: {currPlayer.memory}") # Optional: for debugging

                elif isinstance(currPlayer, heuristicAIPlayer):
                    print(f"{currPlayer.name} (Heuristic) is making moves...")
                    currPlayer.move(self.board) # Heuristic AI makes all its moves in one go.

                    # Check for game conditions after heuristic player's move
                    self.gameLogic.check_longest_road(currPlayer)
                    self.gameLogic.check_largest_army(currPlayer) # Assuming heuristic might play knights

                # ... (common turn finalization, victory check, etc. as before) ...
                print(f"Player:{currPlayer.name}, Resources:{currPlayer.resources}, Points: {currPlayer.victoryPoints}")
                self.boardView.displayGameScreen()
                if not self.gameOver : pygame.time.delay(300)
                if currPlayer.victoryPoints >= self.maxPoints: self.gameOver = True; break
            if self.gameOver: break
                                   
# Initialize new game and run
if __name__ == "__main__":
    newGame_AI = catanAIGame()