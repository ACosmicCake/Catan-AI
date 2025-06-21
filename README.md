# Settlers of Catan - AI Arena

## Overview

This project is an adaptation of a Settlers of Catan framework, originally built in Python with a focus on Reinforcement Learning agents. It has been significantly modified to serve as an "AI Arena" where multiple AI players, including Large Language Models (LLMs) and heuristic-based AIs, can play against each other.

The game features a GUI implemented using Pygame, and the current primary mode of play involves AI-only games, showcasing the decision-making processes of different AI agents, including the "thoughts" of LLM players.

![Catan Board](/images/catan_gui.png)

## Features

*   **Play Settlers of Catan:** Core game mechanics implemented.
*   **Multiple AI Player Types:**
    *   **LLM Players:** Supports ChatGPT, Gemini, Claude, and Deepseek models as players (requires API keys).
    *   **Heuristic AI:** A pre-existing heuristic-based AI player.
*   **Selectable AI for Each Slot:** Users can choose the type of AI (any of the four LLMs or the Heuristic AI) for each player slot in a game (3 or 4 players). This allows for diverse matchups like LLM vs. LLM, LLM vs. Heuristic, or all Heuristic AI games.
*   **LLM Thought Display:** The reasoning or "thoughts" provided by LLM players during their turn are displayed in the GUI, offering insights into their decision-making.
*   **AI vs. AI Gameplay:** The primary focus is on `AIGame.py` for AI-only matches.

## Requirements

*   Python 3.7+
*   For a full list of Python package dependencies, please see `requirements.txt`.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```
    (Replace `<repository_url>` and `<repository_directory>` with actual values if known, otherwise leave as placeholders for the user to fill in.)

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    Install all necessary packages using the `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

4.  **API Key Configuration (for LLM Players):**
    To use the LLM players, you need to provide API keys for the respective services (OpenAI, Google AI Studio, Anthropic, Deepseek).
    *   Create a file named `.env` in the root directory of the project.
    *   Add your API keys to this file in the following format:
        ```env
        OPENAI_API_KEY="your-openai-api-key"
        GEMINI_API_KEY="your-gemini-api-key"
        CLAUDE_API_KEY="your-claude-api-key"
        DEEPSEEK_API_KEY="your-deepseek-api-key"
        ```
    *   The project uses `python-dotenv` (listed in `requirements.txt`) to load these keys from the `.env` file automatically when the application starts.

## How to Run the Game

1.  **Navigate to the Code Directory:**
    Ensure your terminal is in the project's root directory. The main game script is within the `code` subdirectory.

2.  **Run `AIGame.py`:**
    This script launches a game exclusively for AI players.
    ```bash
    python code/AIGame.py
    ```

3.  **Initial Prompts:**
    *   **Number of Players:** The game will first ask you to "Enter Number of Players (3 or 4):".
    *   **AI Type Selection:** For each player slot, you will be prompted to choose the type of AI. A list of available LLMs and the Heuristic AI will be displayed with corresponding numbers. Enter the number for your desired AI for each player.

    Example of AI Type Selection Prompt:
    ```
    Choose AI type for Player 1:
      1: ChatGPT (LLM)
      2: Gemini (LLM)
      3: Claude (LLM)
      4: Deepseek (LLM)
      5: Heuristic AI
    Enter choice (1-5):
    ```

4.  **Gameplay:**
    *   The game will proceed with the initial setup phase, where selected AIs will place their first settlements and roads.
    *   During gameplay, if LLM players are active, their "thoughts" (reasoning for their moves) will be displayed on the right side of the game screen.

## Framework Overview (Core Modules)

The game's functionality is primarily structured around the following modules located in the `code/` directory:

*   `hexTile.py` & `hexLib.py`: Manage the hexagonal board tiles and associated geometry.
*   `board.py`: Implements the game board logic, including building actions.
*   `player.py`: Base class for all player functionalities.
*   `heuristicAIPlayer.py`: Implements the logic for the heuristic-based AI.
*   `LLMPlayer.py`: New class that interfaces with LLM APIs to enable them as players. It constructs prompts, (currently) simulates LLM responses, and extracts actions and thoughts.
*   `modelState.py`: Generates a comprehensive JSON representation of the current game state, which is provided to the LLM players.
*   `AIGame.py`: Manages the game flow for AI vs. AI matches, including player setup and turn progression. This is the primary script to run for the AI Arena.
*   `gameView.py`: Handles the Pygame-based GUI, including rendering the board, pieces, and LLM thoughts.
*   (`catanGame.py`: Originally for mixed human/AI games, less focus in current LLM Arena setup).

## License

This project includes a `LICENSE` file (MIT License). Please refer to it for details.
