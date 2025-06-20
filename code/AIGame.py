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
                # LLM places a settlement
                print(f"{player_i.name} to place first settlement.")
                current_model_state_settlement = modelState(self, player_i)
                action_settlement = player_i.get_llm_move(current_model_state_settlement)
                print(f"{player_i.name} (Thoughts for settlement: {player_i.thoughts}) -> Action: {action_settlement}")

                if action_settlement.get("type") == "build_settlement":
                    v_idx = action_settlement.get("vertex_index")
                    if v_idx is not None:
                        v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                        if v_coord and not self.board.boardGraph[v_coord].isColonised:
                            player_i.build_settlement(v_coord, self.board)
                            print(f"{player_i.name} built initial settlement at {v_idx}.")
                        else:
                            print(f"{player_i.name} failed initial settlement at {v_idx} (invalid/occupied). Placing randomly.")
                            self.execute_random_setup_settlement(player_i)
                    else:
                        print(f"{player_i.name} did not provide valid settlement. Placing randomly.")
                        self.execute_random_setup_settlement(player_i)
                else:
                    print(f"{player_i.name} did not choose to build settlement. Placing randomly.")
                    self.execute_random_setup_settlement(player_i)

                self.boardView.displayGameScreen()
                pygame.time.delay(500)

                print(f"{player_i.name} to place first road.")
                current_model_state_road = modelState(self, player_i)
                action_road = player_i.get_llm_move(current_model_state_road)
                print(f"{player_i.name} (Thoughts for road: {player_i.thoughts}) -> Action: {action_road}")

                if action_road.get("type") == "build_road":
                    v1_idx = action_road.get("v1_index")
                    v2_idx = action_road.get("v2_index")
                    if v1_idx is not None and v2_idx is not None:
                        v1_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx)
                        v2_coord = self.board.vertex_index_to_pixel_dict.get(v2_idx)
                        if player_i.buildGraph['SETTLEMENTS']: # Check if a settlement exists
                            last_settlement_coord = player_i.buildGraph['SETTLEMENTS'][-1]
                            if v1_coord and v2_coord and (v1_coord == last_settlement_coord or v2_coord == last_settlement_coord):
                                player_i.build_road(v1_coord, v2_coord, self.board)
                                print(f"{player_i.name} built initial road from {v1_idx} to {v2_idx}.")
                            else:
                                print(f"{player_i.name} failed initial road (invalid/not adjacent). Placing randomly.")
                                self.execute_random_setup_road(player_i)
                        else: # Should not happen if settlement placement was successful
                            print(f"{player_i.name} has no settlement to build road from. Placing randomly.")
                            self.execute_random_setup_road(player_i) # This might still fail if no settlements
                    else:
                        print(f"{player_i.name} did not provide valid road. Placing randomly.")
                        self.execute_random_setup_road(player_i)
                else:
                    print(f"{player_i.name} did not choose to build road. Placing randomly.")
                    self.execute_random_setup_road(player_i)

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
                print(f"{player_i.name} to place second settlement.")
                # ... (LLM settlement placement logic as above, with distance rule check) ...
                current_model_state_settlement = modelState(self, player_i)
                action_settlement = player_i.get_llm_move(current_model_state_settlement)
                print(f"{player_i.name} (Thoughts for settlement: {player_i.thoughts}) -> Action: {action_settlement}")

                if action_settlement.get("type") == "build_settlement":
                    v_idx = action_settlement.get("vertex_index")
                    if v_idx is not None:
                        v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                        if v_coord and not self.board.boardGraph[v_coord].isColonised:
                            valid_placement = True
                            for neighbor_v_pixel_idx_key in self.board.boardGraph[v_coord].edgeList: # edgeList contains pixel coords
                                if self.board.boardGraph[neighbor_v_pixel_idx_key].isColonised:
                                    valid_placement = False; break
                            if valid_placement:
                                player_i.build_settlement(v_coord, self.board)
                                print(f"{player_i.name} built initial settlement at {v_idx}.")
                            else:
                                print(f"{player_i.name} failed initial settlement at {v_idx} (too close). Placing randomly.")
                                self.execute_random_setup_settlement(player_i)
                        else:
                            print(f"{player_i.name} failed initial settlement at {v_idx} (invalid/occupied). Placing randomly.")
                            self.execute_random_setup_settlement(player_i)
                    else:
                        print(f"{player_i.name} did not provide valid settlement. Placing randomly.")
                        self.execute_random_setup_settlement(player_i)
                else:
                    print(f"{player_i.name} did not choose to build settlement. Placing randomly.")
                    self.execute_random_setup_settlement(player_i)

                self.boardView.displayGameScreen()
                pygame.time.delay(500)

                print(f"{player_i.name} to place second road.")
                # ... (LLM road placement logic as above) ...
                current_model_state_road = modelState(self, player_i)
                action_road = player_i.get_llm_move(current_model_state_road)
                print(f"{player_i.name} (Thoughts for road: {player_i.thoughts}) -> Action: {action_road}")

                if action_road.get("type") == "build_road":
                    v1_idx = action_road.get("v1_index")
                    v2_idx = action_road.get("v2_index")
                    if v1_idx is not None and v2_idx is not None:
                        v1_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx)
                        v2_coord = self.board.vertex_index_to_pixel_dict.get(v2_idx)
                        if player_i.buildGraph['SETTLEMENTS']:
                            last_settlement_coord = player_i.buildGraph['SETTLEMENTS'][-1]
                            if v1_coord and v2_coord and (v1_coord == last_settlement_coord or v2_coord == last_settlement_coord):
                                player_i.build_road(v1_coord, v2_coord, self.board)
                                print(f"{player_i.name} built initial road from {v1_idx} to {v2_idx}.")
                            else:
                                print(f"{player_i.name} failed initial road (invalid/not adjacent). Placing randomly.")
                                self.execute_random_setup_road(player_i)
                        else:
                             print(f"{player_i.name} has no settlement to build road from. Placing randomly.")
                             self.execute_random_setup_road(player_i)
                    else:
                        print(f"{player_i.name} did not provide valid road. Placing randomly.")
                        self.execute_random_setup_road(player_i)
                else:
                    print(f"{player_i.name} did not choose to build road. Placing randomly.")
                    self.execute_random_setup_road(player_i)

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
                print('MaxRoadLength:{}, Longest Road:{}\n'.format(player_i.maxRoadLength, player_i.longestRoadFlag))
        
        else:
            print("AI using heuristic robber...")
            currentPlayer.heuristic_move_robber(self.board)


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



    #Function that runs the main game loop with all players and pieces
    def playCatan(self):
        #self.board.displayBoard() #Display updated board
        numTurns = 0
        # from LLMPlayer import LLMPlayer # Will be used when players are LLMPlayer instances

        while (self.gameOver == False):
            #Loop for each player's turn -> iterate through the player queue
            for currPlayer in self.playerQueue.queue:
                numTurns += 1
                print("---------------------------------------------------------------------------")
                print(f"Current Player: {currPlayer.name} (Color: {currPlayer.color})")
                
                #Update Player's dev card stack with dev cards drawn in previous turn and reset devCardPlayedThisTurn
                currPlayer.updateDevCards()
                currPlayer.devCardPlayedThisTurn = False

                # --- Dice Roll and Resource Update ---
                pygame.event.pump() # Keep Pygame responsive
                diceNum = self.rollDice()
                self.update_playerResources(diceNum, currPlayer) # Handles 7-out rule via heuristic_move_robber if diceNum is 7
                self.diceStats[diceNum] += 1
                self.diceStats_list.append(diceNum)
                # --- End of Dice Roll ---

                # LLM Player Turn Logic or Heuristic AI Logic
                if hasattr(currPlayer, 'get_llm_move'): # Check if the player is an LLM type
                    print(f"{currPlayer.name} is an LLMPlayer, getting move...")
                    try:
                        current_model_state = modelState(self, currPlayer)
                        action = currPlayer.get_llm_move(current_model_state)
                        print(f"{currPlayer.name} proposed action: {action}")
                        print(f"{currPlayer.name}'s thoughts: {currPlayer.thoughts}")

                        action_type = action.get("type")

                        if action_type == "build_road":
                            v1_idx = action.get("v1_index")
                            v2_idx = action.get("v2_index")
                            if v1_idx is not None and v2_idx is not None:
                                try:
                                    v1_coord = self.board.vertex_index_to_pixel_dict.get(v1_idx)
                                    v2_coord = self.board.vertex_index_to_pixel_dict.get(v2_idx)
                                    if v1_coord and v2_coord:
                                        print(f"{currPlayer.name} attempts to build road between {v1_idx} and {v2_idx}")
                                        currPlayer.build_road(v1_coord, v2_coord, self.board)
                                        self.check_longest_road(currPlayer) # Check after building
                                    else:
                                        print(f"Invalid vertex indices for build_road: {v1_idx}, {v2_idx}")
                                except Exception as e:
                                    print(f"Error executing build_road: {e}")
                            else:
                                print("Missing vertex indices for build_road action.")

                        elif action_type == "build_settlement":
                            v_idx = action.get("vertex_index")
                            if v_idx is not None:
                                try:
                                    v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                                    if v_coord:
                                        print(f"{currPlayer.name} attempts to build settlement at {v_idx}")
                                        currPlayer.build_settlement(v_coord, self.board)
                                    else:
                                        print(f"Invalid vertex index for build_settlement: {v_idx}")
                                except Exception as e:
                                    print(f"Error executing build_settlement: {e}")
                            else:
                                print("Missing vertex index for build_settlement action.")

                        elif action_type == "build_city":
                            v_idx = action.get("vertex_index")
                            if v_idx is not None:
                                try:
                                    v_coord = self.board.vertex_index_to_pixel_dict.get(v_idx)
                                    if v_coord:
                                        if v_coord in currPlayer.buildGraph['SETTLEMENTS']:
                                            print(f"{currPlayer.name} attempts to build city at {v_idx}")
                                            currPlayer.build_city(v_coord, self.board)
                                        else:
                                            print(f"{currPlayer.name} cannot build city at {v_idx}: no settlement present.")
                                    else:
                                        print(f"Invalid vertex index for build_city: {v_idx}")
                                except Exception as e:
                                    print(f"Error executing build_city: {e}")
                            else:
                                print("Missing vertex index for build_city action.")

                        elif action_type == "buy_development_card":
                            print(f"{currPlayer.name} attempts to buy development card.")
                            currPlayer.draw_devCard(self.board)

                        elif action_type == "trade_with_bank":
                            res_give = action.get("resource_to_give")
                            res_receive = action.get("resource_to_receive")
                            if res_give and res_receive:
                                print(f"{currPlayer.name} attempts to trade {res_give} for {res_receive} with bank.")
                                currPlayer.trade_with_bank(res_give.upper(), res_receive.upper())
                            else:
                                print("Missing resource types for trade_with_bank action.")

                        elif action_type == "play_knight_card":
                            print(f"{currPlayer.name} wants to play a KNIGHT card (conceptual - not fully implemented).")
                            # Placeholder for non-interactive knight play
                            # if 'KNIGHT' in currPlayer.devCards and currPlayer.devCards['KNIGHT'] > 0:
                            #    currPlayer.devCards['KNIGHT'] -= 1
                            #    currPlayer.knightsPlayed += 1
                            #    # self.robber(currPlayer) # This would call the robber placement logic
                            #    self.check_largest_army(currPlayer)
                            # else:
                            #    print(f"{currPlayer.name} has no KNIGHT card to play.")
                            pass

                        elif action_type == "end_turn":
                            print(f"{currPlayer.name} ends their turn.")
                            pass

                        else:
                            print(f"Unknown or unsupported action type: {action_type}. Player ends turn by default.")

                    except Exception as e:
                        print(f"Error during LLM player {currPlayer.name}'s turn: {e}")
                        print(f"{currPlayer.name} ends turn due to error.")

                else: # Fallback to existing heuristic AI logic if not an LLMPlayer
                    print(f"{currPlayer.name} is a HeuristicAIPlayer, using existing move logic.")
                    currPlayer.move(self.board)
                    self.check_longest_road(currPlayer) # Original placement for heuristic AI

                # Common turn finalization
                print("Player:{}, Resources:{}, Points: {}".format(currPlayer.name, currPlayer.resources, currPlayer.victoryPoints))
                self.boardView.displayGameScreen() # Update display
                pygame.time.delay(300) # Brief pause

                # Check if game is over
                if currPlayer.victoryPoints >= self.maxPoints:
                    self.gameOver = True
                    print("====================================================")
                    print(f"PLAYER {currPlayer.name} WINS IN {int(numTurns/self.numPlayers)} ROUNDS!")
                    print(self.diceStats)
                    break # Break from player loop

            if(self.gameOver):
                # Handle game over screen or delay before exiting
                start_time = pygame.time.get_ticks()
                while pygame.time.get_ticks() - start_time < 5000: # 5-second display of final board
                    pygame.event.pump() # Keep Pygame responsive
                    self.boardView.displayGameScreen() # Keep showing the board
                break # Break from game loop
                                   
# Initialize new game and run - this line should be outside the class
# newGame_AI = catanAIGame()