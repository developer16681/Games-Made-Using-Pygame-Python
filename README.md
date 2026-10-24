# 🎮 Games Made Using Pygame & Python 🕹️

A curated collection of standalone 2D and 3D arcade games built using **Python**, **Pygame**, and **Ursina Engine**, developed with the assistance of **Claude AI**.

Every game in this collection is designed to run self-contained with minimal setup. Most games synthesize their sound effects and chiptune music procedurally in-code or run directly out of the box with zero external asset dependencies!

---

## 📑 Included Games

| Game | Engine / Libs | Dimension | Key Features | Run Command |
| :--- | :--- | :--- | :--- | :--- |
| **[Chess](Pygame/Chess/chess.py)** | Pygame | 2D | Mini-max AI opponent, 3 difficulty levels, procedural sounds & chiptune BGM, move undo, board flip. | `python "Pygame/Chess/chess.py"` |
| **[Crystal Arena](<Pygame/Crystal Arena/crystal_arena.py>)** | Ursina, NumPy | 3D | Fast-paced first-person arena shooter, procedural wave audio, dynamic lighting & shadows. | `python "Pygame/Crystal Arena/crystal_arena.py"` |
| **[Forest Game](<Pygame/Forest Game/forest_game.py>)** | Ursina | 3D | 3D first-person exploration and survival with weapon mechanics and procedural sound generation. | `python "Pygame/Forest Game/forest_game.py"` |
| **[Neon Drift](Pygame/Neon_Drift/neon_drift%20(1).py)** | Ursina, NumPy | 3D | Retro-synthwave 3D space racer with procedural audio synthesis and boost mechanics. | `python "Pygame/Neon_Drift/neon_drift (1).py"` |
| **[Pacman](<Pygame/Pacman/pacman (1).py>)** | Pygame | 2D | Classic arcade Pac-Man with neon glow effects, ghost pathfinding AI, and procedural audio. | `python "Pygame/Pacman/pacman (1).py"` |
| **[Neon Snake](<Pygame/Snake Game/Snake_Claude.py>)** | Pygame | 2D | Polished Snake game featuring particle effects, high-score tracking, and chiptune music. | `python "Pygame/Snake Game/Snake_Claude.py"` |
| **[Sweet Crush](Pygame/Sweet_Crush/sweet_crush.py)** | Pygame | 2D | Match-3 candy puzzle game with animated combos and in-code audio synthesis. | `python "Pygame/Sweet_Crush/sweet_crush.py"` |
| **[Tic Tac Toe](<Pygame/Tic Tac Toe/Tic_Tac_Toe.py>)** | Pygame | 2D | Unbeatable Minimax AI & 2-player modes, confetti celebration effects, and clean UI. | `python "Pygame/Tic Tac Toe/Tic_Tac_Toe.py"` |
| **[Turbo Rush](<Pygame/Turbo Rush/turbo_rush.py>)** | Pygame | 2D | Top-down traffic racer with nitro boosting, coin collection, and procedural audio. | `python "Pygame/Turbo Rush/turbo_rush.py"` |

---

## ✨ Highlights

- 🤖 **AI-Assisted Craftsmanship**: Gameplay logic, particle systems, procedural audio math, and UI crafted with Claude AI.
- 🔊 **Zero-Asset Audio Synthesis**: Many games synthesize their own chiptune tracks, SFX, and wave files at runtime using Python standard libraries (`math`, `wave`, `array`, `struct`).
- ⚡ **Plug-and-Play**: No bulky binary assets or complex setups required. Clone and play!
- 🎨 **Visual Polish**: Features retro aesthetics, neon glow palettes, smooth particle physics, and responsive controls.

---

## 🛠️ Prerequisites & Installation

### 1. Requirements
Ensure you have **Python 3.8+** installed on your system.

### 2. Install Dependencies
Install the required libraries for 2D (Pygame) and 3D (Ursina & NumPy) games:

```bash
# For 2D games (Chess, Pacman, Snake, Sweet Crush, Tic Tac Toe, Turbo Rush)
pip install pygame

# For 3D games (Crystal Arena, Forest Game, Neon Drift)
pip install ursina numpy
```

---

## 🚀 How to Play

### 1. Clone the Repository
```bash
git clone https://github.com/developer16681/Games-made-using-Pygame.git
cd Games-made-using-Pygame
```

### 2. Launch Any Game
Navigate to the game directory or launch directly using python:

```bash
# Example: Launching Pacman
python "Pygame/Pacman/pacman (1).py"

# Example: Launching Neon Snake
python "Pygame/Snake Game/Snake_Claude.py"

# Example: Launching Crystal Arena (3D)
python "Pygame/Crystal Arena/crystal_arena.py"

# Example: Launching Chess
python "Pygame/Chess/chess.py"
```

---

## 🎮 General Controls

| Game | Typical Controls |
| :--- | :--- |
| **2D Arcade / Driving** | <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> or Arrow Keys to steer/move, <kbd>Space</kbd> for Action/Nitro, <kbd>P</kbd> to Pause, <kbd>M</kbd> to Mute |
| **3D Action / FPS** | <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> to move, Mouse to look, Left Click to shoot, <kbd>Space</kbd> to jump |
| **Board / Puzzle** | Mouse Left Click / Drag to interact, <kbd>R</kbd> to restart, <kbd>Esc</kbd> to exit |

---

## 🤝 Contributing & Experiments

Want to add new mechanics, tweak game AI, or add more procedural audio?
Feel free to fork the repository, make improvements, experiment with AI prompts, and submit a pull request!

---

*Enjoy playing and exploring these games!* 🕹️✨
