import json
import numpy as np # Added import

# from board import catanBoard # Assuming catanBoard is in board.py
# from player import player # Assuming player is in player.py

# Probabilities represented as "dots" similar to game pieces (max 5 dots for 6 & 8)
# 7 is not a resource-producing roll.
DICE_ROLL_PROBABILITIES = {
    2: 1,  # (1/36)
    3: 2,  # (2/36)
    4: 3,  # (3/36)
    5: 4,  # (4/36)
    6: 5,  # (5/36)
    8: 5,  # (5/36)
    9: 4,  # (4/36)
    10: 3, # (3/36)
    11: 2, # (2/36)
    12: 1, # (1/36)
    0: 0,  # For Desert (roll_number is 0 or None)
    None: 0
}

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
                 trade_resources_requested_from_you: dict = None,
                 private_chat_active: bool = False, # Added for private chat context
                 communication_phase_active: bool = False, # Added for global communication phase context
                 # Negotiation specific flags passed during construction if this state is for a negotiation turn
                 is_negotiation_turn: bool = False,
                 negotiation_partner_name: str = None):
        self.board = self.get_board_state(catan_game.board) # Gets initial board state including choke points placeholder for hex_control
        self.players = self.get_players_state(catan_game, current_player, catan_game.board) # Pass full game for maxPoints access

        # Calculate hex_control now that both board and player states (with settlement/city locations) are available
        # Need pixel_to_vertex_index_map for _calculate_hex_control
        pixel_to_vertex_index_map = {v_pixel: v_idx for v_idx, v_pixel in catan_game.board.vertex_index_to_pixel_dict.items()}
        self._calculate_hex_control(catan_game.board, self.players, pixel_to_vertex_index_map)

        self.current_player_name = current_player.name
        self.development_cards_left_in_deck = len(catan_game.board.devCardStack) if hasattr(catan_game, 'board') and hasattr(catan_game.board, 'devCardStack') else 0

        # Initialize negotiation fields
        self.negotiation_in_progress = False
        self.negotiation_participants = []
        self.negotiation_history = []
        self.your_turn_to_negotiate = False
        self.negotiation_partner_name = None # Companion to your_turn_to_negotiate

        if hasattr(catan_game, 'negotiation_active') and catan_game.negotiation_active:
            # Check if the current_player is part of the active negotiation
            negotiation_ctx = catan_game.negotiation_context
            if negotiation_ctx.get('initiator') == current_player or negotiation_ctx.get('target') == current_player:
                self.negotiation_in_progress = True
                self.negotiation_participants = [negotiation_ctx['initiator'].name, negotiation_ctx['target'].name]
                self.negotiation_history = negotiation_ctx['offer_history'] # This is a list of dicts

                # Determine if it's this player's turn to negotiate and who the partner is
                # This part depends on how catanAIGame.handle_negotiation passes control.
                # We'll use the `is_negotiation_turn` and `negotiation_partner_name` passed to __init__.
                if is_negotiation_turn:
                    self.your_turn_to_negotiate = True
                    self.negotiation_partner_name = negotiation_partner_name

        # Pick up feedback from player object if available (set by AIGame.py after an action)
        # These are read before other state construction that might depend on them (like available_actions if feedback was about a failed build)
        self.last_action_status = getattr(current_player, 'feedback_status_for_next_state', None)
        self.last_action_error_details = getattr(current_player, 'feedback_details_for_next_state', None)

        # Important: Clear them from the player object after reading, so they are not stale for the next unrelated state.
        # This ensures feedback is for the immediately following state generation.
        if hasattr(current_player, 'feedback_status_for_next_state'):
            current_player.feedback_status_for_next_state = None
        if hasattr(current_player, 'feedback_details_for_next_state'):
            current_player.feedback_details_for_next_state = None

        # Chat histories and phases
        self.global_chat_history = catan_game.global_chat_history[-10:] # Include last 10 global messages
        self.private_chat_history = []
        if hasattr(current_player, 'name') and hasattr(catan_game, 'private_chat_histories'):
            for (p1_name, p2_name), history in catan_game.private_chat_histories.items():
                if current_player.name in (p1_name, p2_name):
                    self.private_chat_history.append({
                        "participants": [p1_name, p2_name],
                        "history": history[-10:]
                    })
        self.private_chat_active = private_chat_active
        self.communication_phase_active = communication_phase_active # Reflects game's current communication phase status

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
                "probability_dots": DICE_ROLL_PROBABILITIES.get(hex_tile.resource.num if hex_tile.resource else 0, 0)
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

        # --- Hex Control Calculation ---
        # This needs player information, so it's better done after players_states are partially computed
        # or by passing players_queue and pixel_to_vertex_index_map into this function.
        # For now, I'll compute it here, assuming access to necessary player build data.
        # This implies get_players_state might need to be called first or player data passed in.
        # To keep it within get_board_state, it needs to iterate through all players.
        # This is inefficient. A better design would be to calculate this in the main __init__ after both board and players are fetched.
        # TEMP: For now, let's assume this will be refactored or player data is accessible.
        # For this step, I will defer full hex_control to a post-processing step if players_queue is not available here.
        # Let's assume for the plan that this calculation can access player settlement/city locations.
        # For now, I'll just add a placeholder for hex_control in the hexes list.

        # Add hex_control placeholder to each hex
        for h_data in hexes:
            h_data["hex_control"] = [] # Placeholder: list of {"player_name": "name", "influence": X}

        # --- Choke Points (Simplified) ---
        # Vertices adjacent to 3 hexes, listing their roll numbers.
        choke_points_data = []
        for v_coord, vertex_obj in board_obj.boardGraph.items():
            if len(vertex_obj.adjacentHexList) == 3: # Typically, intersections are on 3 hexes
                v_idx = pixel_to_vertex_index_map.get(v_coord)
                if v_idx is not None:
                    connected_hex_details = []
                    is_valuable_choke = False
                    high_prob_count = 0
                    for h_idx_adj in vertex_obj.adjacentHexList:
                        hex_tile_adj = board_obj.hexTileDict.get(h_idx_adj)
                        if hex_tile_adj and hex_tile_adj.resource:
                            roll_num = hex_tile_adj.resource.num if hex_tile_adj.resource.num is not None else 0
                            connected_hex_details.append({
                                "hex_index": h_idx_adj,
                                "resource_type": hex_tile_adj.resource.type,
                                "roll_number": roll_num
                            })
                            if roll_num in [6, 8, 5, 9]: # High probability numbers
                                high_prob_count +=1
                    if high_prob_count >= 2: # At least two high-probability hexes connected
                        is_valuable_choke = True

                    if is_valuable_choke: # Only add if it seems valuable
                        choke_points_data.append({
                            "vertex_index": v_idx,
                            "connected_hexes": connected_hex_details
                        })
        choke_points_data = sorted(choke_points_data, key=lambda cp: cp["vertex_index"])


        return {
            "hexes": sorted(hexes, key=lambda h: h["hex_index"]), # Sort for consistency
            "ports": sorted(ports, key=lambda p: p["type"]), # Sort for consistency
            "robber_location_hex_index": robber_location_hex_index,
            "choke_points": choke_points_data # Add choke points here
            # "hex_control" will be added later or needs refactor
        }

    # Helper method to calculate hex control, called from __init__ after basic board and player states are ready
    def _calculate_hex_control(self, board_obj, players_list_of_dicts, pixel_to_vertex_index_map):
        hex_control_map = {h_idx: [] for h_idx in board_obj.hexTileDict.keys()}

        for p_state in players_list_of_dicts:
            player_name = p_state["name"]
            # Iterate through player's settlements
            for s_v_idx in p_state["settlements_vertex_indices"]:
                s_v_coord = board_obj.vertex_index_to_pixel_dict.get(s_v_idx)
                if s_v_coord:
                    vertex_obj = board_obj.boardGraph.get(s_v_coord)
                    if vertex_obj:
                        for h_idx in vertex_obj.adjacentHexList:
                            # Check if player already listed for this hex, update influence or add new
                            found_player_influence = next((inf for inf in hex_control_map.get(h_idx, []) if inf["player_name"] == player_name), None)
                            if found_player_influence:
                                found_player_influence["influence"] += 1
                            elif h_idx in hex_control_map: # Ensure hex_idx is valid before appending
                                hex_control_map[h_idx].append({"player_name": player_name, "influence": 1})
            # Iterate through player's cities
            for c_v_idx in p_state["cities_vertex_indices"]:
                c_v_coord = board_obj.vertex_index_to_pixel_dict.get(c_v_idx)
                if c_v_coord:
                    vertex_obj = board_obj.boardGraph.get(c_v_coord)
                    if vertex_obj:
                        for h_idx in vertex_obj.adjacentHexList:
                            found_player_influence = next((inf for inf in hex_control_map.get(h_idx, []) if inf["player_name"] == player_name), None)
                            if found_player_influence:
                                found_player_influence["influence"] += 2 # Cities have more influence
                            elif h_idx in hex_control_map: # Ensure hex_idx is valid before appending
                                hex_control_map[h_idx].append({"player_name": player_name, "influence": 2})

        # Integrate this into self.board.hexes
        for h_data in self.board["hexes"]:
            h_idx = h_data["hex_index"]
            if h_idx in hex_control_map:
                h_data["hex_control"] = sorted(hex_control_map[h_idx], key=lambda x: (-x["influence"], x["player_name"]))


    def get_players_state(self, catan_game, current_player, board_obj): # Changed players_queue to catan_game
        player_states = []
        players_queue = catan_game.playerQueue.queue # Get queue from catan_game
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
                "is_current_player": p.name == current_player.name,
                "threat_score": 0 # Will be calculated below
            })

        # Calculate strategic overlays: resource_affinity, strategic_posture, and enhanced threat_level
        for player_state in player_states:
            original_player_object = next((p_obj for p_obj in list(players_queue) if p_obj.name == player_state["name"]), None)

            if original_player_object:
                # 1. Resource Affinity (based on production potential from settlements/cities)
                production_potential = {"WOOD": 0, "BRICK": 0, "SHEEP": 0, "WHEAT": 0, "ORE": 0}
                player_buildings = [] # List of (vertex_coord, type_is_city=True/False)
                for s_coord in original_player_object.buildGraph.get('SETTLEMENTS', []):
                    player_buildings.append((s_coord, False))
                for c_coord in original_player_object.buildGraph.get('CITIES', []):
                    player_buildings.append((c_coord, True))

                for v_coord, is_city in player_buildings:
                    vertex_obj = board_obj.boardGraph.get(v_coord)
                    if vertex_obj:
                        for hex_idx in vertex_obj.adjacentHexList:
                            hex_tile = board_obj.hexTileDict.get(hex_idx)
                            if hex_tile and hex_tile.resource and hex_tile.resource.type != "DESERT":
                                resource_type = hex_tile.resource.type
                                production_potential[resource_type] += (2 if is_city else 1)

                if sum(production_potential.values()) > 0:
                    player_state["resource_affinity"] = max(production_potential, key=production_potential.get)
                else:
                    player_state["resource_affinity"] = "NONE"

                # 2. Strategic Posture (simplified inference)
                num_settlements = len(player_state["settlements_vertex_indices"])
                num_cities = len(player_state["cities_vertex_indices"])
                # road_length = original_player_object.maxRoadLength # Assuming player object has this
                # For now, use number of road segments as a proxy if maxRoadLength isn't directly on player_state
                road_segments_count = len(player_state["roads_vertex_indices_pairs"])


                # dev_cards_bought = original_player_object.developmentCardsBought # If tracked
                # Using knights_played and unrevealed dev cards as proxy
                dev_cards_metric = player_state["knights_played"] + sum(player_state["dev_cards"].values())


                postures = []
                if num_cities > num_settlements / 2 and num_cities > 0: # More cities or significant cities
                    postures.append("CITY_BUILDER")
                if road_segments_count >= 5 : # Threshold for seeking longest road
                    postures.append("LONGEST_ROAD_SEEKER")
                if dev_cards_metric >= 2: # Actively using/buying dev cards
                    postures.append("DEVELOPMENT_CARD_USER")
                if num_settlements > num_cities and num_settlements >=3: # Expansionist
                     postures.append("EXPANSIONIST")

                if not postures and (num_settlements + num_cities) < 3 : postures.append("EARLY_DEVELOPMENT")
                elif not postures: postures.append("BALANCED")

                player_state["strategic_posture"] = ", ".join(postures) if postures else "UNDEFINED"


                # 3. Enhanced Threat Level
                vp = player_state["victory_points"]
                knights = player_state["knights_played"]
                num_resource_cards = sum(original_player_object.resources.values())
                num_dev_cards_unplayed = sum(player_state["dev_cards"].values()) # Already in player_state

                base_threat = (vp * 3) + (knights * 1.5) + (road_segments_count * 0.2) + \
                              ((num_resource_cards + num_dev_cards_unplayed) * 0.5)

                # Proximity to victory bonus (e.g. 10 points to win)
                max_points_for_game = catan_game.maxPoints if hasattr(catan_game, 'maxPoints') else 10
                if vp >= max_points_for_game - 2: # e.g. 8 or 9 points if max is 10
                    base_threat += 5
                elif vp >= max_points_for_game - 3: # e.g. 7 points if max is 10
                    base_threat += 2

                player_state["threat_level"] = round(base_threat, 1)
                del player_state["threat_score"] # Remove old field if it was there (it's initialized to 0 now)

            else: # Fallback if original_player_object not found
                player_state["resource_affinity"] = "UNKNOWN"
                player_state["strategic_posture"] = "UNKNOWN"
                player_state["threat_level"] = player_state.get("victory_points",0) * 3


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
