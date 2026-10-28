"""A cozy little fox platformer built with Tkinter.

Run with: python fox_campfire.py
"""

import math
from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont

WIDTH = 960
HEIGHT = 600
GROUND_Y = 500
PLAYER_WIDTH = 34
PLAYER_HEIGHT = 34
PLAYER_HALF_WIDTH = PLAYER_WIDTH / 2
MICHAEL_JACKSON_MODE = False  # if True, the fox moonwalks instead of walking normally


class CozyFoxGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Little Fox by the Campfire")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#17243a", highlightthickness=0)
        self.canvas.pack()

        self.michael_jackson_mode = bool(MICHAEL_JACKSON_MODE)
        self.config_michael_jackson_mode = bool(MICHAEL_JACKSON_MODE)

        sprite_dir = Path(__file__).resolve().parent
        sprite_folders = [
            sprite_dir / "fox_sprites",
            sprite_dir / "fox_sprites" / "fox_sprites",
        ]

        def load_sprite(action: str, index: int, flipped: bool = False) -> tk.PhotoImage:
            suffix = "_flipped" if flipped else ""
            for folder in sprite_folders:
                candidates = [
                    folder / f"{action}_{index}{suffix}.png",
                    folder / f"{action}_{index}.png",
                ]
                for candidate in candidates:
                    if candidate.exists():
                        return tk.PhotoImage(master=root, file=str(candidate))
            return tk.PhotoImage(master=root, file=str(sprite_folders[0] / f"{action}_{index}{suffix}.png"))

        self.sprite_frames = {
            action: [
                load_sprite(action, index)
                for index in range(count)
            ]
            for action, count in (
                ("walk_left", 5),
                ("walk_right", 4),
                ("jump_left", 4),
                ("jump_right", 6),
            )
        }
        if MICHAEL_JACKSON_MODE:
            self.flipped_sprite_frames = {}
        else:
            self.flipped_sprite_frames = {
                action: [
                    load_sprite(action, index, flipped=True)
                    for index in range(count)
                ]
                for action, count in (
                    ("walk_left", 5),
                    ("walk_right", 4),
                    ("jump_left", 4),
                    ("jump_right", 6),
                )
            }

        self.frame = 0
        self.keys: set[str] = set()
        self.state = "start"
        self.menu_index = 0
        self.config_index = 0
        self.config_return_state = "start"
        self.level_select_index = 0
        self.scroll_offset = 0
        self.completed_levels: set[int] = set()
        self.levels = self.build_levels()

        self.current_level_index = 0
        self.current_level = self.levels[0]
        self.player_x = float(self.current_level["start_x"])
        self.player_y = float(self.current_level["start_y"])
        self.velocity_y = 0.0
        self.facing = 1
        self.on_ground = True
        self.camera_x = 0.0
        self.checkpoint_x = self.player_x
        self.enemies: list[dict] = []

        self._load_level(0, keep_selection=True)

        self.root.bind("<KeyPress>", self.on_key_down)
        self.root.bind("<KeyRelease>", self.on_key_up)
        self.root.focus_set()
        self.tick()

    def build_levels(self) -> list[dict]:
        def make_checkpoints(start_x: float, goal_x: float, count: int = 20) -> tuple[float, ...]:
            if count <= 1:
                return (float(start_x),)
            return tuple(float(start_x + (goal_x - start_x) * i / (count - 1)) for i in range(count))

        def sanitize_hazards(level: dict) -> tuple[tuple[float, float], ...]:
            ground_and_platforms = list(level["ground_segments"]) + [
                (x, x + width) for x, _, width in level["platforms"]
            ]
            fixed = []
            for hazard_x, hazard_width in level["hazards"]:
                left = float(hazard_x)
                right = left + float(hazard_width)
                valid = any(left < end and right > start for start, end in ground_and_platforms)
                if valid:
                    fixed.append((float(hazard_x), float(hazard_width)))
                    continue

                # Snap invalid spikes onto the closest usable surface so they never sit in a gap.
                best_segment = None
                best_distance = None
                for start, end in ground_and_platforms:
                    center = (start + end) / 2.0
                    distance = abs(center - left)
                    if best_distance is None or distance < best_distance:
                        best_distance = distance
                        best_segment = (start, end)

                if best_segment is None:
                    continue
                start, end = best_segment
                snapped_left = min(max(start + 2, left), max(start, end - hazard_width))
                fixed.append((float(snapped_left), float(hazard_width)))
            return tuple(fixed)

        level_specs = [
            {
                "name": "Campfire Trail",
                "world_width": 1800,
                "goal_offset": 130,
                "ground_segments": ((0, 350), (470, 710), (860, 1125), (1255, 1800)),
                "platforms": ((210, 420, 90), (520, 360, 100), (730, 300, 90), (940, 340, 100), (1170, 305, 100), (1380, 345, 115)),
                "hazards": ((370, 38), (740, 38), (1075, 36), (1395, 36)),
                "enemies": (
                    {"x": 500, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 480, "max_x": 700, "speed": 1.2, "dir": 1},
                    {"x": 960, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 890, "max_x": 1050, "speed": 1.35, "dir": -1},
                ),
            },
            {
                "name": "Moonlit Ridge",
                "world_width": 1900,
                "goal_offset": 150,
                "ground_segments": ((0, 330), (430, 670), (780, 1015), (1090, 1335), (1455, 1705), (1820, 1900)),
                "platforms": ((190, 405, 90), (430, 330, 100), (620, 280, 90), (850, 350, 100), (1055, 295, 100), (1270, 330, 100), (1490, 280, 100), (1705, 325, 110)),
                "hazards": ((300, 36), (700, 36), (1015, 38), (1365, 36), (1740, 40)),
                "enemies": (
                    {"x": 470, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 445, "max_x": 640, "speed": 1.6, "dir": 1},
                    {"x": 890, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 815, "max_x": 1025, "speed": 1.9, "dir": -1},
                    {"x": 1310, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1210, "max_x": 1435, "speed": 2.0, "dir": 1},
                ),
            },
            {
                "name": "Cinder Path",
                "world_width": 2100,
                "goal_offset": 170,
                "ground_segments": ((0, 300), (400, 640), (740, 960), (1085, 1315), (1420, 1655), (1775, 2100)),
                "platforms": ((160, 410, 88), (410, 350, 92), (610, 285, 90), (835, 345, 100), (1035, 280, 96), (1240, 330, 100), (1460, 270, 98), (1645, 318, 102), (1830, 272, 100)),
                "hazards": ((260, 30), (580, 32), (920, 34), (1180, 34), (1545, 32), (1860, 30)),
                "enemies": (
                    {"x": 440, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 400, "max_x": 630, "speed": 1.9, "dir": 1},
                    {"x": 885, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 800, "max_x": 1015, "speed": 2.1, "dir": -1},
                    {"x": 1275, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1195, "max_x": 1390, "speed": 2.3, "dir": 1},
                    {"x": 1670, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1580, "max_x": 1775, "speed": 2.5, "dir": -1},
                ),
            },
            {
                "name": "Foxfire Fall",
                "world_width": 2300,
                "goal_offset": 190,
                "ground_segments": ((0, 290), (390, 610), (710, 930), (1025, 1260), (1360, 1605), (1715, 1960), (2080, 2300)),
                "platforms": ((155, 405, 90), (395, 335, 90), (590, 270, 95), (770, 325, 98), (975, 285, 95), (1185, 330, 100), (1385, 270, 100), (1585, 315, 100), (1790, 270, 100), (1980, 320, 110)),
                "hazards": ((290, 28), (620, 32), (955, 34), (1295, 32), (1650, 34), (2010, 32)),
                "enemies": (
                    {"x": 420, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 390, "max_x": 610, "speed": 2.1, "dir": 1},
                    {"x": 820, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 760, "max_x": 940, "speed": 2.3, "dir": -1},
                    {"x": 1180, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1090, "max_x": 1305, "speed": 2.5, "dir": 1},
                    {"x": 1595, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1515, "max_x": 1705, "speed": 2.7, "dir": -1},
                ),
            },
            {
                "name": "Ashen Steps",
                "world_width": 2450,
                "goal_offset": 205,
                "ground_segments": ((0, 280), (360, 600), (680, 885), (1005, 1235), (1325, 1585), (1685, 1945), (2110, 2450)),
                "platforms": ((160, 400, 90), (385, 325, 90), (560, 265, 90), (770, 320, 100), (960, 282, 90), (1150, 330, 100), (1360, 268, 100), (1575, 310, 100), (1770, 268, 100), (1970, 315, 110), (2200, 280, 110)),
                "hazards": ((260, 28), (600, 30), (930, 32), (1230, 30), (1585, 32), (1925, 30), (2175, 30)),
                "enemies": (
                    {"x": 410, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 370, "max_x": 610, "speed": 2.3, "dir": 1},
                    {"x": 860, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 765, "max_x": 985, "speed": 2.5, "dir": -1},
                    {"x": 1170, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1080, "max_x": 1315, "speed": 2.8, "dir": 1},
                    {"x": 1580, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1485, "max_x": 1715, "speed": 3.0, "dir": -1},
                    {"x": 1985, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1910, "max_x": 2115, "speed": 3.2, "dir": 1},
                ),
            },
            {
                "name": "Night Stalker",
                "world_width": 2600,
                "goal_offset": 220,
                "ground_segments": ((0, 280), (350, 585), (660, 885), (960, 1205), (1290, 1530), (1630, 1885), (2015, 2265), (2390, 2600)),
                "platforms": ((140, 400, 90), (360, 325, 90), (545, 260, 92), (740, 318, 100), (935, 278, 96), (1135, 330, 100), (1340, 268, 100), (1545, 310, 106), (1750, 272, 100), (1960, 315, 110), (2190, 278, 100), (2375, 330, 110)),
                "hazards": ((235, 26), (560, 30), (885, 32), (1220, 30), (1550, 32), (1905, 30), (2240, 30)),
                "enemies": (
                    {"x": 390, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 355, "max_x": 580, "speed": 2.5, "dir": 1},
                    {"x": 800, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 720, "max_x": 915, "speed": 2.8, "dir": -1},
                    {"x": 1125, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1035, "max_x": 1265, "speed": 3.0, "dir": 1},
                    {"x": 1505, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1415, "max_x": 1655, "speed": 3.2, "dir": -1},
                    {"x": 1935, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1840, "max_x": 2090, "speed": 3.4, "dir": 1},
                ),
            },
            {
                "name": "Mosswall Run",
                "world_width": 2750,
                "goal_offset": 235,
                "ground_segments": ((0, 260), (330, 560), (650, 860), (940, 1180), (1265, 1510), (1625, 1880), (2000, 2245), (2365, 2750)),
                "platforms": ((135, 395, 90), (345, 317, 90), (515, 255, 90), (710, 310, 100), (900, 270, 95), (1090, 325, 100), (1285, 265, 100), (1495, 310, 100), (1700, 270, 100), (1905, 320, 110), (2110, 275, 100), (2315, 330, 105), (2510, 290, 110)),
                "hazards": ((225, 26), (520, 30), (845, 30), (1185, 30), (1525, 30), (1855, 30), (2180, 30), (2475, 30)),
                "enemies": (
                    {"x": 360, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 330, "max_x": 540, "speed": 2.7, "dir": 1},
                    {"x": 790, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 700, "max_x": 905, "speed": 3.0, "dir": -1},
                    {"x": 1105, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1015, "max_x": 1235, "speed": 3.2, "dir": 1},
                    {"x": 1490, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1405, "max_x": 1625, "speed": 3.4, "dir": -1},
                    {"x": 1910, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1820, "max_x": 2050, "speed": 3.6, "dir": 1},
                ),
            },
            {
                "name": "Ember Crown",
                "world_width": 2900,
                "goal_offset": 240,
                "ground_segments": ((0, 250), (300, 540), (620, 840), (930, 1165), (1245, 1490), (1585, 1845), (1965, 2225), (2340, 2900)),
                "platforms": ((120, 392, 92), (305, 315, 90), (485, 255, 90), (685, 310, 98), (870, 272, 96), (1060, 330, 100), (1235, 268, 98), (1440, 308, 102), (1640, 270, 100), (1850, 320, 108), (2050, 272, 100), (2245, 332, 106), (2460, 290, 110)),
                "hazards": ((200, 24), (485, 28), (810, 30), (1145, 30), (1460, 30), (1810, 30), (2135, 30), (2425, 30)),
                "enemies": (
                    {"x": 335, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 300, "max_x": 505, "speed": 2.9, "dir": 1},
                    {"x": 810, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 720, "max_x": 930, "speed": 3.2, "dir": -1},
                    {"x": 1085, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 995, "max_x": 1210, "speed": 3.4, "dir": 1},
                    {"x": 1465, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1380, "max_x": 1605, "speed": 3.6, "dir": -1},
                    {"x": 1890, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1795, "max_x": 2035, "speed": 3.8, "dir": 1},
                ),
            },
            {
                "name": "Celestial Verge",
                "world_width": 3100,
                "goal_offset": 260,
                "ground_segments": ((0, 240), (300, 520), (600, 805), (895, 1110), (1225, 1465), (1545, 1805), (1920, 2200), (2335, 2605), (2720, 3100)),
                "platforms": ((120, 390, 90), (295, 312, 90), (465, 255, 90), (645, 300, 94), (835, 260, 94), (1025, 318, 100), (1215, 260, 100), (1410, 306, 100), (1610, 258, 100), (1800, 312, 100), (2000, 260, 100), (2205, 318, 105), (2395, 270, 100), (2600, 325, 105), (2820, 285, 100)),
                "hazards": ((205, 22), (455, 26), (760, 26), (1065, 28), (1395, 28), (1735, 28), (2080, 28), (2410, 28), (2750, 28)),
                "enemies": (
                    {"x": 330, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 290, "max_x": 500, "speed": 3.1, "dir": 1},
                    {"x": 790, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 710, "max_x": 900, "speed": 3.4, "dir": -1},
                    {"x": 1085, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1005, "max_x": 1215, "speed": 3.6, "dir": 1},
                    {"x": 1450, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1365, "max_x": 1605, "speed": 3.8, "dir": -1},
                    {"x": 1880, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1800, "max_x": 2045, "speed": 4.0, "dir": 1},
                    {"x": 2450, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 2365, "max_x": 2575, "speed": 4.2, "dir": -1},
                ),
            },
            {
                "name": "Foxfire Crown",
                "world_width": 3300,
                "goal_offset": 290,
                "ground_segments": ((0, 230), (290, 500), (600, 800), (880, 1095), (1195, 1420), (1530, 1785), (1890, 2165), (2290, 2580), (2710, 3300)),
                "platforms": ((115, 388, 90), (275, 318, 88), (445, 255, 88), (620, 298, 96), (805, 255, 96), (990, 318, 100), (1185, 260, 100), (1380, 305, 100), (1570, 254, 100), (1765, 312, 104), (1960, 260, 100), (2165, 318, 102), (2365, 265, 100), (2570, 322, 104), (2800, 280, 112)),
                "hazards": ((180, 22), (455, 24), (760, 26), (1050, 28), (1385, 28), (1715, 28), (2055, 28), (2385, 28), (2725, 28)),
                "enemies": (
                    {"x": 325, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 285, "max_x": 500, "speed": 3.3, "dir": 1},
                    {"x": 805, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 700, "max_x": 905, "speed": 3.7, "dir": -1},
                    {"x": 1100, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1005, "max_x": 1225, "speed": 3.9, "dir": 1},
                    {"x": 1465, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1380, "max_x": 1605, "speed": 4.1, "dir": -1},
                    {"x": 1880, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 1795, "max_x": 2055, "speed": 4.3, "dir": 1},
                    {"x": 2450, "y": GROUND_Y - 18, "w": 22, "h": 18, "min_x": 2360, "max_x": 2605, "speed": 4.5, "dir": -1},
                ),
            },
        ]

        levels: list[dict] = []
        for index, level in enumerate(level_specs):
            level = {**level, "hazards": sanitize_hazards(level)}
            goal_x = level["world_width"] - level["goal_offset"]
            levels.append(
                {
                    **level,
                    "start_x": 120.0,
                    "start_y": float(GROUND_Y - PLAYER_HEIGHT),
                    "goal_x": float(goal_x),
                    "checkpoints": make_checkpoints(120.0, float(goal_x), 20),
                    "sky": [
                        ["#17243a", "#1d2b45", "#2a3854", "#394760"],
                        ["#101d2f", "#1a2c40", "#273a53", "#3a4b68"],
                        ["#1b2437", "#2a3244", "#3b4258", "#4d5369"],
                        ["#1f1f2d", "#2d2b46", "#3b3a5d", "#4d4a72"],
                        ["#1d2435", "#2d2f4c", "#3d405c", "#4f4c73"],
                        ["#1b1f2f", "#2a2b45", "#3a375b", "#4a466d"],
                        ["#1a1d2a", "#262d44", "#312d58", "#423a68"],
                        ["#1d1d2b", "#2b2440", "#382d55", "#4a395f"],
                        ["#17192b", "#252848", "#352f5d", "#4b3d76"],
                        ["#151820", "#222a3c", "#303459", "#483971"],
                    ][index],
                    "ground_color": ["#315047", "#2c4d4a", "#2e3f3a", "#354a43", "#2f4a4d", "#2d3a3c", "#384a4a", "#304350", "#3f4957", "#40485d"][index],
                }
            )
        return levels

    def _safe_spawn_position(self) -> tuple[float, float]:
        x = self.checkpoint_x
        safe_y = float(GROUND_Y - PLAYER_HEIGHT)

        for start, end in self.current_level["ground_segments"]:
            if start <= x <= end:
                return x, safe_y

        for px, py, pw in self.current_level["platforms"]:
            if px <= x <= px + pw:
                safe_y = min(safe_y, float(py - PLAYER_HEIGHT))

        return x, float(safe_y)

    def _load_level(self, index: int, keep_selection: bool = False) -> None:
        self.current_level_index = index
        self.current_level = self.levels[index]
        self.player_x = float(self.current_level["start_x"])
        self.player_y = float(self.current_level["start_y"])
        self.velocity_y = 0.0
        self.facing = 1
        self.on_ground = True
        self.camera_x = 0.0
        self.checkpoint_x = float(self.current_level["start_x"])
        self.enemies = []
        for enemy in self.current_level["enemies"]:
            self.enemies.append(
                {
                    "x": float(enemy["x"]),
                    "y": float(enemy["y"]),
                    "w": float(enemy["w"]),
                    "h": float(enemy["h"]),
                    "min_x": float(enemy["min_x"]),
                    "max_x": float(enemy["max_x"]),
                    "speed": float(enemy["speed"]),
                    "dir": int(enemy["dir"]),
                    "alive": True,
                }
            )
        if not keep_selection:
            self.level_select_index = index
            self._sync_scroll_to_selection()

    def _sync_scroll_to_selection(self) -> None:
        visible = 5
        if self.level_select_index < self.scroll_offset:
            self.scroll_offset = self.level_select_index
        elif self.level_select_index >= self.scroll_offset + visible:
            self.scroll_offset = self.level_select_index - visible + 1
        self.scroll_offset = max(0, min(self.scroll_offset, max(0, len(self.levels) - visible)))

    def _move_selection(self, delta: int) -> None:
        self.level_select_index = max(0, min(len(self.levels) - 1, self.level_select_index + delta))
        self._sync_scroll_to_selection()

    def on_key_down(self, event: tk.Event) -> None:
        key = event.keysym.lower()

        if key == "escape":
            if self.state == "playing":
                self.state = "level_select"
                self.keys.clear()
            elif self.state == "config":
                self.state = self.config_return_state
                self.menu_index = 0
                if self.state == "playing":
                    self.keys.clear()
            elif self.state in {"start", "level_select", "end"}:
                self.root.destroy()
            return

        if self.state == "start":
            if key in {"p", "return", "space"}:
                self.state = "level_select"
                self.level_select_index = 0
                self.scroll_offset = 0
            elif key == "c":
                self.state = "config"
                self.config_return_state = "start"
                self.config_index = 0
            elif key in {"up", "w"}:
                self.menu_index = (self.menu_index - 1) % 3
            elif key in {"down", "s"}:
                self.menu_index = (self.menu_index + 1) % 3
            elif key in {"return", "space"}:
                if self.menu_index == 0:
                    self.state = "level_select"
                    self.level_select_index = 0
                    self.scroll_offset = 0
                elif self.menu_index == 1:
                    self.state = "config"
                    self.config_return_state = "start"
                    self.config_index = 0
                else:
                    self.root.destroy()
            return

        if self.state == "config":
            if key in {"up", "w"}:
                self.config_index = (self.config_index - 1) % 2
            elif key in {"down", "s"}:
                self.config_index = (self.config_index + 1) % 2
            elif key == "p":
                self.state = "playing"
                self._load_level(self.level_select_index if self.level_select_index < len(self.levels) else 0)
            elif key in {"left", "a"}:
                if self.config_index == 0:
                    self.config_michael_jackson_mode = False
            elif key in {"right", "d"}:
                if self.config_index == 0:
                    self.config_michael_jackson_mode = True
            elif key in {"return", "space"}:
                if self.config_index == 0:
                    self.config_michael_jackson_mode = not self.config_michael_jackson_mode
                else:
                    self.state = self.config_return_state
                    self.menu_index = 0
                    if self.state == "playing":
                        self.keys.clear()
            elif key in {"b", "x"}:
                self.state = self.config_return_state
                self.menu_index = 0
                if self.state == "playing":
                    self.keys.clear()
            return

        if self.state == "level_select":
            if key in {"up", "w"}:
                self._move_selection(-1)
            elif key in {"down", "s"}:
                self._move_selection(1)
            elif key in {"prior", "page_up"}:
                self._move_selection(-5)
            elif key in {"next", "page_down"}:
                self._move_selection(5)
            elif key in {"return", "space"}:
                self.state = "playing"
                self._load_level(self.level_select_index)
            elif key == "c":
                self.state = "config"
                self.config_return_state = "level_select"
                self.config_index = 0
            elif key == "m":
                self.state = "start"
                self.menu_index = 0
            elif key in {"left", "a"}:
                self.state = "start"
                self.menu_index = 0
            return

        if self.state == "playing":
            if key == "c":
                self.state = "config"
                self.config_return_state = "playing"
                self.config_index = 0
                self.keys.clear()
                return
            if key == "m":
                self.state = "start"
                self.menu_index = 0
                self.keys.clear()
                return
            self.keys.add(key)
            if key in {"space", "w", "up"} and self.on_ground:
                self.velocity_y = -12.0
                self.on_ground = False
            return

        if self.state == "end":
            if key in {"return", "space", "r"}:
                self.state = "level_select"
                self.level_select_index = 0
                self.scroll_offset = 0

    def on_key_up(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def tick(self) -> None:
        self.update_game()
        self.draw_scene()
        self.frame += 1
        self.root.after(16, self.tick)

    def _hazard_is_on_ground(self, hazard_x: float, hazard_width: float) -> bool:
        hazard_left = hazard_x
        hazard_right = hazard_x + hazard_width
        for start, end in self.current_level["ground_segments"]:
            if hazard_right > start and hazard_left < end:
                return True
        for x, y, width in self.current_level["platforms"]:
            if hazard_right > x and hazard_left < x + width:
                return True
        return False

    def update_game(self) -> None:
        self.michael_jackson_mode = bool(self.config_michael_jackson_mode)
        if self.state != "playing":
            return

        move = 0
        if "a" in self.keys or "left" in self.keys:
            move -= 1
        if "d" in self.keys or "right" in self.keys:
            move += 1
        if move:
            self.facing = move
            self.player_x = max(24, min(self.current_level["world_width"] - 40, self.player_x + move * 3.2))

        previous_bottom = self.player_y + PLAYER_HEIGHT
        self.velocity_y = min(self.velocity_y + 0.45, 12)
        self.player_y += self.velocity_y
        self.on_ground = False

        player_left = self.player_x - PLAYER_HALF_WIDTH
        player_right = self.player_x + PLAYER_HALF_WIDTH
        player_top = self.player_y
        player_bottom = self.player_y + PLAYER_HEIGHT

        landing_y = None
        if self.velocity_y >= 0:
            for start, end in self.current_level["ground_segments"]:
                if (
                    player_right > start
                    and player_left < end
                    and previous_bottom <= GROUND_Y
                    and player_bottom >= GROUND_Y
                ):
                    landing_y = GROUND_Y - PLAYER_HEIGHT
                    break
            if landing_y is None:
                for x, y, width in self.current_level["platforms"]:
                    if (
                        player_right > x - 2
                        and player_left < x + width + 2
                        and previous_bottom <= y
                        and player_bottom >= y
                    ):
                        landing_y = y - PLAYER_HEIGHT
                        break
            if landing_y is not None:
                self.player_y = landing_y
                self.velocity_y = 0
                self.on_ground = True

        for checkpoint in self.current_level["checkpoints"]:
            if self.player_x >= checkpoint:
                self.checkpoint_x = float(checkpoint)

        for enemy in self.enemies:
            if not enemy["alive"]:
                continue
            enemy["x"] += enemy["dir"] * enemy["speed"]
            if enemy["x"] <= enemy["min_x"] or enemy["x"] + enemy["w"] >= enemy["max_x"]:
                enemy["dir"] *= -1
                enemy["x"] = max(enemy["min_x"], min(enemy["x"], enemy["max_x"] - enemy["w"]))

            enemy_left = enemy["x"]
            enemy_right = enemy["x"] + enemy["w"]
            enemy_top = enemy["y"]
            enemy_bottom = enemy["y"] + enemy["h"]
            if (
                player_right > enemy_left
                and player_left < enemy_right
                and player_bottom > enemy_top + 6
                and player_top < enemy_bottom
            ):
                if previous_bottom <= enemy_top + 8 and self.velocity_y > 0:
                    enemy["alive"] = False
                    self.velocity_y = -8.5
                    self.player_y = enemy_top - PLAYER_HEIGHT
                    self.on_ground = False
                else:
                    self.player_x = self.checkpoint_x
                    self.player_y = float(GROUND_Y - PLAYER_HEIGHT)
                    self.velocity_y = 0.0
                    self.keys.clear()
                    break

        if self.player_y > HEIGHT + 80:
            self.player_x, self.player_y = self._safe_spawn_position()
            self.velocity_y = 0
            self.on_ground = True
            self.keys.clear()

        for hazard_x, hazard_width in self.current_level["hazards"]:
            if not self._hazard_is_on_ground(hazard_x, hazard_width):
                continue
            left = hazard_x - self.camera_x
            width = max(10, int(hazard_width))
            for i in range(0, width, 10):
                self.canvas.create_polygon(
                    left + i, GROUND_Y,
                    left + i + 6, GROUND_Y - 18,
                    left + i + 12, GROUND_Y,
                    fill="#d85a5a",
                    outline="",
                )

        if self.player_x >= self.current_level["goal_x"]:
            self.completed_levels.add(self.current_level_index)
            if self.current_level_index == len(self.levels) - 1:
                self.state = "end"
            else:
                next_level = min(self.current_level_index + 1, len(self.levels) - 1)
                self.state = "level_select"
                self.level_select_index = next_level
                self._sync_scroll_to_selection()
                self._load_level(next_level, keep_selection=True)
            self.keys.clear()

        self.camera_x = max(0, min(self.current_level["world_width"] - WIDTH, self.player_x - WIDTH * 0.42))

    def draw_background(self, theme=None) -> None:
        if theme is None:
            theme = self.current_level["sky"] if self.state == "playing" else self.levels[0]["sky"]
        self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill=theme[0], outline="")
        self.canvas.create_rectangle(0, 120, WIDTH, HEIGHT, fill=theme[1], outline="")
        self.canvas.create_rectangle(0, 180, WIDTH, HEIGHT, fill=theme[2], outline="")
        self.canvas.create_rectangle(0, 240, WIDTH, HEIGHT, fill=theme[3], outline="")

        moon_x = 760 + math.sin(self.frame / 28.0) * 12
        self.canvas.create_oval(moon_x - 42, 70, moon_x + 42, 154, fill="#f7e9bc", outline="")
        self.canvas.create_oval(moon_x - 18, 95, moon_x + 18, 131, fill="#1b263d", outline="")

        for px in range(60, WIDTH + 50, 90):
            x = px + ((self.frame // 16) % 30)
            self.canvas.create_oval(x, 90 + ((px // 30) % 30), x + 5, 96 + ((px // 30) % 30), fill="#f3e3b6", outline="")

    def draw_landscape(self) -> None:
        base_color = self.current_level["ground_color"]
        self.canvas.create_rectangle(0, GROUND_Y, WIDTH, HEIGHT, fill=base_color, outline="")
        for start, end in self.current_level["ground_segments"]:
            if start < self.camera_x + WIDTH and end > self.camera_x:
                left = max(start, self.camera_x)
                right = min(end, self.camera_x + WIDTH)
                self.canvas.create_rectangle(left - self.camera_x, GROUND_Y, right - self.camera_x, HEIGHT, fill=base_color, outline="")
                self.canvas.create_rectangle(left - self.camera_x, GROUND_Y - 10, right - self.camera_x, GROUND_Y, fill="#4d826d", outline="")

        for x, y, width in self.current_level["platforms"]:
            px = x - self.camera_x
            self.canvas.create_rectangle(px, y, px + width, y + 12, fill="#5e795d", outline="")
            self.canvas.create_rectangle(px, y + 12, px + width, y + 18, fill="#7fa182", outline="")

        for hazard_x, hazard_width in self.current_level["hazards"]:
            if not self._hazard_is_on_ground(hazard_x, hazard_width):
                continue
            left = hazard_x - self.camera_x
            width = max(10, int(hazard_width))
            for i in range(0, width, 10):
                self.canvas.create_polygon(
                    left + i, GROUND_Y,
                    left + i + 6, GROUND_Y - 18,
                    left + i + 12, GROUND_Y,
                    fill="#d85a5a",
                    outline="",
                )

    def draw_campfire(self) -> None:
        x = 90 - self.camera_x
        self.canvas.create_rectangle(x - 10, GROUND_Y - 8, x + 10, GROUND_Y, fill="#503828", outline="")
        self.canvas.create_oval(x - 16, GROUND_Y - 32, x + 16, GROUND_Y - 2, fill="#ffb347", outline="")
        self.canvas.create_oval(x - 8, GROUND_Y - 22, x + 8, GROUND_Y - 10, fill="#ffd27a", outline="")

    def draw_goal(self) -> None:
        goal_x = self.current_level["goal_x"] - self.camera_x
        self.canvas.create_rectangle(goal_x - 6, GROUND_Y - 42, goal_x + 6, GROUND_Y - 20, fill="#f5e7bd", outline="")
        self.canvas.create_polygon(goal_x, GROUND_Y - 52, goal_x + 18, GROUND_Y - 26, goal_x - 18, GROUND_Y - 26, fill="#f7d29d", outline="")

    def draw_enemies(self) -> None:
        for enemy in self.enemies:
            if not enemy["alive"]:
                continue
            ex = enemy["x"] - self.camera_x
            ey = enemy["y"]
            self.canvas.create_oval(ex, ey, ex + enemy["w"], ey + enemy["h"], fill="#3c2a40", outline="")
            self.canvas.create_oval(ex + 3, ey + 2, ex + enemy["w"] - 3, ey + enemy["h"] - 4, fill="#7d4060", outline="")

    def _draw_sprite(self, x: float, y: float, action: str, facing: int = 1, frame_offset: int = 0) -> None:
        if self.michael_jackson_mode:
            frames = self.sprite_frames.get(action, [])
            if not frames:
                return
            sprite_index = (self.frame // 6 + frame_offset) % len(frames)
            sprite = frames[sprite_index]
            self.canvas.create_image(x, y, image=sprite, anchor="nw")
            return

        frames = self.flipped_sprite_frames.get(action, []) if facing < 0 else self.sprite_frames.get(action, [])
        if not frames:
            return
        sprite_index = (self.frame // 6 + frame_offset) % len(frames)
        sprite = frames[sprite_index]
        self.canvas.create_image(x, y, image=sprite, anchor="nw")

    def draw_fox(self) -> None:
        x = self.player_x - self.camera_x
        y = self.player_y
        direction = 1 if self.facing >= 0 else -1
        moving = any(key in self.keys for key in ("a", "d", "left", "right"))

        if MICHAEL_JACKSON_MODE:
            action = "walk_right" if moving else "walk_right"
            if not self.on_ground:
                action = "jump_right"
            self._draw_sprite(x - 12, y - 4, action, 1, frame_offset=(self.frame // 6) % 2 if moving else 0)
            return

        if not self.on_ground:
            action = "jump_right" if direction > 0 else "jump_left"
            animation_shift = 0 if self.velocity_y < 0 else 2
            self._draw_sprite(x - 12, y - 4, action, direction, frame_offset=animation_shift)
            return

        action = "walk_right" if direction > 0 else "walk_left"
        animation_shift = 0 if moving else 0
        if moving:
            animation_shift = (self.frame // 6) % 2
        self._draw_sprite(x - 12, y - 4, action, direction, frame_offset=animation_shift)

    def draw_start_menu(self) -> None:
        self.draw_background(theme=self.levels[0]["sky"])

        panel_x1, panel_y1, panel_x2, panel_y2 = 120, 90, WIDTH - 120, HEIGHT - 60
        self.canvas.create_rectangle(panel_x1, panel_y1, panel_x2, panel_y2, fill="#17243a", outline="#f5e7bd", width=3)
        self.canvas.create_text(WIDTH / 2, 152, text="Little Fox by the Campfire", fill="#f5e7bd", font=tkfont.Font(family="Georgia", size=30, weight="bold"))
        self.canvas.create_text(WIDTH / 2, 196, text="a cozy little platformer adventure", fill="#c2cbb5", font=tkfont.Font(family="Georgia", size=14, weight="bold"))
        self.canvas.create_text(WIDTH / 2, 228, text="designed and programmed by", fill="#c2cbb5", font=tkfont.Font(family="Georgia", size=15, weight="bold"))
        self.canvas.create_text(WIDTH / 2, 260, text="Esploric and 9TAILS", fill="#f3d7a0", font=tkfont.Font(family="Georgia", size=18, weight="bold"))

        bob = math.sin(self.frame / 10.0) * 8
        fox_x = WIDTH / 2 - 52
        fox_y = 285 + bob
        self._draw_sprite(fox_x, fox_y, "walk_right", 1, frame_offset=(self.frame // 8) % 4)

        start_y = 420
        button_gap = 66
        for index, option in enumerate(["PLAY", "CONFIG", "QUIT"]):
            x = WIDTH / 2
            y = start_y + index * button_gap
            if index == self.menu_index:
                self.canvas.create_rectangle(x - 142, y - 30, x + 142, y + 30, fill="#f5e7bd", outline="")
                self.canvas.create_text(x, y, text=option, fill="#17243a", font=tkfont.Font(family="Georgia", size=20, weight="bold"))
            else:
                self.canvas.create_rectangle(x - 128, y - 26, x + 128, y + 26, fill="#2d3a4c", outline="")
                self.canvas.create_text(x, y, text=option, fill="#dfe9d3", font=tkfont.Font(family="Georgia", size=18, weight="bold"))

        self.canvas.create_text(WIDTH / 2, HEIGHT - 78, text="Press C for config • Arrow keys to move • Enter to select", fill="#d0dacc", font=tkfont.Font(family="Georgia", size=11, weight="bold"))

    def draw_config_menu(self) -> None:
        self.draw_background(theme=self.levels[0]["sky"])

        panel_x1, panel_y1, panel_x2, panel_y2 = 160, 120, WIDTH - 160, HEIGHT - 120
        self.canvas.create_rectangle(panel_x1, panel_y1, panel_x2, panel_y2, fill="#17243a", outline="#f5e7bd", width=3)
        self.canvas.create_text(WIDTH / 2, 180, text="Config", fill="#f5e7bd", font=tkfont.Font(family="Georgia", size=28, weight="bold"))

        toggle_text = "ON" if self.config_michael_jackson_mode else "OFF"
        self.canvas.create_text(WIDTH / 2, 260, text=f"Michael Jackson Mode: {toggle_text}", fill="#dfe9d3", font=tkfont.Font(family="Georgia", size=20, weight="bold"))

        options = ["Toggle mode", "Back"]
        for index, option in enumerate(options):
            y = 335 + index * 70
            selected = index == self.config_index
            if selected:
                self.canvas.create_rectangle(WIDTH / 2 - 150, y - 22, WIDTH / 2 + 150, y + 22, fill="#f5e7bd", outline="")
                self.canvas.create_text(WIDTH / 2, y, text=option, fill="#17243a", font=tkfont.Font(family="Georgia", size=18, weight="bold"))
            else:
                self.canvas.create_rectangle(WIDTH / 2 - 135, y - 18, WIDTH / 2 + 135, y + 18, fill="#2d3a4c", outline="")
                self.canvas.create_text(WIDTH / 2, y, text=option, fill="#dfe9d3", font=tkfont.Font(family="Georgia", size=16, weight="bold"))

        self.canvas.create_text(WIDTH / 2, HEIGHT - 110, text="Arrow keys to move • Enter to select • Esc to go back", fill="#d0dacc", font=tkfont.Font(family="Georgia", size=11, weight="bold"))

    def draw_level_select(self) -> None:
        self.draw_background(theme=self.levels[0]["sky"])
        self.canvas.create_rectangle(60, 60, WIDTH - 60, HEIGHT - 50, fill="#17243a", outline="#f5e7bd", width=3)
        self.canvas.create_text(WIDTH / 2, 110, text="Choose your trail", fill="#f5e7bd", font=tkfont.Font(family="Georgia", size=28, weight="bold"))
        self.canvas.create_text(WIDTH / 2, 144, text="little fox, big adventures", fill="#c4d4c6", font=tkfont.Font(family="Georgia", size=12, weight="bold"))

        visible_count = 5
        visible_levels = self.levels[self.scroll_offset : self.scroll_offset + visible_count]
        item_left = 150
        item_right = WIDTH - 170
        item_width = item_right - item_left
        start_y = 200
        for offset, level in enumerate(visible_levels):
            index = self.scroll_offset + offset
            selected = index == self.level_select_index
            base_y = start_y + offset * 72
            fill = "#f5e7bd" if selected else "#394d62"
            self.canvas.create_rectangle(item_left, base_y - 26, item_right, base_y + 26, fill=fill, outline="")

            display_name = level["name"]
            if len(display_name) > 18:
                display_name = display_name[:15] + "..."
            label = f"{index + 1}. {display_name}"
            self.canvas.create_text(item_left + 30, base_y, anchor="w", text=label, fill="#17243a" if selected else "#eff7ef", font=tkfont.Font(family="Georgia", size=14, weight="bold"))
            status = "CLEAR" if index in self.completed_levels else "READY"
            self.canvas.create_text(item_right - 28, base_y, anchor="e", text=status, fill="#17243a" if selected else "#eff7ef", font=tkfont.Font(family="Georgia", size=11, weight="bold"))

        scrollbar_top = 180
        scrollbar_bottom = 470
        self.canvas.create_rectangle(WIDTH - 110, scrollbar_top, WIDTH - 92, scrollbar_bottom, fill="#2d3a4c", outline="")
        track_height = scrollbar_bottom - scrollbar_top
        total_pages = max(1, len(self.levels) - visible_count + 1)
        thumb_h = max(34, int(track_height / total_pages))
        thumb_y = scrollbar_top + (self.scroll_offset / max(1, len(self.levels) - visible_count)) * max(0, track_height - thumb_h)
        self.canvas.create_rectangle(WIDTH - 110, thumb_y, WIDTH - 92, thumb_y + thumb_h, fill="#f5e7bd", outline="")

        self.canvas.create_text(WIDTH / 2, HEIGHT - 90, text="Arrow keys to move • Page Up/Down to scroll • Enter to play • Esc to return", fill="#d0dacc", font=tkfont.Font(family="Georgia", size=11, weight="bold"))

    def draw_end_screen(self) -> None:
        self.draw_background(theme=self.levels[-1]["sky"])
        self.canvas.create_rectangle(140, 150, WIDTH - 140, HEIGHT - 130, fill="#17243a", outline="#f5e7bd", width=3)
        self.canvas.create_text(WIDTH / 2, 220, text="The little fox is home!", fill="#f5e7bd", font=tkfont.Font(family="Georgia", size=28, weight="bold"))
        self.canvas.create_text(WIDTH / 2, 270, text="all 10 cozy trails cleared", fill="#c2cbb5", font=tkfont.Font(family="Georgia", size=15, weight="bold"))
        self.canvas.create_text(WIDTH / 2, 350, text="Press Enter or R to wander another route", fill="#f5e7bd", font=tkfont.Font(family="Georgia", size=13, weight="bold"))

    def draw_scene(self) -> None:
        self.canvas.delete("all")

        if self.state == "start":
            self.draw_start_menu()
            return

        if self.state == "config":
            self.draw_config_menu()
            return

        if self.state == "level_select":
            self.draw_level_select()
            return

        if self.state == "end":
            self.draw_end_screen()
            return

        self.draw_background()
        self.draw_landscape()
        self.draw_goal()
        self.draw_campfire()
        self.draw_enemies()
        self.draw_fox()

        self.canvas.create_text(18, 18, anchor="nw", text=f"Trail {self.current_level_index + 1}: {self.current_level['name']}", fill="#f5e7bd", font=tkfont.Font(family="Georgia", size=12, weight="bold"))


def main() -> None:
    root = tk.Tk()
    game = CozyFoxGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()