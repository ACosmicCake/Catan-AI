#Settlers of Catan
#Heuristic AI class implementation

from board import *
from player import *
import numpy as np

#Class definition for an AI player
class heuristicAIPlayer(player):
    
    #Update AI player flag and resources
    def updateAI(self): 
        self.isAI = True
        self.setupResources = [] #List to keep track of setup resources
        # Initialize resources with the exact amount needed for the setup phase (2 settlements, 2 roads).
        # This allows the AI to use its standard build methods during setup by "spending" this initial budget.
        # Cost: 2x Settle (1W,1S,1H,1B) + 2x Road (1B,1W) = 4xWOOD, 4xBRICK, 2xWHEAT, 2xSHEEP.
        self.resources = {'ORE':0, 'BRICK':0, 'WHEAT':0, 'WOOD':0, 'SHEEP':0}
        print("Added new AI Player:", self.name)


    #Function to build an initial settlement - just choose random spot for now
    def initial_setup(self, board):
        #Build random settlement
        possibleVertices = board.get_setup_settlements(self)

        #Simple heuristic for choosing initial spot
        diceRoll_expectation = {2:1, 3:2, 4:3, 5:4, 6:5, 8:5, 9:4, 10:3, 11:2, 12:1, None:0}
        vertexValues = []

        #Get the adjacent hexes for each hex
        for v in possibleVertices.keys():
            vertexNumValue = 0
            resourcesAtVertex = []
            #For each adjacent hex get its value and overall resource diversity for that vertex
            for adjacentHex in board.boardGraph[v].adjacentHexList:
                resourceType = board.hexTileDict[adjacentHex].resource.type
                if(resourceType not in resourcesAtVertex):
                    resourcesAtVertex.append(resourceType)
                numValue = board.hexTileDict[adjacentHex].resource.num
                vertexNumValue += diceRoll_expectation[numValue] #Add to total value of this vertex

            #basic heuristic for resource diversity
            vertexNumValue += len(resourcesAtVertex)*2
            for r in resourcesAtVertex:
                if(r != 'DESERT' and r not in self.setupResources):
                    vertexNumValue += 2.5 #Every new resource gets a bonus
            
            vertexValues.append(vertexNumValue)


        vertexToBuild_index = vertexValues.index(max(vertexValues))
        vertexToBuild = list(possibleVertices.keys())[vertexToBuild_index]

        #Add to setup resources
        for adjacentHex in board.boardGraph[vertexToBuild].adjacentHexList:
            resourceType = board.hexTileDict[adjacentHex].resource.type
            if(resourceType not in self.setupResources and resourceType != 'DESERT'):
                self.setupResources.append(resourceType)

        self.build_settlement(vertexToBuild, board)


        #Build random road
        possibleRoads = board.get_setup_roads(self)
        randomEdge = np.random.randint(0, len(possibleRoads.keys()))
        self.build_road(list(possibleRoads.keys())[randomEdge][0], list(possibleRoads.keys())[randomEdge][1], board)

    
    def move(self, board):
        print("AI Player {} playing...".format(self.name))
        #Trade resources if there are excessive amounts of a particular resource
        self.trade()
        #Build a settlements, city and few roads
        possibleVertices = board.get_potential_settlements(self)
        if(possibleVertices != {} and (self.resources['BRICK'] > 0 and self.resources['WOOD'] > 0 and self.resources['SHEEP'] > 0 and self.resources['WHEAT'] > 0)):
            randomVertex = np.random.randint(0, len(possibleVertices.keys()))
            self.build_settlement(list(possibleVertices.keys())[randomVertex], board)

        #Build a City
        possibleVertices = board.get_potential_cities(self)
        if(possibleVertices != {} and (self.resources['WHEAT'] >= 2 and self.resources['ORE'] >= 3)):
            randomVertex = np.random.randint(0, len(possibleVertices.keys()))
            self.build_city(list(possibleVertices.keys())[randomVertex], board)

        #Build a couple roads
        for i in range(2):
            if(self.resources['BRICK'] > 0 and self.resources['WOOD'] > 0):
                possibleRoads = board.get_potential_roads(self)
                randomEdge = np.random.randint(0, len(possibleRoads.keys()))
                self.build_road(list(possibleRoads.keys())[randomEdge][0], list(possibleRoads.keys())[randomEdge][1], board)

        #Draw a Dev Card with 1/3 probability
        devCardNum = np.random.randint(0, 3)
        if(devCardNum == 0):
            self.draw_devCard(board)
        
        return

    #Wrapper function to control all trading
    def trade(self):
        for r1, r1_amount in self.resources.items():
            if(r1_amount >= 6): #heuristic to trade if a player has more than 5 of a particular resource
                for r2, r2_amount in self.resources.items():
                    if(r2_amount < 1):
                        self.trade_with_bank(r1, r2)
                        break

    
    #Choose which player to rob
    def choose_player_to_rob(self, board):
        '''Heuristic function to choose the player with maximum points.
        Choose hex with maximum other players, Avoid blocking own resource
        args: game board object
        returns: hex index and player to rob
        '''
        #Get list of robber spots
        robberHexDict = board.get_robber_spots()
        
        #Choose a hexTile with maximum adversary settlements
        maxHexScore = 0 #Keep only the best hex to rob
        for hex_ind, hexTile in robberHexDict.items():
            #Extract all 6 vertices of this hexTile
            vertexList = polygon_corners(board.flat, hexTile.hex)

            hexScore = 0 #Heuristic score for hexTile
            playerToRob_VP = 0
            playerToRob = None
            for vertex in vertexList:
                playerAtVertex = board.boardGraph[vertex].state['Player']
                if playerAtVertex == self:
                    hexScore -= self.victoryPoints
                elif playerAtVertex != None: #There is an adversary on this vertex
                    hexScore += playerAtVertex.visibleVictoryPoints
                    #Find strongest other player at this hex, provided player has resources
                    if playerAtVertex.visibleVictoryPoints >= playerToRob_VP and sum(playerAtVertex.resources.values()) > 0:
                        playerToRob_VP = playerAtVertex.visibleVictoryPoints
                        playerToRob = playerAtVertex
                else:
                    pass

            if hexScore >= maxHexScore and playerToRob != None:
                hexToRob_index = hex_ind
                playerToRob_hex = playerToRob
                maxHexScore = hexScore

        return hexToRob_index, playerToRob_hex


    def heuristic_move_robber(self, board):
        '''Function to control heuristic AI robber
        Calls the choose_player_to_rob and move_robber functions
        args: board object
        returns: player object that was robbed, or None
        '''
        #Get the best hex and player to rob
        # Ensure that choose_player_to_rob can handle cases where no player can be robbed (e.g., returns None for playerRobbed)
        hex_i, playerRobbed = self.choose_player_to_rob(board)

        if hex_i is None : # choose_player_to_rob might return None if no valid spot/player
            print(f"{self.name} (Heuristic) could not find a valid hex/player to rob.")
            # Move robber to a default location if necessary, without robbing
            # For now, assume if hex_i is None, playerRobbed is also None.
            # Find first available hex that is not the current robber hex
            current_robber_hex = None
            for idx, tile in board.hexTileDict.items():
                if tile.robber:
                    current_robber_hex = idx
                    break

            default_hex_to_move = 0
            if current_robber_hex is not None: # Move it somewhere else
                for idx in board.hexTileDict.keys():
                    if idx != current_robber_hex:
                        default_hex_to_move = idx
                        break

            self.move_robber(default_hex_to_move, board, None) # Move robber without stealing
            return None


        #Move the robber; move_robber calls steal_resource which now returns the stolen resource or None
        resource_stolen = self.move_robber(hex_i, board, playerRobbed)

        if playerRobbed and resource_stolen:
            print(f"{self.name} (Heuristic) successfully robbed {playerRobbed.name} of a {resource_stolen} at hex {hex_i}.")
            return playerRobbed # Return the player object that was successfully robbed
        elif playerRobbed:
            print(f"{self.name} (Heuristic) moved robber to hex {hex_i} and targeted {playerRobbed.name}, but they had no resources.")
            return None # Robbery attempted but failed due to no resources
        else:
            print(f"{self.name} (Heuristic) moved robber to hex {hex_i}, no player was robbed.")
            return None # No player was targeted or robbery was not applicable


    # def heuristic_play_dev_card(self, board):
    #     '''Heuristic strategies to choose and play a dev card
    #     args: board object
    #     '''
    #     #Check if player can play a devCard this turn
    #     if self.devCardPlayedThisTurn != True:
    #         #Get a list of all the unique dev cards this player can play
    #         devCardsAvailable = []
    #         for cardName, cardAmount in self.devCards.items():
    #             if(cardName != 'VP' and cardAmount >= 1): #Exclude Victory points
    #                 devCardsAvailable.append((cardName, cardAmount))

    #         if(len(devCardsAvailable) >=1):
                #If a hexTile is currently blocked, try and play a Knight

                #If expansion needed, try road-builder

                #If resources needed, try monopoly or year of plenty


    def resources_needed_for_settlement(self):
        '''Function to return the resources needed for a settlement
        args: player object - use self.resources
        returns: list of resources needed for a settlement
        '''
        resourcesNeededDict = {}
        for resourceName in self.resources.keys():
            if resourceName != 'ORE' and self.resources[resourceName] == 0:
                resourcesNeededDict[resourceName] = 1

        return resourcesNeededDict


    def resources_needed_for_city(self):
        '''Function to return the resources needed for a city
        args: player object - use self.resources
        returns: list of resources needed for a city
        '''
        resourcesNeededDict = {}
        if self.resources['ORE'] < 3:
            resourcesNeededDict['ORE'] = 3 - self.resources['ORE']

        if self.resources['WHEAT'] < 2:
            resourcesNeededDict['ORE'] = 2 - self.resources['WHEAT']

        return resourcesNeededDict

    def heuristic_discard(self):
        '''Function for the AI to choose a set of cards to discard upon rolling a 7
        '''
        return

    #Function to propose a trade -> give r1 and get r2
    #Propose a trade as a dictionary with {r1:amt_1, r2: amt_2} specifying the trade
    #def propose_trade_with_players(self):
    

    #Function to accept/reject trade - return True if accept
    #def accept_trade(self, r1_dict, r2_dict):
        

    #Function to find best action - based on gamestate
    def get_action(self):
        return

    #Function to execute the player's action
    def execute_action(self):
        return
