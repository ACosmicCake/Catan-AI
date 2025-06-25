class NegotiationManager:
    VALID_STATES = ["IDLE", "PROPOSED", "COUNTERED", "ACCEPTED", "REJECTED", "ENDED_BY_PLAYER", "ENDED_SYSTEM"]

    def __init__(self, game_turn_started: int):
        self.initiator = None
        self.target = None
        self.history = []  # List of offers, where each offer is a dict
        self.current_state = "IDLE"
        self.turn_started = game_turn_started
        self.last_turn_updated = game_turn_started
        self.active_negotiator = None # Player object whose turn it is to respond/counter

    def start_negotiation(self, initiator_player, target_player, initial_offer_details: dict, game_turn: int):
        if self.current_state != "IDLE":
            print(f"Warning: Starting a new negotiation while one is already active (state: {self.current_state}). This may override.")
            # Potentially log or handle the override more gracefully

        self.initiator = initiator_player
        self.target = target_player
        self.history = [initial_offer_details] # initial_offer_details should include 'from_player', 'to_player', 'resources_offered', 'resources_requested', 'turn'
        self.current_state = "PROPOSED"
        self.active_negotiator = target_player # Target player responds first
        self.last_turn_updated = game_turn
        print(f"Negotiation started by {initiator_player.name} with {target_player.name} at turn {game_turn}. Offer: {initial_offer_details}")
        return True

    def add_counter_offer(self, countering_player, counter_offer_details: dict, game_turn: int):
        if self.current_state not in ["PROPOSED", "COUNTERED"]:
            print(f"Error: Cannot make counter-offer in state {self.current_state}")
            return False
        if countering_player != self.active_negotiator:
            print(f"Error: It's not {countering_player.name}'s turn to make a counter-offer. Active: {self.active_negotiator.name}")
            return False

        self.history.append(counter_offer_details)
        self.current_state = "COUNTERED"
        # Switch active negotiator
        self.active_negotiator = self.initiator if countering_player == self.target else self.target
        self.last_turn_updated = game_turn
        print(f"{countering_player.name} made a counter-offer at turn {game_turn}. New offer: {counter_offer_details}")
        return True

    def accept_offer(self, accepting_player, game_turn: int):
        if self.current_state not in ["PROPOSED", "COUNTERED"]:
            print(f"Error: Cannot accept offer in state {self.current_state}")
            return False
        if accepting_player != self.active_negotiator:
            print(f"Error: It's not {accepting_player.name}'s turn to accept. Active: {self.active_negotiator.name}")
            return False

        # Further validation (e.g., can players afford the trade) should be done by AIGame before calling this
        last_offer = self.history[-1]
        self.history.append({
            "type": "acceptance",
            "player": accepting_player.name,
            "accepted_offer": last_offer,
            "turn": game_turn
        })
        self.current_state = "ACCEPTED"
        self.active_negotiator = None # No active negotiator once accepted
        self.last_turn_updated = game_turn
        print(f"Offer accepted by {accepting_player.name} at turn {game_turn}. Last offer was: {last_offer}")
        return True

    def reject_offer(self, rejecting_player, reason: str = "No reason given.", game_turn: int):
        if self.current_state not in ["PROPOSED", "COUNTERED"]:
            # Allow rejection even if state is already ended, as a final explicit act.
            # print(f"Warning: Rejecting offer in state {self.current_state}")
            pass # Allow this
        if rejecting_player != self.active_negotiator and self.current_state in ["PROPOSED", "COUNTERED"]:
            print(f"Error: It's not {rejecting_player.name}'s turn to reject. Active: {self.active_negotiator.name if self.active_negotiator else 'None'}")
            return False

        last_offer = self.history[-1] if self.history else None
        self.history.append({
            "type": "rejection",
            "player": rejecting_player.name,
            "rejected_offer": last_offer,
            "reason": reason,
            "turn": game_turn
        })
        self.current_state = "REJECTED"
        self.active_negotiator = None
        self.last_turn_updated = game_turn
        print(f"Offer rejected by {rejecting_player.name} at turn {game_turn}. Reason: {reason}. Last offer: {last_offer}")
        return True

    def end_negotiation_by_player(self, player_ending, reason: str = "Player chose to end.", game_turn: int):
        if self.current_state == "IDLE" or self.current_state.startswith("ENDED_"):
            print(f"Negotiation already ended or idle. Current state: {self.current_state}")
            return False # Or True if we consider it "successfully ended"

        self.history.append({
            "type": "ended_by_player",
            "player": player_ending.name,
            "reason": reason,
            "turn": game_turn
        })
        self.current_state = "ENDED_BY_PLAYER"
        self.active_negotiator = None
        self.last_turn_updated = game_turn
        print(f"Negotiation ended by {player_ending.name} at turn {game_turn}. Reason: {reason}")
        return True

    def end_negotiation_by_system(self, reason: str, game_turn: int):
        if self.current_state == "IDLE" or self.current_state.startswith("ENDED_"):
            # This might happen if system tries to end an already concluded negotiation, e.g. timeout after player accept/reject
            print(f"Negotiation already ended or idle. Current state: {self.current_state}. System tried to end for: {reason}")
            return True

        self.history.append({
            "type": "ended_by_system",
            "reason": reason,
            "turn": game_turn
        })
        self.current_state = "ENDED_SYSTEM"
        self.active_negotiator = None
        self.last_turn_updated = game_turn
        print(f"Negotiation ended by system at turn {game_turn}. Reason: {reason}")
        return True

    def get_context_for_player(self, player_obj):
        """
        Returns the negotiation context relevant for the given player.
        This will be used by modelState.
        """
        if not self.initiator or not self.target: # Not started or improperly configured
            return {
                "negotiation_active": False
            }

        is_participant = (player_obj == self.initiator or player_obj == self.target)
        if not is_participant or self.current_state == "IDLE" or self.current_state.startswith("ENDED_") or self.current_state == "ACCEPTED" or self.current_state == "REJECTED":
            return {
                "negotiation_active": False,
                "negotiation_last_state": self.current_state, # Provide last state if it just ended
                "negotiation_history_summary": self.history[-3:] if self.history else [] # Last few entries
            }

        partner = self.target if player_obj == self.initiator else self.initiator

        return {
            "negotiation_active": True,
            "negotiation_state": self.current_state,
            "negotiation_initiator_name": self.initiator.name,
            "negotiation_target_name": self.target.name,
            "negotiation_partner_name": partner.name,
            "your_turn_to_negotiate": player_obj == self.active_negotiator,
            "negotiation_history": self.history, # Full history for participants
            "last_offer": self.history[-1] if self.history else None
        }

    def is_active(self):
        return self.current_state not in ["IDLE", "ACCEPTED", "REJECTED", "ENDED_BY_PLAYER", "ENDED_SYSTEM"]

    def get_last_offer(self):
        if self.history:
            # Iterate backwards to find the last actual offer (PROPOSED or COUNTERED)
            for entry in reversed(self.history):
                if entry.get("type") in [None, "initial_offer", "counter_offer"] and "resources_offered" in entry: # Assuming type might be implicit for offers
                    return entry
        return None

if __name__ == '__main__':
    # Basic Test
    class MockPlayer:
        def __init__(self, name):
            self.name = name

    p1 = MockPlayer("Alice")
    p2 = MockPlayer("Bob")

    manager = NegotiationManager(game_turn_started=1)
    print(f"Initial state: {manager.current_state}")

    initial_offer = {
        "from_player": p1.name, "to_player": p2.name,
        "resources_offered": {"WOOD": 2}, "resources_requested": {"BRICK": 1},
        "turn": 1, "type": "initial_offer"
    }
    manager.start_negotiation(p1, p2, initial_offer, game_turn=1)
    print(f"State after start: {manager.current_state}, Active: {manager.active_negotiator.name if manager.active_negotiator else 'None'}")
    print(f"Context for Bob: {manager.get_context_for_player(p2)}")

    counter_offer = {
        "from_player": p2.name, "to_player": p1.name,
        "resources_offered": {"BRICK": 1}, "resources_requested": {"WOOD": 1, "SHEEP": 1},
        "turn": 2, "type": "counter_offer"
    }
    manager.add_counter_offer(p2, counter_offer, game_turn=2)
    print(f"State after counter: {manager.current_state}, Active: {manager.active_negotiator.name if manager.active_negotiator else 'None'}")
    print(f"Context for Alice: {manager.get_context_for_player(p1)}")

    manager.accept_offer(p1, game_turn=3)
    print(f"State after accept: {manager.current_state}")
    print(f"Context for Bob after accept: {manager.get_context_for_player(p2)}")
    print(f"Is active: {manager.is_active()}")

    # Test rejection
    manager2 = NegotiationManager(game_turn_started=4)
    manager2.start_negotiation(p1, p2, initial_offer, game_turn=4)
    manager2.reject_offer(p2, "Not enough wood offered", game_turn=5)
    print(f"State after reject: {manager2.current_state}")
    print(f"Context for Alice after reject: {manager2.get_context_for_player(p1)}")

    # Test end by player
    manager3 = NegotiationManager(game_turn_started=6)
    manager3.start_negotiation(p1, p2, initial_offer, game_turn=6)
    manager3.end_negotiation_by_player(p1, "Need to build", game_turn=7)
    print(f"State after end by player: {manager3.current_state}")
    print(f"Is active: {manager3.is_active()}")
    print(f"Last offer in manager3: {manager3.get_last_offer()}")
    print(f"History of manager3: {json.dumps(manager3.history, indent=2)}")

```
