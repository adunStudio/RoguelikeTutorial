import tcod
import math
import textwrap
import shelve

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

WINDOW_TITLE = "Python 3 tcod tutorial"
FULL_SCREEN = False
LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 43

BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH # -2
MSG_HEIGHT = PANEL_HEIGHT - 1

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

EXPLORE_MODE = False

color_dark_wall = tcod.Color(0, 0, 100)
color_light_wall = tcod.Color(130, 110, 50)
color_dark_ground = tcod.Color(50, 50, 150)
color_light_ground = tcod.Color(200, 180, 50)

FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 7

INVENTORY_WIDTH = 50

HEAL_AMOUNT = 40

LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8

FIREBALL_DAMAGE = 25
FIREBALL_RADIUS = 3

LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150 # 200 + player.level * 150

LEVEL_SCREEN_WIDTH = 40

CHARACTER_SCREEN_WIDTH = 30

class Fighter:
    def __init__(self, hp, defense, power, xp, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.xp = xp

        self.death_function = death_function

    def take_damage(self, damage):
        if damage > 0:
            self.hp -= damage

        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                function(self.owner)

            if self.owner != player:
                player.fighter.xp += self.xp


    def attack(self, target):
        damage = self.power - target.fighter.defense

        if damage > 0:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')

    def heal(self, amount):
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class BasicMonster:
    def take_turn(self):
        monster = self.owner
        if tcod.map_is_in_fov(fov_map, monster.x, monster.y):

            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

class ConfuseMonster:
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0:
            self.owner.move(tcod.random_get_int(0, -1, 1), tcod.random_get_int(0, -1, 1))
            self.num_turns -= 1
        else:
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', tcod.red)


class Rect:
    def __init__(self, x, y, w, h):
        # top-left
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) // 2
        center_y = (self.y1 + self.y2) // 2

        return (center_x, center_y)

    def intersect(self, other):
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

class Tile:
    def __init__(self, blocked, block_sight = None):
        self.explored = False
        self.blocked = blocked

        if block_sight is None:
            block_sight = blocked

        self.block_sight = block_sight


class Object:
    def __init__(self, x, y, char, name, color, blocks = False, always_visible=False, fighter = None, ai = None, item = None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible

        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

        self.item = item
        if self.item:
            self.item.owner = self


    def move(self, dx, dy):
        global map
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def move_towards(self, target_x, target_y):
        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.sqrt(dx ** 2 + dy ** 2)

        # Normalize
        dx = int(round(dx / dist))
        dy = int(round(dy / dist))
        self.move(dx, dy)

    def distance_to(self, other):
        dx = other.x - self.x
        dy = other.y - self.y

        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def send_to_back(self):
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def draw(self):
        if EXPLORE_MODE:
            visible = tcod.map_is_in_fov(fov_map, self.x, self.y) or self.always_visible
            if not visible:
                return

        tcod.console_set_default_foreground(con, self.color)
        tcod.console_put_char(con, self.x, self.y, self.char, tcod.BKGND_NONE)

    def clear(self):
        tcod.console_put_char(con, self.x, self.y, ' ', tcod.BKGND_NONE)

class Item:
    def __init__(self, use_function=None):
        self.use_function = use_function

    def use(self):
        if self.use_function is None:
            message("the" + self.owner.name + " cannot be used")
        else:
            if self.use_function() != "cancelled":
                inventory.remove(self.owner)

    def pick_up(self):
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', tcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', tcod.green)

    def drop(self):
        objects.append(self.owner)
        inventory.remove(self.owner)

        self.owner.x = player.x
        self.owner.y = player.y

        message('You dropped a ' + self.owner.name + '.', tcod.yellow)

def make_map():
    global map, objects, stairs

    objects = [player]

    map = [ [Tile(True) for y in range(MAP_HEIGHT)] for x in range(MAP_WIDTH) ]

    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS):
        w = tcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = tcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        # random position without going out of the boundaries of the map
        x = tcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = tcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        new_room = Rect(x, y, w, h)

        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:

            create_room(new_room)


            (new_x, new_y) = new_room.center()
            #room_no = Object(new_x, new_y, chr(65 + num_rooms), 'room number', tcod.white, blocks=False)
            #objects.insert(0, room_no)
            #room_no.send_to_back()

            if num_rooms == 0:
                player.x = new_x
                player.y = new_y

            else:
                (prev_x, prev_y) = rooms[num_rooms-1].center()

                if tcod.random_get_int(0, 0, 1) == 1:
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

                place_objects(new_room)


            rooms.append(new_room)
            num_rooms += 1

    stairs = Object(new_x, new_y, '<', "stairs", tcod.white, always_visible=True)
    objects.append(stairs)
    stairs.send_to_back()

def create_room(room):
    global map

    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y): # 가로
    global map

    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x): # 세로
    global map

    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def place_objects(room):

    max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])

    monster_chances = {}
    monster_chances["orc"] = 80
    monster_chances["troll"] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])

    for i in range(0, max_monsters):
        x = tcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = tcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not is_blocked(x, y):
            choice = random_choice(monster_chances)

            if choice == "orc":  # 80% chance of getting an orc
                fighter_component = Fighter(hp=20, defense=0, power=4, xp=35, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'o', 'orc', tcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)
            if choice == "troll":
                fighter_component = Fighter(hp=30, defense=2, power=8, xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'T', 'troll', tcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)

            objects.append(monster)

    max_items = from_dungeon_level([[2, 1], [2, 4]])

    item_chances = {} # {'heal': 70, 'lightning': 10, 'fireball': 10, 'confuse': 10}
    item_chances["heal"] = 35
    item_chances['lightning'] = from_dungeon_level([[25, 4]])
    item_chances['fireball'] = from_dungeon_level([[25, 6]])
    item_chances['confuse'] = from_dungeon_level([[10, 2]])

    for i in range(0, max_items):
        x = tcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = tcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not is_blocked(x, y):
            choice = random_choice(item_chances)

            if choice == 'heal':
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', 'healing potion', tcod.violet, item=item_component)

            if choice == 'lightning':
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '#', 'scroll of lightning bolt', tcod.light_yellow, item=item_component)

            if choice == 'fireball':
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '#', 'scroll of fireball', tcod.light_red, item=item_component)

            if choice == 'confuse':
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '#', 'scroll of confusion', tcod.light_yellow, item=item_component)

            objects.append(item)
            item.send_to_back()


def is_blocked(x, y):
    if map[x][y].blocked:
        return True

    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False

def player_death(player):
    global game_state
    message("You Died!", tcod.red)
    game_state = "deat"

    player.char = "%"
    player.color = tcod.dark_red

def monster_death(monster):

    message('The ' + monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', tcod.orange)
    monster.char = '%'
    monster.color = tcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name

    monster.send_to_back()

def cast_heal():
    if player.fighter.hp == player.fighter.max_hp:
        message("you are already at full health.", tcod.red)
        return "cancelled"

    message("your wounds start to feel better!", tcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)


def cast_lightning():

    monster = closest_monster(LIGHTNING_RANGE)

    if monster is None:
        message("No enemy is close enough to strike.", tcod.red)
        return "cancelled"

    message('A lighting bolt strikes the ' + monster.name + ' with a loud thunder! The damage is ' + str(LIGHTNING_DAMAGE) + ' hit points.', tcod.light_blue)

    monster.fighter.take_damage(LIGHTNING_DAMAGE)


def cast_confuse():

    message('Left-click an enemy to confuse it, or right-click to cancel.', tcod.light_cyan)

    monster = target_monster(CONFUSE_RANGE)

    if monster is None:
        return 'cancelled'

    old_ai = monster.ai
    monster.ai = ConfuseMonster(old_ai=old_ai)
    monster.ai.owner = monster
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', tcod.light_green)


def cast_fireball():
    message('Left-click a target tile for the fireball, or right-click to cancel.', tcod.light_cyan)

    (x, y) = target_tile()
    if x is None:
        return "cancelled"

    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', tcod.orange)

    for obj in objects:
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', tcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)


def closest_monster(max_range):

    closest_enemy = None
    closest_dist = max_range + 1

    for object in objects:
        if object.fighter and not object == player and tcod.map_is_in_fov(fov_map, object.x, object.y):
            dist = player.distance_to(object)
            if dist < closest_dist:
                closest_enemy = object
                closest_dist = dist
                break

    return closest_enemy

def target_tile(max_range=None):
    global key, mouse

    while True:
        tcod.console_flush()
        tcod.sys_check_for_event(tcod.EVENT_KEY | tcod.EVENT_MOUSE, key, mouse)
        render_all()

        (x, y) = (mouse.cx, mouse.cy)

        if mouse.lbutton_pressed and tcod.map_is_in_fov(fov_map, x, y) and (max_range is None or player.distance(x, y) <= max_range):
            return (x, y)

        if mouse.rbutton_pressed or key.vk == tcod.KEY_ESCAPE:
            return (None, None)


def target_monster(max_range=None):

    while True:
        (x, y) = target_tile(max_range)
        if x is None:
            return None

        for obj in objects:
            if obj.x == x and obj.y ==y and obj.fighter and obj != player:
                return obj


def inventory_menu(header):
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    if index is None or len(inventory) == 0:
        return None

    return inventory[index].item

def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

    header_height = tcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)

    if header == '':
        header_height = 0

    height = len(options) + header_height + 2

    window = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

    tcod.console_set_default_foreground(window, tcod.white)
    tcod.console_print_rect_ex(window, 0, 1, width, height, tcod.BKGND_NONE, tcod.LEFT, header)

    y = header_height + 1
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        tcod.console_print_ex(window, 0, y, tcod.BKGND_NONE, tcod.LEFT, text)
        y += 1
        letter_index += 1

    x = int(SCREEN_WIDTH /2 - width / 2)
    y = int(SCREEN_HEIGHT /2 - height / 2)


    tcod.console_blit(window, 0, 0, width, height, 0, x, y - 3, 1.0, 0.7)

    tcod.console_flush()
    key = tcod.console_wait_for_keypress(True)

    if key.vk == tcod.KEY_ENTER and key.lalt:
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

    index = key.c - ord('a')
    if index >= 0 and index < len(options):
        return index

    return None

def msgbox(text, width=50):
    menu(text, [], width)

def main_menu():
    img = tcod.image_load("/Users/adun/Desktop/RoguelikeTutorial/princess.png") # 160 * 100

    while not tcod.console_is_window_closed():
        tcod.image_blit_2x(img, 0, 0, 0)

        choice = menu("", ["Play a new game, ", "Continue last game", "Quit"], 24)

        if choice == 1:
            try:
                load_game()
            except:
                msgbox("\n No saved game to load.\n", 24)
                continue
            play_game()
        elif choice == 0:
            new_game()
            play_game()

        elif choice == 2:
            break


def check_level_up():
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', tcod.yellow)

        choice = None
        while choice == None:
            choice = menu('Level up! Choose a stat to raise:\n',
                          ['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
                           'Strength (+1 attack, from ' + str(player.fighter.power) + ')',
                           'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)

        if choice == 0:
            player.fighter.max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.power += 1
        elif choice == 2:
            player.fighter.defense += 1


def random_choice_index(chances):

    dice = tcod.random_get_int(0, 1, sum(chances))

    running_sum = 0
    choice = 0

    for w in chances:
        running_sum += w

        if dice <= running_sum:
            return choice

        choice += 1

def random_choice(chances_dict):
    chances = chances_dict.values()
    strings = list(chances_dict.keys())
    
    return strings[random_choice_index(chances)]


def from_dungeon_level(table):
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value

    return 0


def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute

    if fov_recompute:
        # recompute FOV if needed (the player moved or something)
        fov_recompute = False
        tcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        # go through all tiles, and set their background color according to the FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = tcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if EXPLORE_MODE:
                    if not visible:
                        # it's out of the player's FOV
                        if map[x][y].explored:
                            if wall:
                                tcod.console_set_char_background(con, x, y, color_dark_wall, tcod.BKGND_SET)
                            else:
                                tcod.console_set_char_background(con, x, y, color_dark_ground, tcod.BKGND_SET)
                    else:
                        # it's visible
                        if wall:
                            tcod.console_set_char_background(con, x, y, color_light_wall, tcod.BKGND_SET)
                        else:
                            tcod.console_set_char_background(con, x, y, color_light_ground, tcod.BKGND_SET)

                        map[x][y].explored = True

                else:
                    if not visible:
                        # it's out of the player's FOV
                        if wall:
                            tcod.console_set_char_background(con, x, y, color_dark_wall, tcod.BKGND_SET)
                        else:
                            tcod.console_set_char_background(con, x, y, color_dark_ground, tcod.BKGND_SET)
                    else:
                        # it's visible
                        if wall:
                            tcod.console_set_char_background(con, x, y, color_light_wall, tcod.BKGND_SET)
                        else:
                            tcod.console_set_char_background(con, x, y, color_light_ground, tcod.BKGND_SET)

    # draw all objects in the list
    for object in objects:
        if object != player:
            object.draw()

    player.draw()

    # blit the contents of "con" to the root console
    tcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

    # GUI
    tcod.console_set_default_background(panel, tcod.black)
    tcod.console_clear(panel)

    message_y = 1

    for (line, color) in game_msgs:
        tcod.console_set_default_foreground(panel, color)
        tcod.console_print_ex(panel, MSG_X, message_y, tcod.BKGND_NONE, tcod.LEFT, line)
        message_y += 1

    tcod.console_set_default_foreground(panel, tcod.light_gray)
    name = get_names_under_mouse()
    tcod.console_print_ex(panel, 1, 0, tcod.BKGND_NONE, tcod.LEFT, name)

    tcod.console_print_ex(panel, 1, 3, tcod.BKGND_NONE, tcod.LEFT, 'Dungeon level ' + str(dungeon_level))

    render_bar(1, 1, BAR_WIDTH, "HP", player.fighter.hp, player.fighter.max_hp, tcod.light_red, tcod.darker_red)
    tcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)


def handle_keys():
    global key

    if key.vk == tcod.KEY_ENTER and key.lalt:
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

    elif key.vk == tcod.KEY_ESCAPE:
        return 'exit'  # exit game

    if game_state == 'playing':
        if key.vk == tcod.KEY_UP or key.vk == tcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == tcod.KEY_DOWN or key.vk == tcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == tcod.KEY_LEFT or key.vk == tcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == tcod.KEY_RIGHT or key.vk == tcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == tcod.KEY_HOME or key.vk == tcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == tcod.KEY_PAGEUP or key.vk == tcod.KEY_KP9:
            player_move_or_attack(1, -1)
        elif key.vk == tcod.KEY_END or key.vk == tcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == tcod.KEY_PAGEDOWN or key.vk == tcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == tcod.KEY_KP5:
            pass
        else:
            key_char = chr(key.c)

            if key_char == 'g':
                for object in objects:
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break

            if key_char == 'i':
                # show the inventory
                choose_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if choose_item is not None:
                    choose_item.use()

            if key_char == 'd':
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()

            if key_char == 'a':
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()

            if key_char == 'c':
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox(
                    'Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
                    '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense),
                    CHARACTER_SCREEN_WIDTH)

            else:
                return 'didnt-take-turn'


def player_move_or_attack(dx, dy):
    global fov_recompute

    # the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy

    # try to find an attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break

    # attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True

con = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

panel = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)



def get_names_under_mouse():
    global mouse
    (x, y) = mouse.cx, mouse.cy

    names = [obj.name for obj in objects if obj.x == x and obj.y == y and tcod.map_is_in_fov(fov_map, obj.x, obj.y)]

    names = ','.join(names)

    return  names.capitalize()


def message(new_msg, color = tcod.white):
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        game_msgs.append((line, color))


def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):

    bar_width = int(float(value) / maximum * total_width)

    tcod.console_set_default_background(panel, back_color)
    tcod.console_rect(panel, x, y, total_width, 1, False, tcod.BKGND_SCREEN)

    tcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        tcod.console_rect(panel, x, y, bar_width, 1, False, tcod.BKGND_SCREEN)

    tcod.console_set_default_foreground(panel, tcod.white)
    tcod.console_print_ex(panel, x + total_width // 2, y, tcod.BKGND_NONE, tcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))

def next_level():
    global dungeon_level

    dungeon_level += 1

    message('You take a moment to rest, and recover your strength.', tcod.light_violet)
    player.fighter.heal(player.fighter.max_hp // 2)

    message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', tcod.red)
    make_map()
    initialize_fov()


def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level

    dungeon_level = 1

    fighter_component = Fighter(hp=100, defense=1, power=4, xp=0, death_function=player_death)
    player = Object(0, 0, '@', 'player', tcod.white, blocks=True, fighter=fighter_component)

    player.level = 1

    make_map()
    initialize_fov()

    inventory = []

    game_msgs = []

    game_state = "playing"

    message("Welcomm stranger! Prepare to perish in the Tombs of the Ancient Kings.", tcod.red)

def initialize_fov():
    global fov_map, fov_recompute

    fov_recompute = True

    fov_map = tcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    tcod.console_clear(con)


def play_game():
    global key, mouse

    mouse = tcod.Mouse()
    key = tcod.Key()

    while not tcod.console_is_window_closed():
        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS | tcod.EVENT_MOUSE, key, mouse)

        render_all()


        tcod.console_flush()

        check_level_up()


        for object in objects:
            object.clear()

        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        if game_state == "playing" and player_action != "didnt-take-turn":
            for object in objects:
                if object.ai:
                    object.ai.take_turn()

def save_game():

    file = shelve.open("savegame", "n")
    file["map"] = map
    file["objects"] = objects
    file["player_index"] = objects.index(player)
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level

    file.close()

def load_game():
    global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level

    file = shelve.open("savegame", "r")
    map = file["map"]
    objects = file['objects']
    player = objects[file['player_index']]  # get index of player in objects list and access it
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']

    file.close()

    initialize_fov()


def main():

    tcod.console_set_custom_font('/Users/adun/Desktop/RoguelikeTutorial/arial10x10.png', tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD)

    tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, WINDOW_TITLE, FULL_SCREEN)

    tcod.sys_set_fps(LIMIT_FPS)

    main_menu()


if __name__ == "__main__":
    main()

