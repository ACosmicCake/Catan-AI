#Settlers of Catan
#Gameplay class with pygame with AI players

from board import *
from gameView import *
from player import *
from heuristicAIPlayer import * # Keep for potential mixed games or fallback
from modelState import modelState # Should already be there
from LLMPlayer import LLMPlayer # Add this import
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

        # Chat histories
        self.global_chat_history = []
        self.private_chat_histories = {} # Key: tuple(sorted_player_names), Value: list of messages
        self.communication_phase_active = False # Flag to manage new game loop state
        self.active_private_chat_participants = None # Tuple (player1_name, player2_name) or None

        #Dictionary to keep track of dice statistics
        self.diceStats = {2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0}
        self.diceStats_list = []

        while(self.numPlayers not in [3,4]): #Only accept 3 and 4 player games
            try:
                self.numPlayers = int(input("Enter Number of Players (3 or 4):"))
            except:
                print("Please input a valid number")

        print("Initializing game with {} players...".format(self.numPlayers))
        print("Note that Player 1 goes first, Player 2 second and so forth.")
        
        #Initialize blank player queue and initial set up of roads + settlements
        self.playerQueue = queue.Queue(self.numPlayers)
        self.gameSetup = True #Boolean to take care of setup phase
        # self.robber_action_pending = False # Old flag, remove or ensure it's removed
        self.player_to_move_robber = None # New flag: stores the player object

        #Initialize boardview object
        self.boardView = catanGameView(self.board, self)

        #Functiont to go through initial set up
        self.build_initial_settlements()
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
                print(f"Creating LLM Player: {playerName} with color {player_color} and type {llm_type}")
                newPlayer = LLMPlayer(playerName, player_color, llm_type)
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
                last_s_status, last_s_error = None, None
                placed_settlement_v_idx = None

                while not settlement_placed_successfully and settlement_placement_attempts < max_settlement_placement_attempts:
                    settlement_placement_attempts += 1
                    if settlement_placement_attempts > 1: print(f"Re-prompting {player_i.name} for settlement (attempt {settlement_placement_attempts})")

                    current_model_state_settlement = modelState(self, player_i,
                                                                last_action_status=last_s_status,
                                                                last_action_error_details=last_s_error)
                    last_s_status, last_s_error = None, None # Reset for next potential error

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
                        else:
                            last_s_status = "invalid_placement"
                            last_s_error = f"Vertex {v_idx} is not a valid setup settlement location (e.g. occupied, too close, or rule violation). Valid are: {current_model_state_settlement.available_actions.get('build_settlement', [])}"
                    else:
                        last_s_status = "invalid_action_type_or_format"
                        last_s_error = f"Expected 'build_settlement' action with 'vertex_index'. Got: {action_settlement}"

                if not settlement_placed_successfully:
                    print(f"CRITICAL: {player_i.name} failed to place first settlement after {max_settlement_placement_attempts} attempts. Halting setup for this player.")
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

                    last_r_status, last_r_error = None, None # Initialize before loop

                    while not road_placed_successfully and road_placement_attempts < max_road_placement_attempts:
                        road_placement_attempts += 1
                        if road_placement_attempts > 1:
                            print(f"Re-prompting {player_i.name} for road placement (attempt {road_placement_attempts}).")

                        current_model_state_road = modelState(self, player_i,
                                                              setup_road_placement_pending=True,
                                                              last_settlement_vertex_index=placed_settlement_v_idx, # Use the v_idx from successful settlement
                                                              last_action_status=last_r_status,
                                                              last_action_error_details=last_r_error)
                        last_r_status, last_r_error = None, None # Reset for next potential error

                        action_road = player_i.get_llm_move(current_model_state_road)
                        print(f"{player_i.name} (Thoughts for road: {player_i.thoughts}) -> Action: {action_road}")
                        action_type_road = action_road.get("type")
                        v1_idx_road = action_road.get("v1_index")
                        v2_idx_road = action_road.get("v2_index")

                        if action_type_road == "build_road" and v1_idx_road is not None and v2_idx_road is not None:
                            chosen_road_pair = tuple(sorted((v1_idx_road, v2_idx_road)))
                            # Validate connection to the new settlement
                            if not (v1_idx_road == placed_settlement_v_idx or v2_idx_road == placed_settlement_v_idx):
                                last_r_status = "invalid_placement"
                                last_r_error = f"Road {chosen_road_pair} must connect to the new settlement at vertex {placed_settlement_v_idx}."
                            elif chosen_road_pair in current_model_state_road.available_actions.get("build_road", []):
                                v1_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx_road)
                                v2_coord = self.board.vertex_index_to_pixel_dict.get(v2_idx_road)
                                if player_i.build_road(v1_coord, v2_coord, self.board, setup_phase=True):
                                    print(f"{player_i.name} built initial road from {v1_idx_road} to {v2_idx_road}.")
                                    road_placed_successfully = True
                                else: # Should not happen if resources are not an issue in setup and road is valid
                                    last_r_status = "internal_error"
                                    last_r_error = "player.build_road returned False for setup road unexpectedly."
                            else:
                                last_r_status = "invalid_placement"
                                last_r_error = f"Road {chosen_road_pair} is not a valid setup road. Valid are: {current_model_state_road.available_actions.get('build_road', [])}"
                        else:
                            last_r_status = "invalid_action_type_or_format"
                            last_r_error = f"Expected 'build_road' action with 'v1_index' and 'v2_index'. Got: {action_road}"

                    if not road_placed_successfully:
                        print(f"CRITICAL: {player_i.name} failed to place first road after {max_road_placement_attempts} attempts.")
                        # No random fallback. Game might be in inconsistent state if road is not placed.
                # else: # This 'else' corresponds to 'if placed_settlement_v_idx is not None'
                    # print(f"{player_i.name} did not place a settlement, so no road will be placed.") # Optional: for debugging

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
                last_s_status, last_s_error = None, None
                placed_settlement_v_idx = None

                while not settlement_placed_successfully and settlement_placement_attempts < max_settlement_placement_attempts:
                    settlement_placement_attempts += 1
                    if settlement_placement_attempts > 1: print(f"Re-prompting {player_i.name} for 2nd settlement (attempt {settlement_placement_attempts})")

                    current_model_state_settlement = modelState(self, player_i,
                                                                last_action_status=last_s_status,
                                                                last_action_error_details=last_s_error)
                    last_s_status, last_s_error = None, None # Reset

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
                        else:
                            last_s_status = "invalid_placement"
                            last_s_error = f"Vertex {v_idx} is not a valid setup settlement location. Valid are: {current_model_state_settlement.available_actions.get('build_settlement', [])}"
                    else:
                        last_s_status = "invalid_action_type_or_format"
                        last_s_error = f"Expected 'build_settlement' action with 'vertex_index'. Got: {action_settlement}"

                if not settlement_placed_successfully:
                    print(f"CRITICAL: {player_i.name} failed to place 2nd settlement after {max_settlement_placement_attempts} attempts. Halting setup.")
                    player_i.last_placed_settlement_v_idx = None

                self.boardView.displayGameScreen()
                pygame.time.delay(500)

                # --- LLM places second road ---
                if placed_settlement_v_idx is not None: # Only proceed if settlement was placed successfully
                    print(f"{player_i.name} to place second road connected to settlement at {placed_settlement_v_idx}.")
                    road_placement_attempts = 0
                    road_placed_successfully = False
                    max_road_placement_attempts = 3
                    last_r_status, last_r_error = None, None # Initialize before loop

                    while not road_placed_successfully and road_placement_attempts < max_road_placement_attempts:
                        road_placement_attempts += 1
                        if road_placement_attempts > 1:
                            print(f"Re-prompting {player_i.name} for 2nd road (attempt {road_placement_attempts})")

                        current_model_state_road = modelState(self, player_i,
                                                              setup_road_placement_pending=True,
                                                              last_settlement_vertex_index=placed_settlement_v_idx,
                                                              last_action_status=last_r_status,
                                                              last_action_error_details=last_r_error)
                        last_r_status, last_r_error = None, None # Reset for next potential error

                        action_road = player_i.get_llm_move(current_model_state_road)
                        print(f"{player_i.name} (Thoughts for 2nd road: {player_i.thoughts}) -> Action: {action_road}")
                        action_type_road = action_road.get("type")
                        v1_idx_road = action_road.get("v1_index")
                        v2_idx_road = action_road.get("v2_index")

                        if action_type_road == "build_road" and v1_idx_road is not None and v2_idx_road is not None:
                            chosen_road_pair = tuple(sorted((v1_idx_road, v2_idx_road)))
                            if not (v1_idx_road == placed_settlement_v_idx or v2_idx_road == placed_settlement_v_idx):
                                last_r_status = "invalid_placement"
                                last_r_error = f"Road {chosen_road_pair} must connect to the new settlement at vertex {placed_settlement_v_idx}."
                            elif chosen_road_pair in current_model_state_road.available_actions.get("build_road", []):
                                v1_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx_road)
                                v2_coord = self.board.vertex_index_to_pixel_dict.get(v2_idx_road)
                                if player_i.build_road(v1_coord, v2_coord, self.board, setup_phase=True):
                                    print(f"{player_i.name} built 2nd initial road from {v1_idx_road} to {v2_idx_road}.")
                                    road_placed_successfully = True
                                else:
                                    last_r_status = "internal_error"
                                    last_r_error = "player.build_road returned False for 2nd setup road unexpectedly."
                            else:
                                last_r_status = "invalid_placement"
                                last_r_error = f"Road {chosen_road_pair} is not a valid 2nd setup road. Valid are: {current_model_state_road.available_actions.get('build_road', [])}"
                        else:
                            last_r_status = "invalid_action_type_or_format"
                            last_r_error = f"Expected 'build_road' action with 'v1_index' and 'v2_index'. Got: {action_road}"

                    if not road_placed_successfully:
                        print(f"CRITICAL: {player_i.name} failed to place 2nd road after {max_road_placement_attempts} attempts.")
                # else: # Corresponds to 'if placed_settlement_v_idx is not None'
                    # print(f"{player_i.name} did not place second settlement, so no second road will be placed.") # Optional

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


    #Function to roll dice 
    def rollDice(self):
        dice_1 = np.random.randint(1,7)
        dice_2 = np.random.randint(1,7)
        diceRoll = dice_1 + dice_2
        print("Dice Roll = ", diceRoll, "{", dice_1, dice_2, "}")

        return diceRoll

    #Function to update resources for all players
    def update_playerResources(self, diceRoll, currentPlayer):
        if diceRoll != 7: # Collect resources if not a 7
            # ... (existing resource collection logic - no changes here) ...
            hexResourcesRolled = self.board.getHexResourceRolled(diceRoll)
            for player_i in list(self.playerQueue.queue):
                for settlementCoord in player_i.buildGraph['SETTLEMENTS']:
                    for adjacentHex in self.board.boardGraph[settlementCoord].adjacentHexList:
                        if(adjacentHex in hexResourcesRolled and self.board.hexTileDict[adjacentHex].robber == False):
                            resourceGenerated = self.board.hexTileDict[adjacentHex].resource.type
                            player_i.resources[resourceGenerated] += 1
                            print(f"{player_i.name} collects 1 {resourceGenerated} from Settlement")
                for cityCoord in player_i.buildGraph['CITIES']:
                    for adjacentHex in self.board.boardGraph[cityCoord].adjacentHexList:
                        if(adjacentHex in hexResourcesRolled and self.board.hexTileDict[adjacentHex].robber == False):
                            resourceGenerated = self.board.hexTileDict[adjacentHex].resource.type
                            player_i.resources[resourceGenerated] += 2
                            print(f"{player_i.name} collects 2 {resourceGenerated} from City")
                # Display player info (optional here, maybe more suitable in playCatan after all actions)
                # print(f"Player:{player_i.name}, Resources:{player_i.resources}, Points: {player_i.victoryPoints}")
                # print(f"MaxRoadLength:{player_i.maxRoadLength}, Longest Road:{player_i.longestRoadFlag}\n")

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


    #function to check if a player has the longest road - after building latest road
    def check_longest_road(self, player_i):
        if(player_i.maxRoadLength >= 5): #Only eligible if road length is at least 5
            longestRoad = True
            for p in list(self.playerQueue.queue):
                if(p.maxRoadLength >= player_i.maxRoadLength and p != player_i): #Check if any other players have a longer road
                    longestRoad = False
            
            if(longestRoad and player_i.longestRoadFlag == False): #if player_i takes longest road and didn't already have longest road
                #Set previous players flag to false and give player_i the longest road points
                prevPlayer = ''
                for p in list(self.playerQueue.queue):
                    if(p.longestRoadFlag):
                        p.longestRoadFlag = False
                        p.victoryPoints -= 2
                        prevPlayer = 'from Player ' + p.name
    
                player_i.longestRoadFlag = True
                player_i.victoryPoints += 2

                print("Player {} takes Longest Road {}".format(player_i.name, prevPlayer))

    #function to check if a player has the largest army - after playing latest knight
    def check_largest_army(self, player_i):
        if(player_i.knightsPlayed >= 3): #Only eligible if at least 3 knights are player
            largestArmy = True
            for p in list(self.playerQueue.queue):
                if(p.knightsPlayed >= player_i.knightsPlayed and p != player_i): #Check if any other players have more knights played
                    largestArmy = False
            
            if(largestArmy and player_i.largestArmyFlag == False): #if player_i takes largest army and didn't already have it
                #Set previous players flag to false and give player_i the largest points
                prevPlayer = ''
                for p in list(self.playerQueue.queue):
                    if(p.largestArmyFlag):
                        p.largestArmyFlag = False
                        p.victoryPoints -= 2
                        prevPlayer = 'from Player ' + p.name
    
                player_i.largestArmyFlag = True
                player_i.victoryPoints += 2

                print("Player {} takes Largest Army {}".format(player_i.name, prevPlayer))



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

        player_who_moves_robber.move_robber(target_hex_idx, self.board, player_to_rob_obj)

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

                pygame.event.pump()
                diceNum = self.rollDice()
                # update_playerResources now sets pending_discard_count on players and player_to_move_robber on self
                self.update_playerResources(diceNum, currPlayer)
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
                                currPlayer.move_robber(hex_idx, self.board, player_to_rob_object)
                                print(f"{currPlayer.name} moved robber to hex {hex_idx}" + (f" and robbed {player_name_to_rob}" if player_name_to_rob else "."))
                                executed_robber_move = True
                        if not executed_robber_move:
                            print(f"{currPlayer.name} (LLM) failed to provide valid 'move_robber' action. Randomly placing.")
                            self._execute_random_robber_move(currPlayer)

                    elif isinstance(currPlayer, heuristicAIPlayer):
                        print(f"{currPlayer.name} (Heuristic) moving robber...")
                        currPlayer.heuristic_move_robber(self.board) # Heuristic handles its robber move

                    self.player_to_move_robber = None # Reset flag
                    self.boardView.displayGameScreen(); pygame.time.delay(300)

                # --- Main Turn Actions ---
                if isinstance(currPlayer, LLMPlayer):
                    # ... (LLM main turn action logic as before) ...
                    print(f"{currPlayer.name} taking main turn actions...")
                    # Create modelState without private_chat_active=True for normal turn actions
                    state_for_main_turn = modelState(self, currPlayer, private_chat_active=False, communication_phase_active=False)
                    action = currPlayer.get_llm_move(state_for_main_turn)
                    print(f"{currPlayer.name} (Main Turn Thoughts: {currPlayer.thoughts}) -> Action: {action}")

                    action_type = action.get("type")

                    # Handle global message during main turn if chosen
                    if action_type == "send_global_message":
                        message = action.get("message")
                        if message:
                            print(f"[Global Chat | {currPlayer.name}]: {message}")
                            self.global_chat_history.append({"player": currPlayer.name, "message": message})
                            # Potentially get another action after sending a message, or end turn.
                            # For now, sending a global message is a turn-ending action unless combined with others.
                            # The current LLM prompt implies it's one of the main actions. Let's assume it's final for now.
                            # Update: The prompt allows it as one of many. If it's chosen, we process and then player might do more.
                            # This might need a loop or re-prompting if we want multiple actions per turn.
                            # For simplicity, let's assume for now if send_global_message is the primary action, it's the only one processed here.
                            # Re-evaluate if LLM is expected to do more after this.
                            # If other actions are possible, this 'if' should not be an 'elif' chain.
                            # Based on current structure, we process one main action.

                    elif action_type == "initiate_private_chat":
                        recipient_name = action.get("recipient_name")
                        opening_message = action.get("opening_message")
                        recipient_player = self._get_player_by_name(recipient_name)

                        if recipient_player and isinstance(recipient_player, LLMPlayer) and recipient_player != currPlayer:
                            if opening_message:
                                print(f"{currPlayer.name} is starting a private chat with {recipient_name}.")
                                self.handle_private_chat(currPlayer, recipient_player, opening_message)
                            else:
                                print(f"{currPlayer.name} tried to initiate chat with {recipient_name} but provided no opening message.")
                        elif recipient_player == currPlayer:
                            print(f"{currPlayer.name} tried to initiate chat with themselves. Action ignored.")
                        elif not isinstance(recipient_player, LLMPlayer):
                            print(f"{currPlayer.name} tried to initiate chat with {recipient_name}, but they are not an LLM player or cannot chat. Action ignored.")
                        else:
                            print(f"Player {recipient_name} not found for private chat initiated by {currPlayer.name}.")
                        # After chat, turn effectively ends or continues based on handle_private_chat behavior.
                        # For now, let's assume initiating a chat is the main action for the turn.

                    elif action_type == "build_road":
                        v1_idx, v2_idx = action.get("v1_index"), action.get("v2_index")
                        if v1_idx is not None and v2_idx is not None:
                            v1_coord, v2_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx), self.board.vertex_index_to_pixel_dict.get(v2_idx)
                            if v1_coord and v2_coord: currPlayer.build_road(v1_coord, v2_coord, self.board); self.check_longest_road(currPlayer)
                            else: print(f"Invalid vertex indices for build_road: {v1_idx}, {v2_idx}")
                        else: print(f"Missing vertex indices for build_road action for {currPlayer.name}.")
                    elif action_type == "build_settlement":
                        v_idx = action.get("vertex_index")
                        if v_idx is not None:
                            v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                            if v_coord: currPlayer.build_settlement(v_coord, self.board)
                            else: print(f"Invalid vertex index for build_settlement: {v_idx}")
                        else: print(f"Missing vertex index for build_settlement action for {currPlayer.name}.")
                    elif action_type == "build_city":
                        v_idx = action.get("vertex_index")
                        if v_idx is not None:
                            v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                            if v_coord and v_coord in currPlayer.buildGraph['SETTLEMENTS']: currPlayer.build_city(v_coord, self.board)
                            else: print(f"Cannot build city at {v_idx} for {currPlayer.name}")
                        else: print(f"Missing vertex index for build_city action for {currPlayer.name}.")
                    elif action_type == "buy_development_card":
                        currPlayer.draw_devCard(self.board)
                    elif action_type == "trade_with_bank":
                        res_give, res_receive = action.get("resource_to_give"), action.get("resource_to_receive")
                        if res_give and res_receive: currPlayer.trade_with_bank(res_give.upper(), res_receive.upper())
                        else: print(f"Missing resources for trade_with_bank for {currPlayer.name}")
                    elif action_type == "propose_trade":
                        partner_name = action.get("partner_player_name")
                        offered = action.get("resources_offered")
                        requested = action.get("resources_requested")
                        if partner_name and offered and requested:
                            print(f"{currPlayer.name} proposes a trade with {partner_name}. Offering: {offered}, Requesting: {requested}.")
                            target_player = self._get_player_by_name(partner_name)
                            if not target_player:
                                print(f"Trade failed: Player {partner_name} not found.")
                            elif target_player == currPlayer:
                                print(f"Trade failed: Player cannot trade with themselves.")
                            else:
                                if isinstance(target_player, LLMPlayer):
                                    print(f"Prompting {target_player.name} to respond to the trade offer...")
                                    trade_state = modelState(self, target_player,
                                                             trade_offer_pending=True,
                                                             trade_offering_player_name=currPlayer.name,
                                                             trade_resources_offered_to_you=offered,
                                                             trade_resources_requested_from_you=requested)
                                    trade_response_action = target_player.get_llm_move(trade_state)

                                    print(f"{target_player.name} (Trade Offer Thoughts: {target_player.thoughts}) -> Response: {trade_response_action}")

                                    if trade_response_action.get("type") == "accept_trade":
                                        # Validate trade feasibility before execution
                                        can_proposer_give = all(currPlayer.resources.get(res, 0) >= count for res, count in offered.items())
                                        can_target_give = all(target_player.resources.get(res, 0) >= count for res, count in requested.items())

                                        if can_proposer_give and can_target_give:
                                            # Execute trade
                                            for res, count in offered.items():
                                                currPlayer.resources[res] -= count
                                                target_player.resources[res] += count
                                            for res, count in requested.items():
                                                target_player.resources[res] -= count
                                                currPlayer.resources[res] += count
                                            print(f"Trade accepted and completed between {currPlayer.name} and {target_player.name}!")
                                            print(f"{currPlayer.name} new resources: {currPlayer.resources}")
                                            print(f"{target_player.name} new resources: {target_player.resources}")
                                        else:
                                            print(f"Trade accepted by {target_player.name}, but resources are insufficient. Trade cancelled.")
                                            if not can_proposer_give: print(f"{currPlayer.name} lacks resources for offer.")
                                            if not can_target_give: print(f"{target_player.name} lacks resources for request.")
                                    else: # Implicitly reject_trade or invalid response
                                        print(f"{target_player.name} rejected the trade or gave an invalid response.")
                                elif isinstance(target_player, heuristicAIPlayer):
                                    # Basic heuristic: always reject for now, or implement simple logic
                                    print(f"Heuristic AI {target_player.name} automatically rejects trade with {currPlayer.name} for now.")
                                else: # Human player target (not handled in AIGame, but for completeness)
                                    print(f"Trade proposed to human player {target_player.name}. This is not handled in AI-only game mode.")
                        else:
                            print(f"Invalid propose_trade action from {currPlayer.name}: Missing parameters.")
                    elif action_type == "play_knight_card":
                        print(f"{currPlayer.name} wants to play a KNIGHT card (conceptual - not fully implemented).")
                        pass
                    elif action_type == "end_turn":
                        print(f"{currPlayer.name} ends their turn.")
                    else: # Unknown action or if LLM robber phase returned non-robber action
                        print(f"Unknown or unsupported main action type: {action_type} for {currPlayer.name}. Player ends turn by default.")

                elif isinstance(currPlayer, heuristicAIPlayer):
                    # ... (Heuristic main turn action logic as before) ...
                    print(f"{currPlayer.name} (Heuristic) is making moves...")
                    currPlayer.move(self.board)
                    self.check_longest_road(currPlayer)

                # ... (common turn finalization, victory check, etc. as before) ...
                print(f"Player:{currPlayer.name}, Resources:{currPlayer.resources}, Points: {currPlayer.victoryPoints}")
                self.boardView.displayGameScreen()
                if not self.gameOver : pygame.time.delay(300)
                if currPlayer.victoryPoints >= self.maxPoints: self.gameOver = True; break
            if self.gameOver: break
                                   
# Initialize new game and run
if __name__ == "__main__":
    newGame_AI = catanAIGame()