import json
import numpy as np # Added import

# from board import catanBoard # Assuming catanBoard is in board.py
# from player import player # Assuming player is in player.py

class modelState():
    def __init__(self, catan_game, current_player,
                 robber_movement_is_mandatory=False,
                 discard_is_mandatory=False,
                 num_cards_to_discard=0,
                 setup_road_placement_pending=False, # New flag
                 last_settlement_vertex_index=None, # New flag
                 last_action_status: str = None, # New field for feedback
                 last_action_error_details: str = None,
                 trade_offer_pending: bool = False,
                 trade_offering_player_name: str = None,
                 trade_resources_offered_to_you: dict = None,
                 trade_resources_requested_from_you: dict = None):
        self.board = self.get_board_state(catan_game.board)
        self.players = self.get_players_state(catan_game.playerQueue.queue, current_player, catan_game.board)
        self.current_player_name = current_player.name

        # Game phase (setup or main)
        # The game_phase logic seems a bit complex; game.gameSetup should be the primary source of truth.
        if hasattr(catan_game, 'gameSetup'):
            is_setup_phase = catan_game.gameSetup
        elif hasattr(current_player, 'buildGraph') and len(current_player.buildGraph.get('SETTLEMENTS', [])) < 2:
            # Fallback if gameSetup is not present, infer from player's settlements
            is_setup_phase = True
        else:
            is_setup_phase = False # Default if neither condition met

        self.game_phase = "setup" if is_setup_phase else "main"

        # Flags for special actions required by the current_player
        self.robber_movement_is_mandatory = robber_movement_is_mandatory
        self.discard_is_mandatory = discard_is_mandatory
        self.num_cards_to_discard = num_cards_to_discard if discard_is_mandatory else 0

        self.setup_road_placement_pending = setup_road_placement_pending
        if setup_road_placement_pending and last_settlement_vertex_index is not None:
            self.last_settlement_vertex_index = last_settlement_vertex_index

        # Populate available actions - this needs to be aware of setup_road_placement_pending
        self.available_actions = self.get_available_actions(catan_game, current_player, setup_road_placement_pending, last_settlement_vertex_index)

        # Add current player's total resource count if they need to discard
        # This helps the LLM verify its discard if this info is passed for the discarding player.
        # Note: This info is for the 'current_player' for whom this modelState is generated.
        # If this modelState is generated for a player *about to discard*, this is relevant.
        if discard_is_mandatory:
            self.current_player_total_resources = sum(current_player.resources.values())
        else:
            self.current_player_total_resources = 0

        # Store feedback fields if provided
        # These are dynamically set by catanGame.py before serializing for the LLM if a retry is needed.
        if last_action_status:
            self.last_action_status = last_action_status
        if last_action_error_details:
            self.last_action_error_details = last_action_error_details

        self.trade_offer_pending = trade_offer_pending
        if trade_offer_pending:
            self.trade_offering_player_name = trade_offering_player_name
            self.trade_resources_offered_to_you = trade_resources_offered_to_you
            self.trade_resources_requested_from_you = trade_resources_requested_from_you

        self.action_costs = {
            "build_road": {"WOOD": 1, "BRICK": 1},
            "build_settlement": {"WOOD": 1, "BRICK": 1, "SHEEP": 1, "WHEAT": 1},
            "build_city": {"WHEAT": 2, "ORE": 3},
            "buy_development_card": {"ORE": 1, "SHEEP": 1, "WHEAT": 1}
        }

        # Bank trade ratios for the current player
        self.current_player_bank_trade_ratios = {
            "standard_rate": 4,
            "has_general_3_to_1_port": False,
            "specific_2_to_1_ports": {
                "WOOD": False, "BRICK": False, "SHEEP": False, "WHEAT": False, "ORE": False
            }
        }
        if hasattr(current_player, 'portList'):
            if "3:1 PORT" in current_player.portList:
                self.current_player_bank_trade_ratios["has_general_3_to_1_port"] = True

            resource_types = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
            for res_type in resource_types:
                if f"2:1 {res_type}" in current_player.portList:
                    self.current_player_bank_trade_ratios["specific_2_to_1_ports"][res_type] = True

    def get_available_actions(self, game, player_perspective, setup_road_pending, last_settlement_idx):
        """
        Determines the available actions for the current player based on the game state.
        This is a simplified version and might need to be more comprehensive.
        """
        actions = {
            "build_settlement": [],
            "build_city": [],
            "build_road": []
            # "buy_development_card": True, # Simplified: assumes player can always try if they have resources
            # "trade_with_bank": True,    # Simplified
            # "play_knight_card": True, # Simplified, depends on having the card
            # "end_turn": True
        }

        pixel_to_vertex_index_map = {v_pixel: v_idx for v_idx, v_pixel in game.board.vertex_index_to_pixel_dict.items()}

        if self.game_phase == "setup":
            if setup_road_pending:
                # Only road building is allowed, specifically from last_settlement_idx
                # board.get_setup_roads(player) should correctly use player.buildGraph['SETTLEMENTS'][-1]
                # We must ensure that player.buildGraph reflects the settlement at last_settlement_idx
                # This means the settlement must have been "officially" built and added to player.buildGraph
                # before this modelState is created for the road.
                potential_roads_coords = game.board.get_setup_roads(player_perspective)
            else: # Setup settlement placement
                potential_settlements_coords = game.board.get_setup_settlements(player_perspective)
                for v_coord in potential_settlements_coords.keys():
                    v_idx = pixel_to_vertex_index_map.get(v_coord)
                    if v_idx is not None: actions["build_settlement"].append(v_idx)
                # No roads or cities in this specific setup sub-phase via LLM choice
                potential_roads_coords = {} # Explicitly empty

        else: # Main game phase
            # Settlements
            potential_settlements_coords = game.board.get_potential_settlements(player_perspective)
            for v_coord in potential_settlements_coords.keys():
                v_idx = pixel_to_vertex_index_map.get(v_coord)
                if v_idx is not None: actions["build_settlement"].append(v_idx)

            # Cities
            potential_cities_coords = game.board.get_potential_cities(player_perspective)
            for v_coord in potential_cities_coords.keys():
                v_idx = pixel_to_vertex_index_map.get(v_coord)
                if v_idx is not None: actions["build_city"].append(v_idx)

            # Roads
            potential_roads_coords = game.board.get_potential_roads(player_perspective)

        # Common road processing for setup road and main game roads
        if not (self.game_phase == "setup" and not setup_road_pending): # if not setup settlement phase
            for r_coords_tuple in potential_roads_coords.keys():
                v1_coord, v2_coord = r_coords_tuple
                v1_idx = pixel_to_vertex_index_map.get(v1_coord)
                v2_idx = pixel_to_vertex_index_map.get(v2_coord)
                if v1_idx is not None and v2_idx is not None:
                    # For setup road, ensure it connects to last_settlement_idx
                    if setup_road_pending:
                        if v1_idx == last_settlement_idx or v2_idx == last_settlement_idx:
                             actions["build_road"].append(tuple(sorted((v1_idx, v2_idx))))
                    else: # Main game phase roads
                        actions["build_road"].append(tuple(sorted((v1_idx, v2_idx))))

        # Remove duplicates just in case, and sort for consistency
        actions["build_settlement"] = sorted(list(set(actions["build_settlement"])))
        actions["build_city"] = sorted(list(set(actions["build_city"])))
        actions["build_road"] = sorted(list(set(actions["build_road"])))

        return actions

    def get_board_state(self, board_obj):
        hexes = []
        robber_location_hex_index = -1
        for hex_index, hex_tile in board_obj.hexTileDict.items():
            hexes.append({
                "hex_index": hex_tile.index,
                "resource_type": hex_tile.resource.type if hex_tile.resource else "NONE", # Desert has no resource type
                "roll_number": hex_tile.resource.num if hex_tile.resource and hex_tile.resource.num is not None else 0, # Desert roll num is None
            })
            if hex_tile.robber:
                robber_location_hex_index = hex_tile.index

        ports = []
        # Create a reverse mapping from pixel coordinates to vertex index for easier lookup
        pixel_to_vertex_index_map = {v_pixel: v_idx for v_idx, v_pixel in board_obj.vertex_index_to_pixel_dict.items()}

        for vertex_pixel, vertex_obj in board_obj.boardGraph.items():
            if vertex_obj.port and vertex_obj.port != False:
                port_info = {
                    "type": vertex_obj.port,
                    "vertex_indices": [] # Store all vertices making up this port location
                }
                # Find if this port type already exists to append vertex index
                existing_port = next((p for p in ports if p["type"] == vertex_obj.port), None)
                if existing_port:
                    if pixel_to_vertex_index_map.get(vertex_pixel) not in existing_port["vertex_indices"]:
                         existing_port["vertex_indices"].append(pixel_to_vertex_index_map.get(vertex_pixel))
                else:
                    port_info["vertex_indices"].append(pixel_to_vertex_index_map.get(vertex_pixel))
                    ports.append(port_info)

        # Sort vertex_indices in each port for consistent output
        for port_entry in ports:
            port_entry["vertex_indices"].sort()

        return {
            "hexes": sorted(hexes, key=lambda h: h["hex_index"]), # Sort for consistency
            "ports": sorted(ports, key=lambda p: p["type"]), # Sort for consistency
            "robber_location_hex_index": robber_location_hex_index
        }

    def get_players_state(self, players_queue, current_player, board_obj):
        player_states = []
        # Create a reverse mapping from pixel coordinates to vertex index for easier lookup if not already done
        pixel_to_vertex_index_map = {v_pixel: v_idx for v_idx, v_pixel in board_obj.vertex_index_to_pixel_dict.items()}

        for p in list(players_queue): # Convert queue to list for iteration
            settlements_indices = sorted([pixel_to_vertex_index_map.get(s_coord) for s_coord in p.buildGraph.get('SETTLEMENTS', []) if pixel_to_vertex_index_map.get(s_coord) is not None])
            cities_indices = sorted([pixel_to_vertex_index_map.get(c_coord) for c_coord in p.buildGraph.get('CITIES', []) if pixel_to_vertex_index_map.get(c_coord) is not None])

            roads_indices = []
            for r_tuple in p.buildGraph.get('ROADS', []):
                v1_idx = pixel_to_vertex_index_map.get(r_tuple[0])
                v2_idx = pixel_to_vertex_index_map.get(r_tuple[1])
                if v1_idx is not None and v2_idx is not None:
                    # Sort to ensure consistent representation (e.g., (1,2) is same as (2,1))
                    road_pair = tuple(sorted((v1_idx, v2_idx)))
                    roads_indices.append(road_pair)
            roads_indices = sorted(list(set(roads_indices))) # Remove duplicates and sort

            player_states.append({
                "name": p.name,
                "color": p.color,
                "resources": p.resources, # Assuming this is a dict like {'WOOD': 1, 'BRICK': 0, ...}
                "dev_cards": p.devCards, # Assuming this is a dict like {'KNIGHT': 0, ...}
                "settlements_vertex_indices": settlements_indices,
                "cities_vertex_indices": cities_indices,
                "roads_vertex_indices_pairs": roads_indices,
                "victory_points": p.victoryPoints,
                "knights_played": p.knightsPlayed,
                "largest_army": p.largestArmyFlag,
                "longest_road": p.longestRoadFlag,
                "is_current_player": p.name == current_player.name
            })
        return sorted(player_states, key=lambda ps: ps["name"]) # Sort for consistency

    def _json_serializer(self, obj):
        if isinstance(obj, (np.integer, np.int_)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float_)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_): # Handle numpy bool_ type
            return bool(obj)
        # Check for Point type if it's a common issue and not serializable by default.
        # Assuming Point is from hexLib and might not have __dict__ or be directly serializable.
        # This part is speculative, adjust if Point is already handled or has __dict__.
        # elif isinstance(obj, hexLib.Point): # Requires 'import hexLib'
        #     return {"x": obj.x, "y": obj.y} # Example for Point if it's a simple class
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            # Fallback for objects that are not directly serializable and don't have __dict__
            # For example, simple custom objects or specific library objects.
            # Converting to string is a generic fallback but might not be ideal for all structures.
            try:
                return str(obj)
            except Exception:
                raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable and has no __dict__ or str representation.")

    def to_json(self):
        return json.dumps(self, default=self._json_serializer, indent=4, sort_keys=True)

if __name__ == '__main__':
    # This section is for example and testing; it would require mock objects
    # print("modelState class defined.")
    # class MockPlayer:
    #     def __init__(self, name, color, vp, is_current=False):
    #         self.name = name
    #         self.color = color
    #         self.victoryPoints = vp
    #         self.resources = {'WOOD': 2, 'BRICK': 1, 'SHEEP': 1, 'WHEAT': 0, 'ORE': 0}
    #         self.devCards = {'KNIGHT': 1, 'VP': 0}
    #         self.buildGraph = {'ROADS':[], 'SETTLEMENTS':[], 'CITIES':[]}
    #         self.knightsPlayed = 0
    #         self.largestArmyFlag = False
    #         self.longestRoadFlag = False
    #         self.is_current_player = is_current

    # class MockHexTile:
    #     def __init__(self, index, resource_type, roll_number, robber=False):
    #         self.index = index
    #         self.resource = self if resource_type else None # Simplification for attribute access
    #         self.type = resource_type
    #         self.num = roll_number
    #         self.robber = robber

    # class MockVertex:
    #     def __init__(self, index, port_type=False):
    #         self.vertexIndex = index
    #         self.port = port_type
    #         self.pixelCoords = f"pixel_{index}" # Mock pixel coords

    # class MockBoard:
    #     def __init__(self):
    #         self.hexTileDict = {
    #             0: MockHexTile(0, 'WOOD', 5),
    #             1: MockHexTile(1, 'BRICK', 9),
    #             2: MockHexTiled(2, 'DESERT', 0, True) # Robber on desert
    #         }
    #         # Simplified: map vertex index directly to Vertex obj for port testing
    #         self.vertex_index_to_pixel_dict = {i: f"pixel_{i}" for i in range(54)}
    #         self.boardGraph = {
    #             f"pixel_0": MockVertex(0, port_type='2:1 WOOD'),
    #             f"pixel_1": MockVertex(1, port_type='2:1 WOOD'),
    #             f"pixel_2": MockVertex(2, port_type='3:1 PORT'),
    #             f"pixel_3": MockVertex(3, port_type='3:1 PORT'),
    #             f"pixel_4": MockVertex(4)
    #         }


    # class MockCatanGame:
    #     def __init__(self):
    #         self.board = MockBoard()
    #         self.player_p1 = MockPlayer("Alice", "Red", 2, True)
    #         self.player_p2 = MockPlayer("Bob", "Blue", 1)
    #         self.playerQueue = type('obj', (object,), {'queue': [self.player_p1, self.player_p2]})() # Mock queue
    #         self.gameSetup = True


    # mock_game = MockCatanGame()
    # current_player_mock = mock_game.player_p1

    # state = modelState(mock_game, current_player_mock)
    # print(state.to_json())
    pass
