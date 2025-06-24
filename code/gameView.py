#Settlers of Catan
#Game view class implementation with pygame

import pygame
import os # For potential image loading
from hexTile import *
from hexLib import *
from LLMPlayer import LLMPlayer # Add this import

pygame.init()

# --- Constants for GUI Enhancement ---
# Colors
COLOR_BACKGROUND = pygame.Color('seagreen3') # A more game-like background
COLOR_TILE_OUTLINE = pygame.Color('gray50')
COLOR_TEXT_DARK = pygame.Color('black')
COLOR_TEXT_LIGHT = pygame.Color('white')
COLOR_BUTTON_NORMAL = pygame.Color('royalblue3')
COLOR_BUTTON_HOVER = pygame.Color('royalblue4')
COLOR_BUTTON_TEXT = COLOR_TEXT_LIGHT
COLOR_ROBBER = pygame.Color('black')
COLOR_PORT_TEXT = pygame.Color('navy')

# Resource Colors (slightly adjusted for better contrast/appeal)
COLOR_DICT_RGB = {
    "BRICK": (205, 92, 92),   # IndianRed
    "ORE":   (119, 136, 153), # LightSlateGray
    "WHEAT": (240, 230, 140), # Khaki
    "WOOD":  (139, 69, 19),   # SaddleBrown
    "SHEEP": (144, 238, 144), # LightGreen
    "DESERT":(255, 222, 173)  # NavajoWhite
}
# Player Resource Panel
PLAYER_PANEL_X = 780
PLAYER_PANEL_Y = 20
PLAYER_PANEL_WIDTH = 200
PLAYER_PANEL_HEIGHT_PER_PLAYER = 150 # Adjusted height
PLAYER_PANEL_BG = pygame.Color('gray80')
PLAYER_PANEL_TEXT_COLOR = COLOR_TEXT_DARK
RESOURCE_ICON_SIZE = (20, 20) # For potential resource icons

# --- Fonts ---
try:
    FONT_PRIMARY = 'Verdana'
    FONT_SECONDARY = 'Consolas'
    FONT_TITLE = pygame.font.SysFont(FONT_PRIMARY, 28, bold=True)
    FONT_RESOURCE = pygame.font.SysFont(FONT_PRIMARY, 14)
    FONT_PORTS = pygame.font.SysFont(FONT_PRIMARY, 11, italic=True)
    FONT_BUTTON = pygame.font.SysFont(FONT_PRIMARY, 13, bold=True)
    FONT_DICE_ROLL = pygame.font.SysFont(FONT_PRIMARY, 28, bold=True)
    FONT_ROBBER = pygame.font.SysFont(FONT_PRIMARY, 40, bold=True)
    FONT_PLAYER_INFO = pygame.font.SysFont(FONT_SECONDARY, 12)
    FONT_CHAT = pygame.font.SysFont(FONT_SECONDARY, 11)
except pygame.error: # Fallback if system font isn't available
    print("Warning: Preferred fonts not found, using Pygame default.")
    FONT_PRIMARY = None # Pygame default
    FONT_SECONDARY = None
    FONT_TITLE = pygame.font.SysFont(FONT_PRIMARY, 28, bold=True)
    FONT_RESOURCE = pygame.font.SysFont(FONT_PRIMARY, 14)
    FONT_PORTS = pygame.font.SysFont(FONT_PRIMARY, 11, italic=True)
    FONT_BUTTON = pygame.font.SysFont(FONT_PRIMARY, 13, bold=True)
    FONT_DICE_ROLL = pygame.font.SysFont(FONT_PRIMARY, 28, bold=True)
    FONT_ROBBER = pygame.font.SysFont(FONT_PRIMARY, 40, bold=True)
    FONT_PLAYER_INFO = pygame.font.SysFont(FONT_SECONDARY, 12)
    FONT_CHAT = pygame.font.SysFont(FONT_SECONDARY, 11)


#Class to handle catan board display
class catanGameView():
    'Class definition for Catan board display'
    def __init__(self, catanBoardObject, catanGameObject):
        self.board = catanBoardObject
        self.game = catanGameObject

        self.screen = pygame.display.set_mode(self.board.size)
        pygame.display.set_caption('Settlers of Catan - Enhanced Edition')

        # Store fonts in the instance
        self.font_title = FONT_TITLE
        self.font_resource = FONT_RESOURCE
        self.font_ports = FONT_PORTS
        self.font_button = FONT_BUTTON
        self.font_diceRoll = FONT_DICE_ROLL
        self.font_Robber = FONT_ROBBER
        self.font_player_info = FONT_PLAYER_INFO
        self.font_chat = FONT_CHAT

        # Placeholder for resource icons (if we decide to load them)
        self.resource_icons = {}
        # self.load_resource_icons() # Call a method to load icons if they exist

        return None

    # def load_resource_icons(self):
    #     # Example: self.resource_icons["WOOD"] = pygame.image.load("images/wood_icon.png").convert_alpha()
    #     # Ensure images are in an 'images' folder or adjust path
    #     pass


    #Function to display the initial board (hexes and ports)
    def displayInitialBoard(self):
        self.screen.fill(COLOR_BACKGROUND) # Use the new background color

        #Render each hexTile
        for hexTile in self.board.hexTileDict.values():
            hexTileCorners = polygon_corners(self.board.flat, hexTile.hex)
            hexTileColor_rgb = COLOR_DICT_RGB[hexTile.resource.type]

            pygame.draw.polygon(self.screen, pygame.Color(hexTileColor_rgb), hexTileCorners)
            pygame.draw.polygon(self.screen, COLOR_TILE_OUTLINE, hexTileCorners, 2) # Add outline

            hexTile.pixelCenter = hex_to_pixel(self.board.flat, hexTile.hex)
            if(hexTile.resource.type != 'DESERT'):
                # Improved text rendering: resource type on one line, number below
                res_type_text = self.font_resource.render(str(hexTile.resource.type), True, COLOR_TEXT_DARK)
                res_num_text = self.font_resource.render("(" + str(hexTile.resource.num) + ")", True, COLOR_TEXT_DARK)

                res_type_rect = res_type_text.get_rect(center=(hexTile.pixelCenter.x, hexTile.pixelCenter.y - 8))
                res_num_rect = res_num_text.get_rect(center=(hexTile.pixelCenter.x, hexTile.pixelCenter.y + 8))

                self.screen.blit(res_type_text, res_type_rect)
                self.screen.blit(res_num_text, res_num_rect)
            else: # Desert specific text (optional)
                desert_text = self.font_resource.render("DESERT", True, COLOR_TEXT_DARK)
                desert_rect = desert_text.get_rect(center=hexTile.pixelCenter)
                self.screen.blit(desert_text, desert_rect)


        #Display the Ports
        for vCoord, vertexInfo in self.board.boardGraph.items():
            if(vertexInfo.port != False):
                portTextSurf = self.font_ports.render(vertexInfo.port, True, COLOR_PORT_TEXT)
                # Adjust positioning for better aesthetics - this might need fine-tuning
                text_x, text_y = vCoord.x, vCoord.y
                if vCoord.x < self.board.width / 3: text_x -= 40 # Left side
                elif vCoord.x > self.board.width * 2 / 3: text_x += 10 # Right side
                if vCoord.y < self.board.height / 3: text_y -= 15 # Top side
                elif vCoord.y > self.board.height * 2 / 3: text_y += 10 # Bottom side

                # Simple background for port text
                bg_rect = portTextSurf.get_rect(topleft=(text_x-2, text_y-2))
                bg_rect.width += 4
                bg_rect.height += 4
                pygame.draw.rect(self.screen, COLOR_BACKGROUND, bg_rect, border_radius=3) # Match background or use a light color
                self.screen.blit(portTextSurf, (text_x, text_y))
            
        # No pygame.display.update() here, it's called by displayGameScreen


    #Function to draw a road on the board
    def draw_road(self, edgeToDraw, roadColor):
        # Thicker, more distinct roads
        pygame.draw.line(self.screen, pygame.Color(roadColor), edgeToDraw[0], edgeToDraw[1], 12) # Increased thickness
        pygame.draw.line(self.screen, COLOR_TEXT_DARK, edgeToDraw[0], edgeToDraw[1], 14, ) # Outline


    #Function to draw a potential road on the board - thin
    def draw_possible_road(self, edgeToDraw, roadColor):
        # Dashed line for possible road
        start_pos = edgeToDraw[0]
        end_pos = edgeToDraw[1]
        delta_x = end_pos.x - start_pos.x
        delta_y = end_pos.y - start_pos.y
        distance = (delta_x**2 + delta_y**2)**0.5
        num_dashes = int(distance / 10) # 5px dash, 5px gap

        rects = []
        for i in range(num_dashes):
            if i % 2 == 0: # Draw dash
                p1 = Point(start_pos.x + (delta_x * i / num_dashes), start_pos.y + (delta_y * i / num_dashes))
                p2 = Point(start_pos.x + (delta_x * (i+1) / num_dashes), start_pos.y + (delta_y * (i+1) / num_dashes))
                # pygame.draw.line(self.screen, pygame.Color(roadColor), p1, p2, 6) # Slightly thicker possible road
                # For click detection, we need a single rect. We'll use the original full line rect.
        # Return a rect covering the whole potential road for collision detection
        min_x = min(start_pos.x, end_pos.x)
        min_y = min(start_pos.y, end_pos.y)
        max_x = max(start_pos.x, end_pos.x)
        max_y = max(start_pos.y, end_pos.y)
        roadRect = pygame.Rect(min_x - 5, min_y - 5, (max_x - min_x) + 10, (max_y - min_y) + 10)
        # Draw the dashed line for visual
        for i in range(num_dashes):
            if i % 2 == 0:
                 p1 = Point(start_pos.x + (delta_x * i / num_dashes), start_pos.y + (delta_y * i / num_dashes))
                 p2 = Point(start_pos.x + (delta_x * (i+1) / num_dashes), start_pos.y + (delta_y * (i+1) / num_dashes))
                 pygame.draw.line(self.screen, pygame.Color(roadColor), p1, p2, 6)

        return roadRect


    #Function to draw a settlement on the board at vertexToDraw
    def draw_settlement(self, vertexToDraw, color):
        # Draw a small house-like polygon
        # Points define a simple house shape relative to vertexToDraw
        points = [
            (vertexToDraw.x - 10, vertexToDraw.y + 5),  # Bottom-left
            (vertexToDraw.x + 10, vertexToDraw.y + 5),  # Bottom-right
            (vertexToDraw.x + 10, vertexToDraw.y - 5),  # Top-right base of roof
            (vertexToDraw.x, vertexToDraw.y - 15),      # Peak of roof
            (vertexToDraw.x - 10, vertexToDraw.y - 5)   # Top-left base of roof
        ]
        pygame.draw.polygon(self.screen, pygame.Color(color), points)
        pygame.draw.polygon(self.screen, COLOR_TEXT_DARK, points, 2) # Outline

   
    #Function to draw a potential settlement on the board - thin
    def draw_possible_settlement(self, vertexToDraw, color):
        # Larger, outlined circle for potential settlement
        possibleSettlement = pygame.draw.circle(self.screen, pygame.Color(color), (int(vertexToDraw.x), int(vertexToDraw.y)), 18, 0) # Filled, slightly smaller
        pygame.draw.circle(self.screen, COLOR_TEXT_DARK, (int(vertexToDraw.x), int(vertexToDraw.y)), 18, 3) # Outline
        return possibleSettlement

    
    #Function to draw a city on the board at vertexToDraw
    def draw_city(self, vertexToDraw, color):
        # Draw a larger, more complex shape for a city (e.g., multiple blocks or a taller structure)
        # Example: A base rectangle with a smaller one on top
        base_rect = pygame.Rect(vertexToDraw.x - 15, vertexToDraw.y - 10, 30, 20)
        pygame.draw.rect(self.screen, pygame.Color(color), base_rect)
        pygame.draw.rect(self.screen, COLOR_TEXT_DARK, base_rect, 2) # Outline

        top_rect = pygame.Rect(vertexToDraw.x - 10, vertexToDraw.y - 20, 20, 10)
        pygame.draw.rect(self.screen, pygame.Color(color), top_rect)
        pygame.draw.rect(self.screen, COLOR_TEXT_DARK, top_rect, 2) # Outline

   
    #Function to draw a potential city on the board - thin
    def draw_possible_city(self, vertexToDraw, color):
        # Similar to settlement but maybe a different shape or larger outline
        possibleCity = pygame.draw.circle(self.screen, pygame.Color(color), (int(vertexToDraw.x), int(vertexToDraw.y)), 22, 0) # Filled
        pygame.draw.circle(self.screen, COLOR_TEXT_DARK, (int(vertexToDraw.x), int(vertexToDraw.y)), 22, 4) # Thicker Outline
        return possibleCity

    
    #Function to draw the possible spots for a robber
    def draw_possible_robber(self, vertexToDraw): # vertexToDraw is hex center
        # Large, semi-transparent circle to indicate hex selection for robber
        s = pygame.Surface((100,100), pygame.SRCALPHA) # Per-pixel alpha
        pygame.draw.circle(s, (0,0,0,100), (50,50), 45) # Black, semi-transparent
        self.screen.blit(s, (int(vertexToDraw.x)-50, int(vertexToDraw.y)-50))

        # Return a rect for collision detection (adjust size as needed)
        return pygame.Rect(int(vertexToDraw.x)-45, int(vertexToDraw.y)-45, 90, 90)


    #Function to draw possible players to rob
    def draw_possible_players_to_rob(self, vertexCoord): # vertexCoord is player's settlement/city
        # Highlight player piece to rob
        possiblePlayer = pygame.draw.circle(self.screen, pygame.Color('red'), (int(vertexCoord.x), int(vertexCoord.y)), 30, 4)
        return possiblePlayer
        

    #Function to render basic gameplay buttons
    def displayGameButtons(self):
        button_height = 35
        button_width_short = 90
        button_width_long = 130
        padding = 10
        start_x = 20
        start_y = 20

        buttons_config = [
            {"text": "ROLL DICE", "id": "rollDice", "rect": pygame.Rect(start_x, start_y, button_width_short, button_height), "color": pygame.Color('darkgreen')},
            {"text": "ROAD", "id": "buildRoad", "rect": pygame.Rect(start_x, start_y + button_height + padding, button_width_short, button_height), "color": COLOR_BUTTON_NORMAL},
            {"text": "SETTLE", "id": "buildSettlement", "rect": pygame.Rect(start_x, start_y + 2*(button_height + padding), button_width_short, button_height), "color": COLOR_BUTTON_NORMAL},
            {"text": "CITY", "id": "buildCity", "rect": pygame.Rect(start_x, start_y + 3*(button_height + padding), button_width_short, button_height), "color": COLOR_BUTTON_NORMAL},

            {"text": "BUY DEV CARD", "id": "devCard", "rect": pygame.Rect(start_x, start_y + 5*(button_height + padding), button_width_long, button_height), "color": pygame.Color('gold3')},
            {"text": "PLAY DEV CARD", "id": "playDevCard", "rect": pygame.Rect(start_x, start_y + 6*(button_height + padding), button_width_long, button_height), "color": pygame.Color('gold4')},

            {"text": "TRADE BANK", "id": "tradeBank", "rect": pygame.Rect(start_x, start_y + 8*(button_height + padding), button_width_long, button_height), "color": pygame.Color('mediumpurple3')},
            {"text": "TRADE PLAYER", "id": "tradePlayers", "rect": pygame.Rect(start_x, start_y + 9*(button_height + padding), button_width_long, button_height), "color": pygame.Color('mediumpurple4')},

            {"text": "END TURN", "id": "endTurn", "rect": pygame.Rect(start_x, self.board.height - button_height - padding - 50, button_width_short, button_height), "color": pygame.Color('indianred3')},
        ]

        mouse_pos = pygame.mouse.get_pos()

        for btn in buttons_config:
            # Store rects on self for click detection later
            setattr(self, f"{btn['id']}_button", btn["rect"])

            current_color = btn["color"]
            if btn["rect"].collidepoint(mouse_pos):
                # Darken color on hover (simple hover effect)
                current_color = btn["color"].lerp(COLOR_BUTTON_HOVER, 0.3)

            pygame.draw.rect(self.screen, current_color, btn["rect"], border_radius=5)
            pygame.draw.rect(self.screen, COLOR_TEXT_DARK, btn["rect"], 2, border_radius=5) # Outline

            text_surf = self.font_button.render(btn["text"], True, COLOR_BUTTON_TEXT)
            text_rect = text_surf.get_rect(center=btn["rect"].center)
            self.screen.blit(text_surf, text_rect)


    #Function to display robber
    def displayRobber(self):
        robberText = self.font_Robber.render("R", True, COLOR_ROBBER)
        for hexTile in self.board.hexTileDict.values():
            if(hexTile.robber):
                robberCoords = hexTile.pixelCenter
                # Draw a more prominent robber marker
                pygame.draw.circle(self.screen, COLOR_ROBBER, (int(robberCoords.x), int(robberCoords.y)), 20) # Solid circle
                text_rect = robberText.get_rect(center=(int(robberCoords.x), int(robberCoords.y)))
                self.screen.blit(robberText, text_rect) # Text on top
                break # Assuming only one robber


    def displayPlayerResources(self):
        panel_x = PLAYER_PANEL_X
        panel_y = PLAYER_PANEL_Y

        for i, player_i in enumerate(list(self.game.playerQueue.queue)):
            player_panel_rect = pygame.Rect(panel_x, panel_y + i * (PLAYER_PANEL_HEIGHT_PER_PLAYER + 10), PLAYER_PANEL_WIDTH, PLAYER_PANEL_HEIGHT_PER_PLAYER)
            pygame.draw.rect(self.screen, PLAYER_PANEL_BG, player_panel_rect, border_radius=5)
            pygame.draw.rect(self.screen, pygame.Color(player_i.color), player_panel_rect, 3, border_radius=5) # Border with player color

            text_y_offset = player_panel_rect.top + 10

            # Player Name
            name_surf = self.font_player_info.render(f"{player_i.name} (VP: {player_i.victoryPoints})", True, PLAYER_PANEL_TEXT_COLOR)
            self.screen.blit(name_surf, (player_panel_rect.left + 10, text_y_offset))
            text_y_offset += 20

            # Resources
            res_order = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
            for res_idx, res_name in enumerate(res_order):
                res_count = player_i.resources.get(res_name, 0)

                # Try to use icons if available, otherwise text
                # if res_name in self.resource_icons:
                #     icon_rect = self.resource_icons[res_name].get_rect(topleft=(player_panel_rect.left + 10, text_y_offset))
                #     self.screen.blit(self.resource_icons[res_name], icon_rect)
                #     count_surf = self.font_player_info.render(f": {res_count}", True, PLAYER_PANEL_TEXT_COLOR)
                #     self.screen.blit(count_surf, (icon_rect.right + 5, text_y_offset))
                # else:
                res_surf = self.font_player_info.render(f"{res_name}: {res_count}", True, PLAYER_PANEL_TEXT_COLOR)
                self.screen.blit(res_surf, (player_panel_rect.left + 15, text_y_offset))

                text_y_offset += 18

            # LLM Thoughts (if applicable and not too long)
            if isinstance(player_i, LLMPlayer) and hasattr(player_i, 'thoughts') and player_i.thoughts:
                # Display first few words of thoughts
                thought_snippet = player_i.thoughts.split()[:10] # First 10 words
                display_thought = " ".join(thought_snippet) + ("..." if len(player_i.thoughts.split()) > 10 else "")
                thought_surf = self.font_player_info.render(f"Thinking: {display_thought}", True, pygame.Color('gray30'))
                self.screen.blit(thought_surf, (player_panel_rect.left + 10, text_y_offset + 5))


    #Function to display the gameState board - use to display intermediate build screens
    def displayGameScreen(self):
        # Clear screen / Display board elements
        self.displayInitialBoard() # Draws hexes, ports

        # Display existing structures
        for player_i in list(self.game.playerQueue.queue):
            for existingRoad in player_i.buildGraph['ROADS']:
                self.draw_road(existingRoad, player_i.color)
            for settlementCoord in player_i.buildGraph['SETTLEMENTS']:
                self.draw_settlement(settlementCoord, player_i.color)
            for cityCoord in player_i.buildGraph['CITIES']:
                self.draw_city(cityCoord, player_i.color)

        self.displayRobber() # Draw Robber on top of hexes but below buttons/panels
        self.displayGameButtons() # Draw action buttons
        self.displayPlayerResources() # Draw player info panels

        # Display Global Chat History
        chat_base_x = 150
        chat_base_y = self.board.height - 150 # Position above bottom edge
        chat_line_height = 15
        chat_max_lines = 8
        chat_box_width = 600

        chat_history_to_display = self.game.global_chat_history[-chat_max_lines:]
        if chat_history_to_display:
            num_chat_lines = len(chat_history_to_display)
            chat_box_height = num_chat_lines * chat_line_height + 10

            # Semi-transparent background for chat
            chat_bg_surf = pygame.Surface((chat_box_width, chat_box_height), pygame.SRCALPHA)
            chat_bg_surf.fill((50, 50, 50, 180)) # Dark gray, semi-transparent
            self.screen.blit(chat_bg_surf, (chat_base_x - 5, chat_base_y - 5))

            for idx, chat_entry in enumerate(chat_history_to_display):
                player_name = chat_entry.get("player", "System")
                message = chat_entry.get("message", "")
                chat_text_surface = self.font_chat.render(f"[{player_name}]: {message}", True, COLOR_TEXT_LIGHT)
                self.screen.blit(chat_text_surface, (chat_base_x, chat_base_y + (idx * chat_line_height)))

        # Display Private Chat Status
        if hasattr(self.game, 'active_private_chat_participants') and self.game.active_private_chat_participants:
            p1_name, p2_name = self.game.active_private_chat_participants
            status_font = self.font_player_info # Use existing font
            status_text = f"Private Chat: {p1_name} & {p2_name}"
            status_surface = status_font.render(status_text, True, pygame.Color('yellow'))

            status_x = self.board.width // 2 - status_surface.get_width() // 2
            status_y = 5
            pygame.draw.rect(self.screen, pygame.Color('gray10'), (status_x - 5, status_y - 2, status_surface.get_width() + 10, status_surface.get_height() + 4), border_radius=3)
            self.screen.blit(status_surface, (status_x, status_y))

        pygame.display.flip() # Use flip for full screen update
        return


    #Function to display dice roll
    def displayDiceRoll(self, diceNums):
        # Display dice roll more centrally or in a dedicated spot
        dice_area_rect = pygame.Rect(self.board.width // 2 - 50, 30, 100, 50)
        pygame.draw.rect(self.screen, COLOR_BACKGROUND, dice_area_rect) # Clear previous roll
        
        diceNumText = self.font_diceRoll.render(str(diceNums), True, COLOR_TEXT_DARK)
        text_rect = diceNumText.get_rect(center=dice_area_rect.center)
        self.screen.blit(diceNumText, text_rect)

        # pygame.display.update(dice_area_rect) # Update only the dice roll area
        # Full flip is handled by displayGameScreen, so this might not be needed if called within its flow.


    def buildRoad_display(self, currentPlayer, roadsPossibleDict):
        # Existing logic for drawing possible roads and handling clicks
        # Visuals are updated via draw_possible_road
        for roadEdge in roadsPossibleDict.keys():
            if roadsPossibleDict[roadEdge]: # This value is initially True
                roadsPossibleDict[roadEdge] = self.draw_possible_road(roadEdge, currentPlayer.color)

        pygame.display.flip() # Update screen to show possible roads

        # Event loop remains largely the same
        mouseClicked = False
        while(mouseClicked == False):
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.MOUSEBUTTONDOWN:
                    # Check for button clicks first (e.g., a cancel button if added)
                    # ... (button click handling) ...

                    for road, roadRect in roadsPossibleDict.items():
                        if roadRect and roadRect.collidepoint(e.pos): # Check if roadRect is not None
                            return road # Return the chosen road edge

                    # If click was not on a road, it might be a click to deselect/cancel
                    # For now, any click not on a road in this phase (if not setup) means cancel
                    if not self.game.gameSetup:
                        mouseClicked = True
                        return None # Cancelled building road

            # If in setup, player MUST build a road
            if self.game.gameSetup and not mouseClicked: # Avoid busy loop if no MOUSEBUTTONDOWN
                pygame.time.wait(10) # Small pause
                        

    def buildSettlement_display(self, currentPlayer, verticesPossibleDict):
        # Visuals updated via draw_possible_settlement
        for v in verticesPossibleDict.keys():
            if verticesPossibleDict[v]: # Initially True
                verticesPossibleDict[v] = self.draw_possible_settlement(v, currentPlayer.color)

        pygame.display.flip()

        # Event loop
        mouseClicked = False
        while(mouseClicked == False):
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.MOUSEBUTTONDOWN:
                    for vertex, vertexRect in verticesPossibleDict.items():
                        if vertexRect and vertexRect.collidepoint(e.pos):
                            return vertex

                    if not self.game.gameSetup:
                        mouseClicked = True
                        return None

            if self.game.gameSetup and not mouseClicked:
                pygame.time.wait(10)


    def buildCity_display(self, currentPlayer, verticesPossibleDict):
        # Visuals updated via draw_possible_city
        for c in verticesPossibleDict.keys():
            if verticesPossibleDict[c]: # Initially True
                verticesPossibleDict[c] = self.draw_possible_city(c, currentPlayer.color)

        pygame.display.flip()

        # Event loop
        mouseClicked = False
        while(mouseClicked == False):
            for e in pygame.event.get(): 
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.MOUSEBUTTONDOWN:
                    for vertex, vertexRect in verticesPossibleDict.items():
                        if vertexRect and vertexRect.collidepoint(e.pos):
                            return vertex
                    mouseClicked = True # Clicked somewhere else
                    return None

            pygame.time.wait(10) # Avoid busy loop if no event

    #Function to control the move-robber action with display
    def moveRobber_display(self, currentPlayer, possibleRobberDict_Hexes): # Renamed for clarity
        # possibleRobberDict_Hexes has hexIndex as key, hexTile object as value
        # We need to store the clickable rects
        clickable_robber_hex_rects = {}
        for hexIndex, hexTileObj in possibleRobberDict_Hexes.items():
            # draw_possible_robber now returns the rect for collision
            clickable_robber_hex_rects[hexIndex] = self.draw_possible_robber(hexTileObj.pixelCenter)

        pygame.display.flip()

        mouseClicked = False
        while(mouseClicked == False):
            for e in pygame.event.get(): 
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if(e.type == pygame.MOUSEBUTTONDOWN):
                    for hexIndex, robberCircleRect in clickable_robber_hex_rects.items():
                        if(robberCircleRect.collidepoint(e.pos)): 
                            possiblePlayerDict_Victims = self.board.get_players_to_rob(hexIndex) # playerObj: vertexCoord
                            playerToRob = self.choosePlayerToRob_display(possiblePlayerDict_Victims)
                            mouseClicked = True
                            return hexIndex, playerToRob
            pygame.time.wait(10)

    
    #Function to control the choice of player to rob with display
    def choosePlayerToRob_display(self, possiblePlayerDict_Victims): # playerObj: vertexCoord
        if not possiblePlayerDict_Victims: # No one to rob on this hex
            return None

        clickable_victim_rects = {}
        for playerObj, vertexCoord_of_building in possiblePlayerDict_Victims.items():
            # draw_possible_players_to_rob highlights the building at vertexCoord_of_building
            clickable_victim_rects[playerObj] = self.draw_possible_players_to_rob(vertexCoord_of_building)

        pygame.display.flip()

        mouseClicked = False
        while(mouseClicked == False):
            for e in pygame.event.get(): 
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if(e.type == pygame.MOUSEBUTTONDOWN):
                    for playerToRob, playerCircleRect in clickable_victim_rects.items():
                        if(playerCircleRect.collidepoint(e.pos)): 
                            return playerToRob # Return the player object
            pygame.time.wait(10)
