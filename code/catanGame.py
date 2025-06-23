#Settlers of Catan
#Gameplay class with pygame

from board import *
from gameView import *
from player import *
from heuristicAIPlayer import *
from LLMPlayer import LLMPlayer # Added import
from modelState import modelState # Added import
import queue
import numpy as np
import sys, pygame

#Catan gameplay class definition
class catanGame():
    #Create new gameboard
    def __init__(self):
        print("Initializing Settlers of Catan Board...")
        self.board = catanBoard()

        #Game State variables
        self.gameOver = False
        self.maxPoints = 8
        self.numPlayers = 0

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

        #Initialize boardview object
        self.boardView = catanGameView(self.board, self)
        self.robber_action_pending_for_player = None # Added for managing mandatory robber moves

        #Run functions to view board and vertex graph
        #self.board.printGraph()

        #Functiont to go through initial set up
        self.build_initial_settlements()

        #Display initial board
        self.boardView.displayGameScreen()

    # Helper function for LLM setup phase
    def handle_llm_setup_placement(self, llm_player, placement_type, previous_settlement_idx=None):
        # placement_type can be "settlement" or "road"
        # previous_settlement_idx is for placing a road connected to the just-placed settlement

        action_attempts = 0
        max_action_attempts = 5 # Max attempts for a single setup placement
        placed_successfully = False

        vertex_index_to_pixel_map = self.board.vertex_index_to_pixel_dict
        last_action_status = None # Initialize here
        last_action_error_details = None # Initialize here

        while not placed_successfully and action_attempts < max_action_attempts:
            action_attempts += 1

            # Create model state for setup
            is_setup_road_pending = (placement_type == "road")

            current_model_state = modelState(self, llm_player,
                                             setup_road_placement_pending=is_setup_road_pending,
                                             last_settlement_vertex_index=previous_settlement_idx if is_setup_road_pending else None)

            if last_action_status: # Pass error from previous attempt in this loop
                current_model_state.last_action_status = last_action_status
                current_model_state.last_action_error_details = last_action_error_details
                # Reset for the next attempt's own error, or if it succeeds
                last_action_status = None
                last_action_error_details = None

            llm_action = llm_player.get_llm_move(current_model_state)
            action_type = llm_action.get("type")

            print(f"LLM Player {llm_player.name} (Setup - {placement_type}) tries action: {llm_action}")

            if placement_type == "settlement" and action_type == "build_settlement":
                v_idx = llm_action.get("vertex_index")
                if v_idx is not None:
                    potential_settlements_indices = current_model_state.available_actions.get("build_settlement", [])
                    if v_idx in potential_settlements_indices:
                        target_v_coord = vertex_index_to_pixel_map.get(v_idx)
                        if target_v_coord:
                            # Simplified direct update for setup settlement:
                            # Check again directly as a safeguard, though available_actions should be source of truth
                            if self.board.boardGraph[target_v_coord].isColonised:
                                last_action_status = "invalid_placement"
                                last_action_error_details = "Setup settlement spot is already taken (checked again)."
                            else:
                                llm_player.buildGraph['SETTLEMENTS'].append(target_v_coord)
                                llm_player.settlementsLeft -=1
                                llm_player.victoryPoints +=1 # VP for setup settlements
                                self.board.updateBoardGraph_settlement(target_v_coord, llm_player)
                                if((self.board.boardGraph[target_v_coord].port != False) and (self.board.boardGraph[target_v_coord].port not in llm_player.portList)):
                                    llm_player.portList.append(self.board.boardGraph[target_v_coord].port)
                                    print(f"{llm_player.name} acquired port: {self.board.boardGraph[target_v_coord].port}")
                                print(f"LLM {llm_player.name} (Setup) placed settlement at VI {v_idx}.")
                                # placed_successfully = True # Not needed, direct return
                                return v_idx # Return the index of the placed settlement
                        else:
                            last_action_status = "internal_error"
                            last_action_error_details = f"Invalid vertex index {v_idx} for setup settlement (no pixel map)."
                    else:
                        last_action_status = "invalid_placement"
                        last_action_error_details = f"Proposed setup settlement VI {v_idx} is invalid (not in available actions: {potential_settlements_indices})."
                else:
                    last_action_status = "invalid_action_format"
                    last_action_error_details = "Missing 'vertex_index' for setup build_settlement."

            elif placement_type == "road" and action_type == "build_road":
                v1_idx = llm_action.get("v1_index")
                v2_idx = llm_action.get("v2_index")
                if v1_idx is not None and v2_idx is not None:
                    # Ensure one of the vertices is the previous_settlement_idx
                    # And the other one forms a valid road from available_actions
                    # The available_actions for setup road should already be filtered to connect to previous_settlement_idx.
                    chosen_road_pair = tuple(sorted((v1_idx, v2_idx)))
                    if not (v1_idx == previous_settlement_idx or v2_idx == previous_settlement_idx):
                         last_action_status = "invalid_placement"
                         last_action_error_details = f"Setup road {chosen_road_pair} must connect to the new settlement at vertex {previous_settlement_idx}."
                    else:
                        potential_roads_idx_pairs = current_model_state.available_actions.get("build_road", [])
                        if chosen_road_pair in potential_roads_idx_pairs:
                            target_v1_coord = vertex_index_to_pixel_map.get(v1_idx)
                            target_v2_coord = vertex_index_to_pixel_map.get(v2_idx)
                            if target_v1_coord and target_v2_coord:
                                if llm_player.build_road(target_v1_coord, target_v2_coord, self.board, setup_phase=True):
                                    print(f"LLM {llm_player.name} (Setup) built road {v1_idx}-{v2_idx}.")
                                    placed_successfully = True
                                else:
                                    last_action_status = "internal_error" # Should not fail if logic is right
                                    last_action_error_details = "Failed to build setup road despite valid inputs (player.build_road returned False unexpectedly)."
                            else:
                                last_action_status = "internal_error"
                                last_action_error_details = f"Invalid vertex indices {v1_idx}, {v2_idx} for setup road (no pixel map)."
                        else:
                            last_action_status = "invalid_placement"
                            last_action_error_details = f"Proposed setup road {chosen_road_pair} is invalid (not in available actions: {potential_roads_idx_pairs})."
                else:
                    last_action_status = "invalid_action_format"
                    last_action_error_details = "Missing 'v1_index' or 'v2_index' for setup build_road."
            else:
                last_action_status = "invalid_action_type"
                last_action_error_details = f"Expected action '{'build_settlement' if placement_type == 'settlement' else 'build_road'}' during setup but got '{action_type}'."

            if not placed_successfully:
                print(f"LLM {llm_player.name} (Setup - {placement_type}) invalid attempt: {last_action_status} - {last_action_error_details}. Trying again ({action_attempts}/{max_action_attempts}).")

        if not placed_successfully:
            print(f"LLM Player {llm_player.name} (Setup - {placement_type}) failed to make a valid placement after {max_action_attempts} attempts. CRITICAL FAILURE.")
            return None # Indicate failure for both types if loop exhausted

        # If loop finished due to success (placed_successfully = True):
        # This part of the code should ideally only be reached if placement_type was 'road' and it was successful.
        # Settlement success should have returned v_idx from within the loop.
        if placement_type == "road":
            return True # Successful road placement

        # Fallback, should not be reached if logic is correct, especially for settlements.
        print(f"Error: LLM Setup ({placement_type}) logic flaw or unexpected success state. Assumed failure.")
        return None

    #Function to initialize players + build initial settlements for players
    def build_initial_settlements(self):
        #Initialize new players with names and colors
        playerColors = ['black', 'darkslateblue', 'magenta4', 'orange1']
        for i in range(self.numPlayers -1):
            playerNameInput = input("Enter Player {} name: ".format(i+1))
            newPlayer = player(playerNameInput, playerColors[i])
            self.playerQueue.put(newPlayer)

        test_AI_player = heuristicAIPlayer('Random-Greedy-AI', playerColors[i+1]) #Add the AI Player last
        test_AI_player.updateAI()
        self.playerQueue.put(test_AI_player)

        playerList = list(self.playerQueue.queue)

        self.boardView.displayGameScreen() #display the initial gameScreen
        print("Displaying Initial GAMESCREEN!")

        #Build Settlements and roads of each player forwards
        for player_i in playerList: 
            if isinstance(player_i, LLMPlayer):
                print(f"\n--- {player_i.name} (LLM) Initial Setup: 1st Settlement & Road ---")
                # First settlement
                print(f"{player_i.name}, place your first settlement.")
                settlement1_v_idx = self.handle_llm_setup_placement(player_i, "settlement")
                if settlement1_v_idx is None: # Failed to place
                    print(f"CRITICAL: LLM {player_i.name} failed to place initial settlement. Game cannot continue correctly.")
                    # Handle this critical failure appropriately - maybe exit or manual override
                    return # Or sys.exit()
                self.boardView.displayGameScreen()

                # First road
                print(f"{player_i.name}, place your first road connected to settlement at {settlement1_v_idx}.")
                road1_success = self.handle_llm_setup_placement(player_i, "road", previous_settlement_idx=settlement1_v_idx)
                if not road1_success:
                    print(f"CRITICAL: LLM {player_i.name} failed to place initial road. Game cannot continue correctly.")
                    return # Or sys.exit()
                self.boardView.displayGameScreen()

            elif player_i.isAI and hasattr(player_i, 'initial_setup'): # HeuristicAI
                player_i.initial_setup(self.board)
                self.boardView.displayGameScreen() # Show AI placement
            
            else: # Human player
                self.build(player_i, 'SETTLE')
                self.boardView.displayGameScreen()
                
                self.build(player_i, 'ROAD')
                self.boardView.displayGameScreen()
        
        #Build Settlements and roads of each player reverse
        playerList.reverse()
        for player_i in playerList: 
            if isinstance(player_i, LLMPlayer):
                print(f"\n--- {player_i.name} (LLM) Initial Setup: 2nd Settlement & Road ---")
                # Second settlement
                print(f"{player_i.name}, place your second settlement.")
                settlement2_v_idx = self.handle_llm_setup_placement(player_i, "settlement")
                if settlement2_v_idx is None:
                    print(f"CRITICAL: LLM {player_i.name} failed to place second initial settlement. Game cannot continue correctly.")
                    return
                self.boardView.displayGameScreen()

                # Second road
                print(f"{player_i.name}, place your second road connected to settlement at {settlement2_v_idx}.")
                road2_success = self.handle_llm_setup_placement(player_i, "road", previous_settlement_idx=settlement2_v_idx)
                if not road2_success:
                    print(f"CRITICAL: LLM {player_i.name} failed to place second initial road. Game cannot continue correctly.")
                    return
                self.boardView.displayGameScreen()

            elif player_i.isAI and hasattr(player_i, 'initial_setup'): # HeuristicAI
                player_i.initial_setup(self.board) # Heuristic AI places its second set
                self.boardView.displayGameScreen()

            else: # Human player
                self.build(player_i, 'SETTLE')
                self.boardView.displayGameScreen()

                self.build(player_i, 'ROAD')
                self.boardView.displayGameScreen()

            #Initial resource generation
            #check each adjacent hex to latest settlement
            for adjacentHex in self.board.boardGraph[player_i.buildGraph['SETTLEMENTS'][-1]].adjacentHexList:
                resourceGenerated = self.board.hexTileDict[adjacentHex].resource.type
                if(resourceGenerated != 'DESERT'):
                    player_i.resources[resourceGenerated] += 1
                    print("{} collects 1 {} from Settlement".format(player_i.name, resourceGenerated))

        self.gameSetup = False

        return


    #Generic function to handle all building in the game - interface with gameView
    def build(self, player, build_flag):
        if(build_flag == 'ROAD'): #Show screen with potential roads
            if(self.gameSetup):
                potentialRoadDict = self.board.get_setup_roads(player)
            else:
                potentialRoadDict = self.board.get_potential_roads(player)

            roadToBuild = self.boardView.buildRoad_display(player, potentialRoadDict)
            if(roadToBuild != None):
                player.build_road(roadToBuild[0], roadToBuild[1], self.board)

            
        if(build_flag == 'SETTLE'): #Show screen with potential settlements
            if(self.gameSetup):
                potentialVertexDict = self.board.get_setup_settlements(player)
            else:
                potentialVertexDict = self.board.get_potential_settlements(player)
            
            vertexSettlement = self.boardView.buildSettlement_display(player, potentialVertexDict)
            if(vertexSettlement != None):
                player.build_settlement(vertexSettlement, self.board) 

        if(build_flag == 'CITY'): 
            potentialCityVertexDict = self.board.get_potential_cities(player)
            vertexCity = self.boardView.buildSettlement_display(player, potentialCityVertexDict)
            if(vertexCity != None):
                player.build_city(vertexCity, self.board) 


    #Wrapper Function to handle robber functionality
    def robber(self, player):
        potentialRobberDict = self.board.get_robber_spots()
        print("Move Robber!")

        hex_i, playerRobbed = self.boardView.moveRobber_display(player, potentialRobberDict)
        player.move_robber(hex_i, self.board, playerRobbed)


    #Function to roll dice 
    def rollDice(self):
        dice_1 = np.random.randint(1,7)
        dice_2 = np.random.randint(1,7)
        diceRoll = dice_1 + dice_2
        print("Dice Roll = ", diceRoll, "{", dice_1, dice_2, "}")

        self.boardView.displayDiceRoll(diceRoll)

        return diceRoll

    #Function to update resources for all players
    def update_playerResources(self, diceRoll, currentPlayer):
        if(diceRoll != 7): #Collect resources if not a 7
            #First get the hex or hexes corresponding to diceRoll
            hexResourcesRolled = self.board.getHexResourceRolled(diceRoll)
            #print('Resources rolled this turn:', hexResourcesRolled)

            #Check for each player
            for player_i in list(self.playerQueue.queue):
                #Check each settlement the player has
                for settlementCoord in player_i.buildGraph['SETTLEMENTS']:
                    for adjacentHex in self.board.boardGraph[settlementCoord].adjacentHexList: #check each adjacent hex to a settlement
                        if(adjacentHex in hexResourcesRolled and self.board.hexTileDict[adjacentHex].robber == False): #This player gets a resource if hex is adjacent and no robber
                            resourceGenerated = self.board.hexTileDict[adjacentHex].resource.type
                            player_i.resources[resourceGenerated] += 1
                            print("{} collects 1 {} from Settlement".format(player_i.name, resourceGenerated))
                
                #Check each City the player has
                for cityCoord in player_i.buildGraph['CITIES']:
                    for adjacentHex in self.board.boardGraph[cityCoord].adjacentHexList: #check each adjacent hex to a settlement
                        if(adjacentHex in hexResourcesRolled and self.board.hexTileDict[adjacentHex].robber == False): #This player gets a resource if hex is adjacent and no robber
                            resourceGenerated = self.board.hexTileDict[adjacentHex].resource.type
                            player_i.resources[resourceGenerated] += 2
                            print("{} collects 2 {} from City".format(player_i.name, resourceGenerated))

                print("Player:{}, Resources:{}, Points: {}".format(player_i.name, player_i.resources, player_i.victoryPoints))
                #print('Dev Cards:{}'.format(player_i.devCards))
                #print("RoadsLeft:{}, SettlementsLeft:{}, CitiesLeft:{}".format(player_i.roadsLeft, player_i.settlementsLeft, player_i.citiesLeft))
                print('MaxRoadLength:{}, LongestRoad:{}\n'.format(player_i.maxRoadLength, player_i.longestRoadFlag))
        
        #Logic for a 7 roll
        else:
            #Implement discarding cards
            #Check for each player
            for player_i in list(self.playerQueue.queue):
                if(currentPlayer.isAI):
                    print("AI discarding resources...")
                    #TO-DO
                else:
                    #Player must discard resources
                    player_i.discardResources()

            #Logic for robber
            if isinstance(currentPlayer, LLMPlayer):
                print(f"LLM Player {currentPlayer.name} must move the robber.")
                self.robber_action_pending_for_player = currentPlayer
                # The actual robber move will be handled in handle_llm_turn
            elif currentPlayer.isAI and hasattr(currentPlayer, 'heuristic_move_robber'): # Heuristic AI
                print("AI using heuristic robber...")
                currentPlayer.heuristic_move_robber(self.board)
                self.boardView.displayGameScreen() # Update view after heuristic AI robber move
            else: # Human player
                self.robber(currentPlayer)
                self.boardView.displayGameScreen()#Update back to original gamescreen


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

    # Method to handle LLM player's turn with validation and re-prompting
    def handle_llm_turn(self, llm_player):
        llm_turn_over = False
        last_action_status = None
        last_action_error_details = None

        # Max attempts to prevent infinite loops if LLM keeps making invalid moves.
        max_action_attempts = 10
        action_attempts = 0

        # Ensure dice has been rolled for the LLM player for this turn segment
        # This assumes the main loop's dice roll for AI players has already occurred.
        # If not, it needs to be handled here or ensured before calling.
        # From the integration, dice roll and resource update are done before this call.

        while not llm_turn_over and action_attempts < max_action_attempts:
            action_attempts += 1

            # Create model state for the LLM
            # TODO: These flags need to be accurately determined based on the current game state
            # For example, if a 7 was just rolled, robber_must_move should be true.
            # If player has >7 cards after a 7, discard_is_mandatory should be true.
            # This requires self.diceRoll to be accessible and potentially other state.
            # For now, these are placeholders and need proper integration with game flow.
            robber_must_move_flag = (self.robber_action_pending_for_player == llm_player)

            # Discard logic needs to be more robust: check if this player needs to discard
            player_total_cards = sum(llm_player.resources.values())
            discard_is_mandatory = False
            num_to_discard = 0
            if hasattr(self, 'diceRoll') and self.diceRoll == 7 and player_total_cards > 7:
                # This is a simplification. Discarding happens for all players before robber moves.
                # This logic might be better placed in update_playerResources or a dedicated pre-robber phase.
                # For LLM, it might need a specific state for "discard_pending".
                # For now, let's assume if it's a 7, and LLM has cards, it might be told to discard.
                # This is complex because discard is a global phase, then current player moves robber.
                # Temporarily, we'll not focus on LLM discard via this loop, assume it's handled elsewhere or LLM won't be asked.
                pass # Placeholder: Discard logic is complex to integrate here directly for LLM.

            current_model_state = modelState(self, llm_player,
                                             robber_movement_is_mandatory=robber_must_move,
                                             discard_is_mandatory=discard_is_mandatory,
                                             num_cards_to_discard=num_to_discard,
                                             # setup_road_placement_pending etc. are for setup phase
                                            )
            # Update current_model_state with the accurate robber_must_move status for the LLM
            current_model_state.robber_movement_is_mandatory = robber_must_move_flag

            if last_action_status:
                current_model_state.last_action_status = last_action_status
                current_model_state.last_action_error_details = last_action_error_details
                last_action_status = None
                last_action_error_details = None

            llm_action = llm_player.get_llm_move(current_model_state)
            action_type = llm_action.get("type")

            print(f"LLM Player {llm_player.name} tries action: {llm_action}")

            valid_action_executed_this_step = False # Tracks if *this specific action* was valid and done

            vertex_index_to_pixel_map = self.board.vertex_index_to_pixel_dict

            if action_type == "build_settlement":
                # This action is only valid in main game phase here. Setup is separate.
                if self.gameSetup:
                    last_action_status = "invalid_action_phase"
                    last_action_error_details = "Cannot build settlement via this general action during setup phase. Use setup-specific flow."
                else:
                    v_idx = llm_action.get("vertex_index")
                    if v_idx is not None:
                        potential_settlements_indices = current_model_state.available_actions.get("build_settlement", [])
                        if v_idx in potential_settlements_indices:
                            target_v_coord = vertex_index_to_pixel_map.get(v_idx)
                            if target_v_coord:
                                if llm_player.build_settlement(target_v_coord, self.board):
                                    print(f"LLM {llm_player.name} built settlement at vertex index {v_idx}.")
                                    valid_action_executed_this_step = True
                                    self.boardView.displayGameScreen()
                                else:
                                    last_action_status = "invalid_action_resource"
                                    last_action_error_details = f"Cannot build settlement: {llm_player.name} lacks resources or settlement pieces."
                            else:
                                last_action_status = "internal_error"
                                last_action_error_details = f"Invalid vertex index {v_idx} (no pixel map)."
                        else:
                            last_action_status = "invalid_placement"
                            last_action_error_details = "Proposed settlement location is invalid (occupied, too close, or not connected)."
                    else:
                        last_action_status = "invalid_action_format"
                        last_action_error_details = "Missing 'vertex_index' for build_settlement."

            elif action_type == "build_road":
                # This action is only valid in main game phase here. Setup is separate.
                if self.gameSetup:
                    last_action_status = "invalid_action_phase"
                    last_action_error_details = "Cannot build road via this general action during setup phase. Use setup-specific flow."
                else:
                    v1_idx = llm_action.get("v1_index")
                    v2_idx = llm_action.get("v2_index")
                    if v1_idx is not None and v2_idx is not None:
                        potential_roads_idx_pairs = current_model_state.available_actions.get("build_road", [])
                        chosen_road_pair = tuple(sorted((v1_idx, v2_idx)))

                        if chosen_road_pair in potential_roads_idx_pairs:
                            target_v1_coord = vertex_index_to_pixel_map.get(v1_idx)
                            target_v2_coord = vertex_index_to_pixel_map.get(v2_idx)
                            if target_v1_coord and target_v2_coord:
                                if llm_player.build_road(target_v1_coord, target_v2_coord, self.board, setup_phase=False): # setup_phase is False here
                                    print(f"LLM {llm_player.name} built road between vertex indices {v1_idx} and {v2_idx}.")
                                    valid_action_executed_this_step = True
                                    self.check_longest_road(llm_player)
                                    self.boardView.displayGameScreen()
                                else:
                                    last_action_status = "invalid_action_resource"
                                    last_action_error_details = f"Cannot build road: {llm_player.name} lacks resources or road pieces."
                            else:
                                last_action_status = "internal_error"
                                last_action_error_details = f"Invalid vertex indices {v1_idx}, {v2_idx} (no pixel map)."
                        else:
                            last_action_status = "invalid_placement"
                            last_action_error_details = "Proposed road location is invalid (occupied, not connected, or rule violation)."
                    else:
                        last_action_status = "invalid_action_format"
                        last_action_error_details = "Missing 'v1_index' or 'v2_index' for build_road."

            elif action_type == "build_city":
                v_idx = llm_action.get("vertex_index")
                if v_idx is not None:
                    potential_cities_indices = current_model_state.available_actions.get("build_city", [])
                    if v_idx in potential_cities_indices:
                        target_v_coord = vertex_index_to_pixel_map.get(v_idx)
                        if target_v_coord:
                            if llm_player.build_city(target_v_coord, self.board):
                                print(f"LLM {llm_player.name} built city at vertex index {v_idx}.")
                                valid_action_executed_this_step = True
                                self.boardView.displayGameScreen()
                            else:
                                last_action_status = "invalid_action_resource"
                                last_action_error_details = f"Cannot build city: {llm_player.name} lacks resources or city pieces, or no settlement to upgrade."
                        else:
                            last_action_status = "internal_error"
                            last_action_error_details = f"Invalid vertex index {v_idx} (no pixel map)."
                    else:
                        last_action_status = "invalid_placement"
                        last_action_error_details = "Proposed city location is invalid (no settlement to upgrade or rule violation)."
                else:
                    last_action_status = "invalid_action_format"
                    last_action_error_details = "Missing 'vertex_index' for build_city."

            elif action_type == "buy_development_card":
                if llm_player.draw_devCard(self.board):
                    print(f"LLM {llm_player.name} bought a development card.")
                    valid_action_executed_this_step = True
                else:
                    last_action_status = "invalid_action_resource"
                    last_action_error_details = f"LLM {llm_player.name} failed to buy development card (insufficient resources)."

            elif action_type == "play_dev_card":
                # Playing dev cards needs more complex handling:
                # 1. LLM needs to specify WHICH card. (Assume get_llm_move handles this if card type has params)
                # 2. player.play_devCard takes `self` (the game object)
                # 3. Validation: Does player have the card? Can it be played now?
                # For now, a simple pass-through, assuming LLMPlayer's play_devCard handles choice & player.py handles logic.
                # This will likely need refinement.

                # We'd need to know what card the LLM wants to play. This info should be in llm_action.
                # player.play_devCard is interactive for humans. For LLM, it needs to be non-interactive.
                # This suggests LLMPlayer might need its own version or play_devCard in player.py needs an AI mode.
                # This is a deeper change. For now, let's assume LLM can't play dev cards via this general loop easily.
                # Or, we call it and see. player.play_devCard is interactive (input()). This won't work for LLM.
                # For now, this action will be invalid for LLM until play_devCard is refactored.
                last_action_status = "action_not_yet_supported_for_llm"
                last_action_error_details = "Playing development cards via LLM requires non-interactive 'play_devCard' method."
                # if llm_player.play_devCard(self): # This 'self' is catanGame instance
                #     print(f"LLM {llm_player.name} played a development card.")
                #     valid_action_executed_this_step = True
                #     # check_largest_army might be needed here if a Knight was played.
                # else:
                #     last_action_status = "invalid_action"
                #     last_action_error_details = f"LLM {llm_player.name} failed to play development card."


            elif action_type == "move_robber":
                # This should only happen if robber_must_move_flag is true.
                if not robber_must_move_flag:
                    last_action_status = "invalid_action_phase"
                    last_action_error_details = "LLM attempted to move robber when not mandatory or not its turn to do so."
                else:
                    hex_idx = llm_action.get("hex_index")
                    player_to_rob_name = llm_action.get("player_to_rob_name") # Can be None or "Null"

                    target_player_obj = None
                    if player_to_rob_name and player_to_rob_name.lower() != "null":
                        for p_obj in list(self.playerQueue.queue):
                            if p_obj.name == player_to_rob_name:
                                target_player_obj = p_obj
                                break

                    # Validate hex_idx (e.g., not current robber spot, valid index)
                    # board.get_robber_spots() gives valid hexes. modelState should reflect this.
                    # For simplicity, assume LLM picks a valid hex from those provided if modelState is good.
                    # A more robust check: is hex_idx in board.get_robber_spots().keys()?

                    if hex_idx is not None and hex_idx in self.board.hexTileDict and not self.board.hexTileDict[hex_idx].robber:
                        llm_player.move_robber(hex_idx, self.board, target_player_obj)
                        print(f"LLM {llm_player.name} moved robber to hex {hex_idx}, targeting {target_player_obj.name if target_player_obj else 'no one'}.")
                        valid_action_executed_this_step = True
                        self.robber_action_pending_for_player = None # Robber action completed
                        # Player can now take other actions or end turn.
                        self.boardView.displayGameScreen()

                    else:
                        last_action_status = "invalid_placement"
                        last_action_error_details = f"Invalid hex_index {hex_idx} for robber or hex already has robber."

            # TODO: trade_with_bank, trade_with_players, discard_cards

            elif action_type == "end_turn":
                print(f"LLM Player {llm_player.name} chooses to end turn.")
                llm_turn_over = True
                valid_action_executed_this_step = True

            else:
                last_action_status = "unknown_action"
                last_action_error_details = f"Unknown action type '{action_type}' received from LLM."

            if not valid_action_executed_this_step and not llm_turn_over:
                print(f"LLM {llm_player.name} invalid action attempt: {last_action_status} - {last_action_error_details}. Re-prompting.")
            elif valid_action_executed_this_step and not llm_turn_over:
                 print(f"LLM {llm_player.name} successfully executed {action_type}. LLM can choose another action or end turn.")
                 # Reset error messages if a valid action was taken, so the next prompt is clean unless a new error occurs.
                 last_action_status = None
                 last_action_error_details = None


        if action_attempts >= max_action_attempts and not llm_turn_over:
            print(f"LLM Player {llm_player.name} reached max action attempts in a single turn segment. Ending turn automatically.")
            llm_turn_over = True # Force turn over

        return llm_turn_over


    #Function that runs the main game loop with all players and pieces
    def playCatan(self):
        #self.board.displayBoard() #Display updated board

        while (self.gameOver == False):

            #Loop for each player's turn -> iterate through the player queue
            for currPlayer in self.playerQueue.queue:

                print("---------------------------------------------------------------------------")
                print("Current Player:", currPlayer.name)

                turnOver = False #boolean to keep track of turn
                diceRolled = False  #Boolean for dice roll status
                
                #Update Player's dev card stack with dev cards drawn in previous turn and reset devCardPlayedThisTurn
                currPlayer.updateDevCards()
                currPlayer.devCardPlayedThisTurn = False

                while(turnOver == False):

                    #TO-DO: Add logic for AI Player to move
                    #TO-DO: Add option of AI Player playing a dev card prior to dice roll
                    if(currPlayer.isAI):
                        #Roll Dice
                        diceNum = self.rollDice()
                        diceRolled = True
                        self.update_playerResources(diceNum, currPlayer)

                        #currPlayer.move(self.board) #AI Player makes all its moves
                        if isinstance(currPlayer, LLMPlayer):
                            # LLM Player's turn is handled by a dedicated loop
                            # Dice roll and resource update are done at the start of the LLM's turn segment
                            turnOver = self.handle_llm_turn(currPlayer)
                        elif hasattr(currPlayer, 'move'): # For HeuristicAIPlayer or other AI with a 'move' method
                            currPlayer.move(self.board)
                            turnOver = True # Assume heuristic AI completes its turn in one 'move' call
                        else: # Should not happen if isAI is true
                            print(f"Warning: AI Player {currPlayer.name} has no 'move' method and is not LLMPlayer. Ending turn.")
                            turnOver = True

                        #Check if AI player gets longest road/largest army and update Victory points
                        # These checks should be done after each relevant action (e.g. road build for longest_road)
                        # For LLM, check_longest_road is called within handle_llm_turn after a road is built.
                        # Largest army check would be after playing a knight card.
                        # For HeuristicAI, these might need to be called after its .move() if not handled internally.
                        # For simplicity, let's assume .move() for HeuristicAI handles its own point updates or we call it here.
                        if not isinstance(currPlayer, LLMPlayer): # LLM handles this internally now or after specific actions
                            self.check_longest_road(currPlayer)
                        self.check_largest_army(currPlayer)
                        print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))
                        
                        self.boardView.displayGameScreen()#Update back to original gamescreen
                        turnOver = True

                    else: #Game loop for human players
                        for e in pygame.event.get(): #Get player actions/in-game events
                            #print(e)
                            if e.type == pygame.QUIT:
                                sys.exit(0)

                            #Check mouse click in rollDice
                            if(e.type == pygame.MOUSEBUTTONDOWN):
                                #Check if player rolled the dice
                                if(self.boardView.rollDice_button.collidepoint(e.pos)):
                                    if(diceRolled == False): #Only roll dice once
                                        diceNum = self.rollDice()
                                        diceRolled = True
                                        
                                        self.boardView.displayDiceRoll(diceNum)
                                        #Code to update player resources with diceNum
                                        self.update_playerResources(diceNum, currPlayer)

                                #Check if player wants to build road
                                if(self.boardView.buildRoad_button.collidepoint(e.pos)):
                                    #Code to check if road is legal and build
                                    if(diceRolled == True): #Can only build after rolling dice
                                        self.build(currPlayer, 'ROAD')
                                        self.boardView.displayGameScreen()#Update back to original gamescreen

                                        #Check if player gets longest road and update Victory points
                                        self.check_longest_road(currPlayer)
                                        #Show updated points and resources  
                                        print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))

                                #Check if player wants to build settlement
                                if(self.boardView.buildSettlement_button.collidepoint(e.pos)):
                                    if(diceRolled == True): #Can only build settlement after rolling dice
                                        self.build(currPlayer, 'SETTLE')
                                        self.boardView.displayGameScreen()#Update back to original gamescreen
                                        #Show updated points and resources  
                                        print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))

                                #Check if player wants to build city
                                if(self.boardView.buildCity_button.collidepoint(e.pos)):
                                    if(diceRolled == True): #Can only build city after rolling dice
                                        self.build(currPlayer, 'CITY')
                                        self.boardView.displayGameScreen()#Update back to original gamescreen
                                        #Show updated points and resources  
                                        print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))

                                #Check if player wants to draw a development card
                                if(self.boardView.devCard_button.collidepoint(e.pos)):
                                    if(diceRolled == True): #Can only draw devCard after rolling dice
                                        currPlayer.draw_devCard(self.board)
                                        #Show updated points and resources  
                                        print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))
                                        print('Available Dev Cards:', currPlayer.devCards)

                                #Check if player wants to play a development card - can play devCard whenever after rolling dice
                                if(self.boardView.playDevCard_button.collidepoint(e.pos)):
                                        currPlayer.play_devCard(self)
                                        self.boardView.displayGameScreen()#Update back to original gamescreen
                                        
                                        #Check for Largest Army and longest road
                                        self.check_largest_army(currPlayer)
                                        self.check_longest_road(currPlayer)
                                        #Show updated points and resources  
                                        print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))
                                        print('Available Dev Cards:', currPlayer.devCards)

                                #Check if player wants to trade with the bank
                                if(self.boardView.tradeBank_button.collidepoint(e.pos)):
                                        currPlayer.initiate_trade(self, 'BANK')
                                        #Show updated points and resources  
                                        print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))
                                
                                #Check if player wants to trade with another player
                                if(self.boardView.tradePlayers_button.collidepoint(e.pos)):
                                        currPlayer.initiate_trade(self, 'PLAYER')
                                        #Show updated points and resources  
                                        print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))

                                #Check if player wants to end turn
                                if(self.boardView.endTurn_button.collidepoint(e.pos)):
                                    if(diceRolled == True): #Can only end turn after rolling dice
                                        print("Ending Turn!")
                                        turnOver = True  #Update flag to nextplayer turn

                    #Update the display
                    #self.displayGameScreen(None, None)
                    pygame.display.update()
                    
                    #Check if game is over
                    if currPlayer.victoryPoints >= self.maxPoints:
                        self.gameOver = True
                        self.turnOver = True
                        print("====================================================")
                        print("PLAYER {} WINS!".format(currPlayer.name))
                        print("Exiting game in 10 seconds...")
                        break

                if(self.gameOver):
                    startTime = pygame.time.get_ticks()
                    runTime = 0
                    while(runTime < 10000): #10 second delay prior to quitting
                        runTime = pygame.time.get_ticks() - startTime

                    break
                    
                

#Initialize new game and run
newGame = catanGame()
newGame.playCatan()