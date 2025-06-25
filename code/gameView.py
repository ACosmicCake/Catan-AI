#Settlers of Catan
#Game view class implementation with pygame

import pygame
import os # For potential image loading
import sys # For sys.exit in event loops
from hexTile import *
from hexLib import *
from LLMPlayer import LLMPlayer

pygame.init()

# --- Constants for GUI Enhancement ---
# Colors - More vibrant and distinct palette
COLOR_BACKGROUND = pygame.Color('lightskyblue3') # Brighter, more inviting background
COLOR_TILE_OUTLINE = pygame.Color('gray20')      # Darker outline for better contrast
COLOR_TEXT_DARK = pygame.Color('gray10')         # Very dark grey for text
COLOR_TEXT_LIGHT = pygame.Color('ivory2')        # Off-white for text on dark backgrounds
COLOR_BUTTON_NORMAL = pygame.Color('dodgerblue3')
COLOR_BUTTON_HOVER = pygame.Color('dodgerblue4') # Slightly darker for hover
COLOR_BUTTON_TEXT = COLOR_TEXT_LIGHT
COLOR_ROBBER_FILL = pygame.Color('black')
COLOR_ROBBER_TEXT = pygame.Color('white')
COLOR_PORT_TEXT = pygame.Color('midnightblue')
COLOR_PORT_BG = pygame.Color(220, 220, 220, 200) # Semi-transparent light grey for port text background

# Resource Colors (Vibrant and clear)
COLOR_DICT_RGB = {
    "BRICK": (210, 105, 30),  # Chocolate
    "ORE":   (128, 128, 128), # Gray
    "WHEAT": (255, 215, 0),   # Gold
    "WOOD":  (139, 69, 19),   # SaddleBrown
    "SHEEP": (60, 179, 113),  # MediumSeaGreen
    "DESERT":(245, 222, 179)  # Wheat (for desert color)
}

# Player Resource Panel - Improved Spacing and Look
PLAYER_PANEL_X_MARGIN = 20 # Margin from right edge of the screen
PLAYER_PANEL_Y_START = 20
PLAYER_PANEL_WIDTH = 220 # Slightly wider for more space
PLAYER_PANEL_HEIGHT_PER_PLAYER = 160 # Increased height for more content and spacing
PLAYER_PANEL_SPACING = 15 # Space between player panels
PLAYER_PANEL_BG = pygame.Color(230, 230, 230, 220) # Semi-transparent light grey
PLAYER_PANEL_TEXT_COLOR = COLOR_TEXT_DARK
PLAYER_PANEL_BORDER_THICKNESS = 3
RESOURCE_ICON_SIZE = (22, 22)
RESOURCE_TEXT_OFFSET_X = 5 # Space between icon and text
THOUGHT_BUBBLE_COLOR = pygame.Color(200, 200, 200, 180) # For LLM thoughts

# --- Fonts ---
# Using more common and clear fonts if specific ones aren't found
try:
    FONT_PRIMARY_NAME = 'Arial' # Changed to Arial for wider availability
    FONT_SECONDARY_NAME = 'Calibri' # Changed to Calibri
    FONT_TITLE = pygame.font.SysFont(FONT_PRIMARY_NAME, 30, bold=True)
    FONT_RESOURCE_HEX = pygame.font.SysFont(FONT_PRIMARY_NAME, 15, bold=True) # For hex tile text
    FONT_PORTS = pygame.font.SysFont(FONT_PRIMARY_NAME, 12, italic=True)
    FONT_BUTTON = pygame.font.SysFont(FONT_PRIMARY_NAME, 14, bold=True)
    FONT_DICE_ROLL = pygame.font.SysFont(FONT_PRIMARY_NAME, 32, bold=True) # Larger dice roll
    FONT_ROBBER_SYMBOL = pygame.font.SysFont(FONT_PRIMARY_NAME, 36, bold=True) # For the 'R'
    FONT_PLAYER_NAME = pygame.font.SysFont(FONT_SECONDARY_NAME, 16, bold=True) # For player names in panel
    FONT_PLAYER_DETAILS = pygame.font.SysFont(FONT_SECONDARY_NAME, 13)      # For VP, resources
    FONT_PLAYER_THOUGHTS = pygame.font.SysFont(FONT_SECONDARY_NAME, 11, italic=True) # For LLM thoughts
    FONT_CHAT = pygame.font.SysFont(FONT_SECONDARY_NAME, 12)
    FONT_STATUS = pygame.font.SysFont(FONT_PRIMARY_NAME, 14, bold=True) # For game status like private chat
except pygame.error:
    print("Warning: Preferred fonts (Arial, Calibri) not found, using Pygame default.")
    FONT_PRIMARY_NAME = None
    FONT_SECONDARY_NAME = None
    # Fallback to default SysFont if specific names fail
    FONT_TITLE = pygame.font.SysFont(None, 30, bold=True)
    FONT_RESOURCE_HEX = pygame.font.SysFont(None, 15, bold=True)
    FONT_PORTS = pygame.font.SysFont(None, 12, italic=True)
    FONT_BUTTON = pygame.font.SysFont(None, 14, bold=True)
    FONT_DICE_ROLL = pygame.font.SysFont(None, 32, bold=True)
    FONT_ROBBER_SYMBOL = pygame.font.SysFont(None, 36, bold=True)
    FONT_PLAYER_NAME = pygame.font.SysFont(None, 16, bold=True)
    FONT_PLAYER_DETAILS = pygame.font.SysFont(None, 13)
    FONT_PLAYER_THOUGHTS = pygame.font.SysFont(None, 11, italic=True)
    FONT_CHAT = pygame.font.SysFont(None, 12)
    FONT_STATUS = pygame.font.SysFont(None, 14, bold=True)


#Class to handle catan board display
class catanGameView():
    'Class definition for Catan board display'
    def __init__(self, catanBoardObject, catanGameObject):
        self.board = catanBoardObject
        self.game = catanGameObject

        # Adjust screen size if needed, or ensure board.size is adequate
        self.screen_width = self.board.size[0] if self.board.size[0] >= 1000 else 1000 # Min width for panels
        self.screen_height = self.board.size[1] if self.board.size[1] >= 700 else 700  # Min height
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption('Settlers of Catan - AI Edition')

        # Store fonts in the instance
        self.font_title = FONT_TITLE # Though not explicitly used yet, good to have
        self.font_resource_hex = FONT_RESOURCE_HEX
        self.font_ports = FONT_PORTS
        self.font_button = FONT_BUTTON
        self.font_diceRoll = FONT_DICE_ROLL
        self.font_Robber_symbol = FONT_ROBBER_SYMBOL
        self.font_player_name = FONT_PLAYER_NAME
        self.font_player_details = FONT_PLAYER_DETAILS
        self.font_player_thoughts = FONT_PLAYER_THOUGHTS
        self.font_chat = FONT_CHAT
        self.font_status = FONT_STATUS


        # Placeholder for resource icons (if we decide to load them)
        self.resource_icons = {} # Example: self.resource_icons["WOOD"] = pygame.transform.scale(pygame.image.load("path").convert_alpha(), RESOURCE_ICON_SIZE)
        # self.load_resource_icons()

        return None

    # def load_resource_icons(self):
    #     # Example:
    #     # base_path = "images/" # Assuming an images folder
    #     # for res_type in COLOR_DICT_RGB.keys():
    #     #     if res_type != "DESERT":
    #     #         try:
    #     #             img = pygame.image.load(os.path.join(base_path, f"{res_type.lower()}_icon.png")).convert_alpha()
    #     #             self.resource_icons[res_type] = pygame.transform.smoothscale(img, RESOURCE_ICON_SIZE)
    #     #         except pygame.error:
    #     #             print(f"Warning: Could not load icon for {res_type}")
    #     pass


    #Function to display the initial board (hexes and ports)
    def displayInitialBoard(self):
        self.screen.fill(COLOR_BACKGROUND)

        #Render each hexTile
        for hexTile in self.board.hexTileDict.values():
            hexTileCorners = polygon_corners(self.board.flat, hexTile.hex)
            hexTileColor_rgb = COLOR_DICT_RGB[hexTile.resource.type]

            pygame.draw.polygon(self.screen, pygame.Color(hexTileColor_rgb), hexTileCorners)
            pygame.draw.polygon(self.screen, COLOR_TILE_OUTLINE, hexTileCorners, 3) # Thicker outline

            hexTile.pixelCenter = hex_to_pixel(self.board.flat, hexTile.hex)
            text_color_on_tile = COLOR_TEXT_DARK # Default
            # Potentially adjust text color based on tile color for contrast, e.g., for WOOD
            if hexTile.resource.type in ["WOOD", "BRICK", "ORE"]: # Darker tiles
                 text_color_on_tile = COLOR_TEXT_LIGHT

            if(hexTile.resource.type != 'DESERT'):
                res_type_text = self.font_resource_hex.render(str(hexTile.resource.type), True, text_color_on_tile)
                res_num_text = self.font_resource_hex.render(str(hexTile.resource.num), True, text_color_on_tile) # Number only, no parens

                res_type_rect = res_type_text.get_rect(center=(hexTile.pixelCenter.x, hexTile.pixelCenter.y - 10)) # Adjusted y
                res_num_rect = res_num_text.get_rect(center=(hexTile.pixelCenter.x, hexTile.pixelCenter.y + 10))  # Adjusted y

                self.screen.blit(res_type_text, res_type_rect)
                self.screen.blit(res_num_text, res_num_rect)
            else:
                desert_text = self.font_resource_hex.render("DESERT", True, text_color_on_tile)
                desert_rect = desert_text.get_rect(center=hexTile.pixelCenter)
                self.screen.blit(desert_text, desert_rect)


        #Display the Ports
        for vCoord, vertexInfo in self.board.boardGraph.items():
            if(vertexInfo.port != False):
                portTextSurf = self.font_ports.render(vertexInfo.port, True, COLOR_PORT_TEXT)

                text_x, text_y = vCoord.x, vCoord.y
                # More refined positioning based on relative screen position
                if vCoord.x < self.screen_width * 0.3: text_x -= (portTextSurf.get_width() + 5)
                elif vCoord.x > self.screen_width * 0.6: text_x += 10
                if vCoord.y < self.screen_height * 0.2: text_y -= (portTextSurf.get_height() + 5)
                elif vCoord.y > self.screen_height * 0.7: text_y += 10
                else: # Middle band adjustments
                    if vCoord.x < self.screen_width * 0.3 : text_y -= portTextSurf.get_height() // 2
                    elif vCoord.x > self.screen_width * 0.6 : text_y -= portTextSurf.get_height() // 2


                bg_rect = portTextSurf.get_rect(center=(text_x + portTextSurf.get_width()//2, text_y + portTextSurf.get_height()//2))
                bg_rect.inflate_ip(8, 4) # Padding around text

                # Create a surface for transparency
                port_bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
                port_bg_surface.fill(COLOR_PORT_BG)
                self.screen.blit(port_bg_surface, bg_rect.topleft)
                pygame.draw.rect(self.screen, COLOR_PORT_TEXT, bg_rect, 1, border_radius=3) # Outline for port bg
                self.screen.blit(portTextSurf, (bg_rect.left + 4, bg_rect.top + 2)) # Centered within padded bg
            
        # No pygame.display.update() here, it's called by displayGameScreen


    #Function to draw a road on the board
    def draw_road(self, edgeToDraw, roadColor):
        pygame.draw.line(self.screen, pygame.Color(roadColor), edgeToDraw[0], edgeToDraw[1], 10) # Main road line
        pygame.draw.line(self.screen, COLOR_TILE_OUTLINE, edgeToDraw[0], edgeToDraw[1], 12) # Darker outline for depth


    #Function to draw a potential road on the board - thin
    def draw_possible_road(self, edgeToDraw, roadColor):
        start_pos = edgeToDraw[0]
        end_pos = edgeToDraw[1]
        delta_x = end_pos.x - start_pos.x
        delta_y = end_pos.y - start_pos.y
        distance = max(1, (delta_x**2 + delta_y**2)**0.5) # Avoid division by zero if start=end
        num_dashes = int(distance / 8) # Dash length 4px, gap 4px
        num_dashes = max(1, num_dashes) # Ensure at least one dash segment calculation

        # Create a rect for the entire line for click detection
        min_x = min(start_pos.x, end_pos.x) - 6 # Add padding for click area
        min_y = min(start_pos.y, end_pos.y) - 6
        max_x = max(start_pos.x, end_pos.x) + 6
        max_y = max(start_pos.y, end_pos.y) + 6
        roadRect = pygame.Rect(min_x, min_y, (max_x - min_x), (max_y - min_y))

        # Draw the dashed line for visual
        for i in range(num_dashes):
            if i % 2 == 0: # Draw dash
                 p1 = Point(start_pos.x + (delta_x * i / num_dashes), start_pos.y + (delta_y * i / num_dashes))
                 p2 = Point(start_pos.x + (delta_x * (i+1) / num_dashes), start_pos.y + (delta_y * (i+1) / num_dashes))
                 pygame.draw.line(self.screen, pygame.Color(roadColor).lerp(COLOR_TEXT_LIGHT, 0.3), p1, p2, 5) # Lighter color for possible

        return roadRect


    #Function to draw a settlement on the board at vertexToDraw
    def draw_settlement(self, vertexToDraw, color):
        # Simple house shape: square base, triangular roof
        base_width = 18
        base_height = 12
        roof_height = 10

        # Base rectangle
        base_rect_points = [
            (vertexToDraw.x - base_width // 2, vertexToDraw.y + base_height // 2),
            (vertexToDraw.x + base_width // 2, vertexToDraw.y + base_height // 2),
            (vertexToDraw.x + base_width // 2, vertexToDraw.y - base_height // 2),
            (vertexToDraw.x - base_width // 2, vertexToDraw.y - base_height // 2)
        ]
        pygame.draw.polygon(self.screen, pygame.Color(color), base_rect_points)
        pygame.draw.polygon(self.screen, COLOR_TILE_OUTLINE, base_rect_points, 2)

        # Triangular roof
        roof_points = [
            (vertexToDraw.x - base_width // 2, vertexToDraw.y - base_height // 2),
            (vertexToDraw.x + base_width // 2, vertexToDraw.y - base_height // 2),
            (vertexToDraw.x, vertexToDraw.y - base_height // 2 - roof_height)
        ]
        pygame.draw.polygon(self.screen, pygame.Color(color).lerp(pygame.Color("gray30"), 0.2), roof_points) # Slightly darker roof
        pygame.draw.polygon(self.screen, COLOR_TILE_OUTLINE, roof_points, 2)

   
    #Function to draw a potential settlement on the board - thin
    def draw_possible_settlement(self, vertexToDraw, color):
        # Circle with outline, slightly transparent fill
        radius = 16
        # Create a surface for transparency
        settlement_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(settlement_surf, pygame.Color(color[0], color[1], color[2], 150), (radius, radius), radius) # Player color, semi-transparent

        self.screen.blit(settlement_surf, (int(vertexToDraw.x) - radius, int(vertexToDraw.y) - radius))
        pygame.draw.circle(self.screen, COLOR_TILE_OUTLINE, (int(vertexToDraw.x), int(vertexToDraw.y)), radius, 2) # Outline
        return pygame.Rect(int(vertexToDraw.x) - radius, int(vertexToDraw.y) - radius, radius*2, radius*2)

    
    #Function to draw a city on the board at vertexToDraw
    def draw_city(self, vertexToDraw, color):
        # More complex shape for city: e.g., a larger base with a smaller "tower"
        main_building_w = 24
        main_building_h = 18
        tower_w = 12
        tower_h = 10 # Additional height for tower part

        # Main building part (larger rectangle)
        main_points = [
            (vertexToDraw.x - main_building_w // 2, vertexToDraw.y + main_building_h // 2),
            (vertexToDraw.x + main_building_w // 2, vertexToDraw.y + main_building_h // 2),
            (vertexToDraw.x + main_building_w // 2, vertexToDraw.y - main_building_h // 2),
            (vertexToDraw.x - main_building_w // 2, vertexToDraw.y - main_building_h // 2)
        ]
        pygame.draw.polygon(self.screen, pygame.Color(color), main_points)
        pygame.draw.polygon(self.screen, COLOR_TILE_OUTLINE, main_points, 2)

        # "Tower" part (smaller rectangle on top, slightly offset or centered)
        tower_points = [
            (vertexToDraw.x - tower_w // 2, vertexToDraw.y - main_building_h // 2), # Starts from top of main building
            (vertexToDraw.x + tower_w // 2, vertexToDraw.y - main_building_h // 2),
            (vertexToDraw.x + tower_w // 2, vertexToDraw.y - main_building_h // 2 - tower_h),
            (vertexToDraw.x - tower_w // 2, vertexToDraw.y - main_building_h // 2 - tower_h)
        ]
        pygame.draw.polygon(self.screen, pygame.Color(color).lerp(pygame.Color("gray30"), 0.3), tower_points) # Slightly different shade
        pygame.draw.polygon(self.screen, COLOR_TILE_OUTLINE, tower_points, 2)

   
    #Function to draw a potential city on the board - thin
    def draw_possible_city(self, vertexToDraw, color):
        # Larger circle, distinct from settlement, perhaps a square/diamond outline
        radius = 20
        # Create a surface for transparency
        city_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(city_surf, pygame.Color(color[0],color[1],color[2],180), (radius, radius), radius) # Darker/more opaque than settlement

        self.screen.blit(city_surf, (int(vertexToDraw.x) - radius, int(vertexToDraw.y) - radius))
        pygame.draw.circle(self.screen, COLOR_TILE_OUTLINE, (int(vertexToDraw.x), int(vertexToDraw.y)), radius, 3) # Thicker outline
        # Add a small inner circle or symbol to differentiate
        pygame.draw.circle(self.screen, COLOR_TEXT_LIGHT, (int(vertexToDraw.x), int(vertexToDraw.y)), radius // 3, 0)
        return pygame.Rect(int(vertexToDraw.x) - radius, int(vertexToDraw.y) - radius, radius*2, radius*2)

    
    #Function to draw the possible spots for a robber
    def draw_possible_robber(self, vertexToDraw): # vertexToDraw is hex center
        radius = 40 # Slightly smaller than hex half-width for better fit
        s = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (50, 50, 50, 120), (radius, radius), radius) # Dark grey, semi-transparent
        self.screen.blit(s, (int(vertexToDraw.x)-radius, int(vertexToDraw.y)-radius))
        return pygame.Rect(int(vertexToDraw.x)-radius, int(vertexToDraw.y)-radius, radius*2, radius*2)


    #Function to draw possible players to rob
    def draw_possible_players_to_rob(self, vertexCoord): # vertexCoord is player's settlement/city center
        # Draw a targeting reticle or highlight around the building
        radius = 25 # Radius of highlight
        pygame.draw.circle(self.screen, pygame.Color('red'), (int(vertexCoord.x), int(vertexCoord.y)), radius, 3) # Red circle outline
        # Small lines for a "target" look
        pygame.draw.line(self.screen, pygame.Color('red'), (int(vertexCoord.x) - radius - 5, int(vertexCoord.y)), (int(vertexCoord.x) - radius + 5, int(vertexCoord.y)), 2)
        pygame.draw.line(self.screen, pygame.Color('red'), (int(vertexCoord.x) + radius - 5, int(vertexCoord.y)), (int(vertexCoord.x) + radius + 5, int(vertexCoord.y)), 2)
        pygame.draw.line(self.screen, pygame.Color('red'), (int(vertexCoord.x), int(vertexCoord.y) - radius - 5), (int(vertexCoord.x), int(vertexCoord.y) - radius + 5), 2)
        pygame.draw.line(self.screen, pygame.Color('red'), (int(vertexCoord.x), int(vertexCoord.y) + radius - 5), (int(vertexCoord.x), int(vertexCoord.y) + radius + 5), 2)
        return pygame.Rect(int(vertexCoord.x) - radius, int(vertexCoord.y) - radius, radius*2, radius*2)
        

    #Function to render basic gameplay buttons
    def displayGameButtons(self):
        button_height = 40 # Slightly taller buttons
        button_width_short = 110 # Wider short buttons
        button_width_long = 150  # Wider long buttons
        padding_vertical = 12    # Increased vertical padding
        padding_horizontal = 15  # Horizontal padding from edge
        start_x = padding_horizontal
        start_y = padding_vertical + 20 # Start a bit lower to avoid screen top edge

        # Group buttons for better organization if many
        buttons_config = [
            {"text": "ROLL DICE", "id": "rollDice", "rect_pos": (start_x, start_y), "size": (button_width_short, button_height), "color": pygame.Color('springgreen4')},
            {"text": "ROAD", "id": "buildRoad", "rect_pos": (start_x, start_y + button_height + padding_vertical), "size": (button_width_short, button_height), "color": COLOR_BUTTON_NORMAL},
            {"text": "SETTLE", "id": "buildSettlement", "rect_pos": (start_x, start_y + 2*(button_height + padding_vertical)), "size": (button_width_short, button_height), "color": COLOR_BUTTON_NORMAL},
            {"text": "CITY", "id": "buildCity", "rect_pos": (start_x, start_y + 3*(button_height + padding_vertical)), "size": (button_width_short, button_height), "color": COLOR_BUTTON_NORMAL},

            # Second column or further down for other actions
            {"text": "BUY DEV CARD", "id": "devCard", "rect_pos": (start_x, start_y + 5*(button_height + padding_vertical)), "size": (button_width_long, button_height), "color": pygame.Color('gold3')},
            {"text": "PLAY DEV CARD", "id": "playDevCard", "rect_pos": (start_x, start_y + 6*(button_height + padding_vertical)), "size": (button_width_long, button_height), "color": pygame.Color('darkgoldenrod3')},

            {"text": "TRADE BANK", "id": "tradeBank", "rect_pos": (start_x, start_y + 8*(button_height + padding_vertical)), "size": (button_width_long, button_height), "color": pygame.Color('mediumorchid3')},
            {"text": "TRADE PLAYER", "id": "tradePlayers", "rect_pos": (start_x, start_y + 9*(button_height + padding_vertical)), "size": (button_width_long, button_height), "color": pygame.Color('mediumorchid4')},

            {"text": "END TURN", "id": "endTurn", "rect_pos": (start_x, self.screen_height - button_height - padding_vertical - 60), "size": (button_width_short, button_height), "color": pygame.Color('firebrick3')},
        ]

        mouse_pos = pygame.mouse.get_pos()

        for btn_data in buttons_config:
            btn_rect = pygame.Rect(btn_data["rect_pos"], btn_data["size"])
            setattr(self, f"{btn_data['id']}_button", btn_rect) # Store rect on self

            current_color = btn_data["color"]
            if btn_rect.collidepoint(mouse_pos):
                # Darken color on hover (simple hover effect)
                current_color = btn_data["color"].lerp(COLOR_BUTTON_HOVER, 0.2) # More subtle hover

            pygame.draw.rect(self.screen, current_color, btn_rect, border_radius=8) # Rounded corners
            pygame.draw.rect(self.screen, COLOR_TEXT_DARK.lerp(pygame.Color("white"), 0.8), btn_rect, 2, border_radius=8) # Softer outline

            text_surf = self.font_button.render(btn_data["text"], True, COLOR_BUTTON_TEXT)
            text_rect = text_surf.get_rect(center=btn_rect.center)
            self.screen.blit(text_surf, text_rect)


    #Function to display robber
    def displayRobber(self):
        robberText = self.font_Robber_symbol.render("R", True, COLOR_ROBBER_TEXT) # Text on robber
        for hexTile in self.board.hexTileDict.values():
            if(hexTile.robber):
                robberCoords = hexTile.pixelCenter
                # Draw a more prominent robber: larger circle, outline
                pygame.draw.circle(self.screen, COLOR_ROBBER_FILL, (int(robberCoords.x), int(robberCoords.y)), 22)
                pygame.draw.circle(self.screen, COLOR_TEXT_LIGHT, (int(robberCoords.x), int(robberCoords.y)), 22, 2) # Light outline
                text_rect = robberText.get_rect(center=(int(robberCoords.x), int(robberCoords.y)))
                self.screen.blit(robberText, text_rect)
                break


    def displayPlayerResources(self):
        panel_x = self.screen_width - PLAYER_PANEL_WIDTH - PLAYER_PANEL_X_MARGIN

        for i, player_i in enumerate(list(self.game.playerQueue.queue)):
            panel_y = PLAYER_PANEL_Y_START + i * (PLAYER_PANEL_HEIGHT_PER_PLAYER + PLAYER_PANEL_SPACING)
            player_panel_rect = pygame.Rect(panel_x, panel_y, PLAYER_PANEL_WIDTH, PLAYER_PANEL_HEIGHT_PER_PLAYER)

            # Semi-transparent background for the panel
            panel_surf = pygame.Surface(player_panel_rect.size, pygame.SRCALPHA)
            panel_surf.fill(PLAYER_PANEL_BG)
            self.screen.blit(panel_surf, player_panel_rect.topleft)
            pygame.draw.rect(self.screen, pygame.Color(player_i.color), player_panel_rect, PLAYER_PANEL_BORDER_THICKNESS, border_radius=8) # Border with player color

            text_x_start = player_panel_rect.left + 15 # Indent text
            text_y_offset = player_panel_rect.top + 10

            # Player Name and VP
            name_surf = self.font_player_name.render(f"{player_i.name}", True, PLAYER_PANEL_TEXT_COLOR)
            self.screen.blit(name_surf, (text_x_start, text_y_offset))
            vp_surf = self.font_player_details.render(f"VP: {player_i.victoryPoints}", True, PLAYER_PANEL_TEXT_COLOR)
            vp_rect = vp_surf.get_rect(topright=(player_panel_rect.right - 15, text_y_offset + 2))
            self.screen.blit(vp_surf, vp_rect)
            text_y_offset += name_surf.get_height() + 8 # More space after name

            # Resources
            res_order = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]
            res_y_start = text_y_offset
            for res_idx, res_name in enumerate(res_order):
                res_count = player_i.resources.get(res_name, 0)
                current_res_y = res_y_start + res_idx * (RESOURCE_ICON_SIZE[1] + 4) # Vertical spacing for resources

                # Attempt to use resource icons if available
                if res_name in self.resource_icons:
                    icon_rect = self.resource_icons[res_name].get_rect(topleft=(text_x_start, current_res_y))
                    self.screen.blit(self.resource_icons[res_name], icon_rect)
                    count_surf = self.font_player_details.render(f": {res_count}", True, PLAYER_PANEL_TEXT_COLOR)
                    self.screen.blit(count_surf, (icon_rect.right + RESOURCE_TEXT_OFFSET_X, current_res_y + (RESOURCE_ICON_SIZE[1] - count_surf.get_height()) // 2))
                else: # Fallback to text only
                    res_surf = self.font_player_details.render(f"{res_name}: {res_count}", True, PLAYER_PANEL_TEXT_COLOR)
                    self.screen.blit(res_surf, (text_x_start, current_res_y))
            text_y_offset = res_y_start + len(res_order) * (RESOURCE_ICON_SIZE[1] + 4) + 5


            # LLM Thoughts (if applicable) - Improved Display
            if isinstance(player_i, LLMPlayer) and hasattr(player_i, 'thoughts') and player_i.thoughts:
                max_thought_width = player_panel_rect.width - 30 # Max width for thought text

                # Wrap text for thoughts
                words = player_i.thoughts.split(' ')
                lines = []
                current_line = ""
                for word in words:
                    test_line = current_line + word + " "
                    if self.font_player_thoughts.size(test_line)[0] <= max_thought_width:
                        current_line = test_line
                    else:
                        lines.append(current_line.strip())
                        current_line = word + " "
                lines.append(current_line.strip())

                # Display up to 2 lines of thoughts
                displayed_lines = lines[:2]
                if len(lines) > 2:
                    displayed_lines[-1] += "..."

                if displayed_lines:
                    thought_label_surf = self.font_player_thoughts.render("Thinking:", True, PLAYER_PANEL_TEXT_COLOR)
                    self.screen.blit(thought_label_surf, (text_x_start, text_y_offset))
                    text_y_offset += thought_label_surf.get_height()

                    for line_idx, line_text in enumerate(displayed_lines):
                        thought_surf = self.font_player_thoughts.render(line_text, True, PLAYER_PANEL_TEXT_COLOR)
                        self.screen.blit(thought_surf, (text_x_start + 5, text_y_offset)) # Indent thought text
                        text_y_offset += thought_surf.get_height()


    #Function to display the gameState board - use to display intermediate build screens
    def displayGameScreen(self):
        self.displayInitialBoard()

        for player_i in list(self.game.playerQueue.queue):
            for existingRoad in player_i.buildGraph['ROADS']:
                self.draw_road(existingRoad, player_i.color)
            for settlementCoord in player_i.buildGraph['SETTLEMENTS']:
                self.draw_settlement(settlementCoord, player_i.color)
            for cityCoord in player_i.buildGraph['CITIES']:
                self.draw_city(cityCoord, player_i.color)

        self.displayRobber()
        self.displayGameButtons()
        self.displayPlayerResources()

        # Display Global Chat History - Enhanced
        chat_area_width = self.screen_width - PLAYER_PANEL_WIDTH - PLAYER_PANEL_X_MARGIN - 180 # Adjust width based on other elements
        chat_area_height = 120 # Fixed height for chat box
        chat_base_x = 160 # X position of chat box (left of player panels)
        chat_base_y = self.screen_height - chat_area_height - 20 # Position above bottom edge
        chat_line_height = self.font_chat.get_linesize()
        chat_padding = 8
        chat_max_lines = (chat_area_height - 2 * chat_padding) // chat_line_height

        chat_history_to_display = self.game.global_chat_history[-chat_max_lines:] # Get last N messages that fit
        if chat_history_to_display:
            # Semi-transparent background for chat
            chat_bg_rect = pygame.Rect(chat_base_x - chat_padding, chat_base_y - chat_padding,
                                      chat_area_width + 2 * chat_padding, chat_area_height + 2 * chat_padding)
            chat_bg_surf = pygame.Surface(chat_bg_rect.size, pygame.SRCALPHA)
            chat_bg_surf.fill((30, 30, 30, 200)) # Darker, more transparent
            self.screen.blit(chat_bg_surf, chat_bg_rect.topleft)
            pygame.draw.rect(self.screen, COLOR_TEXT_LIGHT, chat_bg_rect, 1, border_radius=5) # Light outline

            for idx, chat_entry in enumerate(chat_history_to_display):
                player_name = chat_entry.get("player", "System")
                message = chat_entry.get("message", "")
                # Truncate long messages
                max_msg_width = chat_area_width - self.font_chat.size(f"[{player_name}]: ")[0] - 5 # Width for message part

                available_width = chat_area_width
                full_prefix = f"[{player_name}]: "
                prefix_width = self.font_chat.size(full_prefix)[0]

                truncated_message = message
                while self.font_chat.size(full_prefix + truncated_message)[0] > available_width - 5 and len(truncated_message) > 0: # 5 for small margin
                    truncated_message = truncated_message[:-1]
                if len(truncated_message) < len(message):
                    truncated_message += "..."

                chat_text_surface = self.font_chat.render(f"{full_prefix}{truncated_message}", True, COLOR_TEXT_LIGHT)
                self.screen.blit(chat_text_surface, (chat_base_x, chat_base_y + (idx * chat_line_height)))

        # Display Private Chat Status - Centered at top
        if hasattr(self.game, 'active_private_chat_participants') and self.game.active_private_chat_participants:
            p1_name, p2_name = self.game.active_private_chat_participants
            status_text = f"Private Chat Active: {p1_name} & {p2_name}"
            status_surface = self.font_status.render(status_text, True, pygame.Color('gold2'))

            status_bg_rect = status_surface.get_rect(centerx=self.screen_width // 2, top=10)
            status_bg_rect.inflate_ip(20, 10) # Padding for background

            pygame.draw.rect(self.screen, pygame.Color(0,0,0,180), status_bg_rect, border_radius=5) # Dark semi-transparent BG
            self.screen.blit(status_surface, status_surface.get_rect(center=status_bg_rect.center))


        pygame.display.flip()
        return


    #Function to display dice roll
    def displayDiceRoll(self, diceNums):
        dice_display_text = str(diceNums)
        diceNumText = self.font_diceRoll.render(dice_display_text, True, COLOR_TEXT_DARK)
        
        # Position it more visibly, e.g., near the center top, but below private chat status
        text_rect = diceNumText.get_rect(centerx=self.screen_width // 2, top=50)

        # Clear previous roll with a small background area
        bg_rect = text_rect.inflate(20, 10) # Add padding for the background
        pygame.draw.rect(self.screen, COLOR_BACKGROUND.lerp(pygame.Color("white"), 0.1), bg_rect, border_radius=5) # Slightly lighter bg
        pygame.draw.rect(self.screen, COLOR_TEXT_DARK, bg_rect, 1, border_radius=5) # Outline for the dice area

        self.screen.blit(diceNumText, text_rect)
        # Full flip is preferred, so displayGameScreen or other callers will handle it.
        # If this needs to update independently, then pygame.display.update(bg_rect) would be used.


    def buildRoad_display(self, currentPlayer, roadsPossibleDict):
        # Clear previous drawings in the areas of possible roads if needed, or rely on full redraw
        # self.displayGameScreen() # Redraw base screen first to clear old highlights

        for roadEdge in roadsPossibleDict.keys():
            if roadsPossibleDict[roadEdge]:
                roadsPossibleDict[roadEdge] = self.draw_possible_road(roadEdge, currentPlayer.color)

        pygame.display.flip()

        mouseClicked = False
        while(mouseClicked == False):
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.MOUSEBUTTONDOWN:
                    for road, roadRect in roadsPossibleDict.items():
                        if roadRect and roadRect.collidepoint(e.pos):
                            return road
                    if not self.game.gameSetup: # Allow cancelling if not setup phase
                        return None # Clicked outside any possible road

            if self.game.gameSetup and not mouseClicked:
                pygame.time.wait(20) # Slightly longer wait, less CPU intensive
                        

    def buildSettlement_display(self, currentPlayer, verticesPossibleDict):
        # self.displayGameScreen() # Redraw base

        for v in verticesPossibleDict.keys():
            if verticesPossibleDict[v]:
                verticesPossibleDict[v] = self.draw_possible_settlement(v, currentPlayer.color)

        pygame.display.flip()

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
                        return None

            if self.game.gameSetup and not mouseClicked:
                pygame.time.wait(20)


    def buildCity_display(self, currentPlayer, verticesPossibleDict):
        # self.displayGameScreen() # Redraw base

        for c_vertex_coord in verticesPossibleDict.keys(): # Key is the vertex coordinate
            # The value in verticesPossibleDict is initially True, then becomes the Rect
            if verticesPossibleDict[c_vertex_coord]:
                verticesPossibleDict[c_vertex_coord] = self.draw_possible_city(c_vertex_coord, currentPlayer.color)

        pygame.display.flip()

        mouseClicked = False
        while(mouseClicked == False):
            for e in pygame.event.get(): 
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.MOUSEBUTTONDOWN:
                    for vertex_coord, cityRect in verticesPossibleDict.items():
                        if cityRect and cityRect.collidepoint(e.pos):
                            return vertex_coord # Return the coordinate
                    return None # Clicked somewhere else, implies cancel

            pygame.time.wait(20)

    #Function to control the move-robber action with display
    def moveRobber_display(self, currentPlayer, possibleRobberDict_Hexes):
        # self.displayGameScreen() # Redraw base

        clickable_robber_hex_rects = {} # hexIndex: Rect
        for hexIndex, hexTileObj in possibleRobberDict_Hexes.items():
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
                            # Original line: possiblePlayerDict_Victims = self.board.get_players_to_rob(hexIndex)
                            # This get_players_to_rob needs to return a dictionary of {playerObj: vertexCoord_of_their_building_on_hex}
                            # Assuming that method is correctly implemented in board.py
                            possiblePlayerDict_Victims = self.board.get_players_to_rob(hexIndex, currentPlayer) # Pass current player to exclude self

                            playerToRob = self.choosePlayerToRob_display(possiblePlayerDict_Victims)
                            return hexIndex, playerToRob # Return selected hex and player (or None)
            pygame.time.wait(20)

    
    #Function to control the choice of player to rob with display
    def choosePlayerToRob_display(self, possiblePlayerDict_Victims):
        if not possiblePlayerDict_Victims:
            return None

        # self.displayGameScreen() # Redraw base, then highlight options

        clickable_victim_rects = {} # playerObj: Rect
        for playerObj, vertexCoord_of_building in possiblePlayerDict_Victims.items():
            clickable_victim_rects[playerObj] = self.draw_possible_players_to_rob(vertexCoord_of_building)

        pygame.display.flip()

        mouseClicked = False
        while(mouseClicked == False):
            for e in pygame.event.get(): 
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if(e.type == pygame.MOUSEBUTTONDOWN):
                    # Check if "No Rob" option was clicked (if implemented)
                    # no_rob_button_rect = getattr(self, "no_rob_button", None) # Example
                    # if no_rob_button_rect and no_rob_button_rect.collidepoint(e.pos):
                    #     return None

                    for playerToRob, playerCircleRect in clickable_victim_rects.items():
                        if(playerCircleRect.collidepoint(e.pos)): 
                            return playerToRob
                    # If click wasn't on a victim, and no "No Rob" button, assume re-click on hex or no valid choice.
                    # Depending on game flow, might want to return None here to indicate no choice made / cancel.
                    # For now, loop continues until a valid victim is clicked.
            pygame.time.wait(20)
