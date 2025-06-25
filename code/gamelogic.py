import numpy as np

class GameLogicManager:
    def __init__(self, board, player_queue_getter):
        """
        Initializes the GameLogicManager.
        Args:
            board: The catanBoard object.
            player_queue_getter: A function that, when called, returns the current list of player objects.
                                 This allows the manager to always get the up-to-date player list.
        """
        self.board = board
        self.get_player_list = player_queue_getter # Store the function itself

    def roll_dice(self):
        """Rolls two dice and returns the sum."""
        dice_1 = np.random.randint(1, 7)
        dice_2 = np.random.randint(1, 7)
        roll_total = dice_1 + dice_2
        print(f"GameLogicManager: Dice Roll = {roll_total} ({dice_1}, {dice_2})")
        return roll_total

    def check_longest_road(self, player_to_check):
        """
        Checks if player_to_check has the longest road and updates VP accordingly.
        Assumes player_to_check.maxRoadLength is up-to-date.
        """
        all_players = self.get_player_list() # Get current player list
        if player_to_check.maxRoadLength < 5:
            return False # Not eligible

        current_longest_road_holder = None
        max_len = player_to_check.maxRoadLength -1 # Check if anyone has a road at least as long

        for p in all_players:
            if p.longestRoadFlag:
                current_longest_road_holder = p
            if p != player_to_check and p.maxRoadLength > max_len : # Check if any other player has a longer or equal road
                 max_len = p.maxRoadLength


        # If player_to_check's road is strictly greater than any other player with >= 5 roads,
        # or if no one else has >= 5 roads and player_to_check does.
        # And player_to_check doesn't already have the flag.
        if player_to_check.maxRoadLength > max_len and not player_to_check.longestRoadFlag:
            if current_longest_road_holder and current_longest_road_holder != player_to_check:
                print(f"GameLogicManager: {current_longest_road_holder.name} loses Longest Road.")
                current_longest_road_holder.longestRoadFlag = False
                current_longest_road_holder.victoryPoints -= 2

            print(f"GameLogicManager: {player_to_check.name} now has Longest Road with length {player_to_check.maxRoadLength}.")
            player_to_check.longestRoadFlag = True
            player_to_check.victoryPoints += 2
            return True

        # Special case: if the current holder's road length is matched by player_to_check,
        # the original holder keeps it. This logic is implicitly handled by max_len starting from player_to_check.maxRoadLength -1
        # and only awarding if player_to_check.maxRoadLength > max_len.

        return False


    def check_largest_army(self, player_to_check):
        """
        Checks if player_to_check has the largest army and updates VP accordingly.
        Assumes player_to_check.knightsPlayed is up-to-date.
        """
        all_players = self.get_player_list() # Get current player list
        if player_to_check.knightsPlayed < 3:
            return False # Not eligible

        current_largest_army_holder = None
        max_knights = player_to_check.knightsPlayed - 1 # Check if anyone has at least as many knights

        for p in all_players:
            if p.largestArmyFlag:
                current_largest_army_holder = p
            if p != player_to_check and p.knightsPlayed > max_knights:
                max_knights = p.knightsPlayed

        if player_to_check.knightsPlayed > max_knights and not player_to_check.largestArmyFlag:
            if current_largest_army_holder and current_largest_army_holder != player_to_check:
                print(f"GameLogicManager: {current_largest_army_holder.name} loses Largest Army.")
                current_largest_army_holder.largestArmyFlag = False
                current_largest_army_holder.victoryPoints -= 2

            print(f"GameLogicManager: {player_to_check.name} now has Largest Army with {player_to_check.knightsPlayed} knights.")
            player_to_check.largestArmyFlag = True
            player_to_check.victoryPoints += 2
            return True

        return False

    def distribute_resources(self, dice_roll):
        """
        Distributes resources to players based on the dice roll.
        Assumes dice_roll is not 7.
        """
        all_players = self.get_player_list()
        if dice_roll == 7:
            print("GameLogicManager: distribute_resources called with 7, but it should be handled by main game loop's 7-roll logic.")
            return

        hex_resources_rolled = self.board.getHexResourceRolled(dice_roll)
        print(f"GameLogicManager: Resources rolled on hexes: {hex_resources_rolled} for dice roll {dice_roll}")

        for player_i in all_players:
            for settlement_coord in player_i.buildGraph['SETTLEMENTS']:
                for adjacent_hex_idx in self.board.boardGraph[settlement_coord].adjacentHexList:
                    if adjacent_hex_idx in hex_resources_rolled and not self.board.hexTileDict[adjacent_hex_idx].robber:
                        resource_type = self.board.hexTileDict[adjacent_hex_idx].resource.type
                        player_i.resources[resource_type] += 1
                        print(f"GameLogicManager: {player_i.name} collects 1 {resource_type} from Settlement at {settlement_coord} (Hex {adjacent_hex_idx})")

            for city_coord in player_i.buildGraph['CITIES']:
                for adjacent_hex_idx in self.board.boardGraph[city_coord].adjacentHexList:
                    if adjacent_hex_idx in hex_resources_rolled and not self.board.hexTileDict[adjacent_hex_idx].robber:
                        resource_type = self.board.hexTileDict[adjacent_hex_idx].resource.type
                        player_i.resources[resource_type] += 2
                        print(f"GameLogicManager: {player_i.name} collects 2 {resource_type} from City at {city_coord} (Hex {adjacent_hex_idx})")

        print("GameLogicManager: Resource distribution complete.")

if __name__ == '__main__':
    print("GameLogicManager class defined.")
    # Add basic tests here if needed, mocking board and player objects.
    pass
