"""Stable achievement IDs for the theme discoveries."""
THEME_BADGES = (
    ('egg_rr', 'Permanent Duck Revolution', 'flag', 'Revolution Realised', 'Meet the little revolutionary duck.'),
    ('egg_midnight', 'Before the Night', 'alt_sun', 'Midnight', 'Find the moon and drag it toward the mountains.'),
    ('egg_field', 'Drum Roll, Please', 'microphone', 'Field Grey', 'Play the hidden field drum.'),
    ('egg_field_combo', 'Beat the Deadline', 'clock', 'Field Grey', 'Play 16 drum beats within 10 seconds.'),
    ('egg_arctic', 'Polar Express', 'alt_snowflake', 'Arctic Station', 'Launch the penguin.'),
    ('egg_burg', 'Forbidden Filing', 'archive', 'BurgSys', 'Unseal the ominous redaction.'),
    ('egg_sorel', 'Well, That Escalated', 'alt_burning_torch', 'Sons of Sorel', 'Discover the scorched version of the theme.'),
    ('egg_terminal', 'Shall We Play a Game?', 'question', 'Soviet Terminal', 'Find the terminal minigame.'),
    ('egg_terminal_win', 'The Only Winning Move', 'shield', 'Soviet Terminal', 'Win in Tic Tac Toe.'),
    ('egg_stallonian', 'A Moustache of Authority', 'alt_royal_crown', 'Stallonian Gambit', 'Crown the portrait and catch its wandering eyes.'),
    ('egg_halloween', 'Bone to Be Wild', 'alt_crescent_moon', 'Halloween', 'Find the waving skeleton hand.'),
    ('egg_sleigh_10', 'Sleigh the Backlog', 'rocket', 'Christmas', 'Collect 10 presents in a single run.'),
    ('egg_stocking', 'Stocking Filler', 'bell', 'Christmas', 'Discover what is hiding in the stocking.'),
    ('egg_vapor', 'A Side of Paradise', 'play', 'Vaporwave', 'Play the hidden sunset cassette.'),
    ('egg_rising', 'Purrfect Timing', 'clock', 'Rising Sun', 'Wake the sleepy ink cat.'),
    ('egg_andorran', 'Two Heads, One Party', 'alt_royal_crown', 'Andorran Dream', 'Meet the imperial party eagles.'),
    ('egg_classic', 'Revolution on Repeat', 'globe', 'Classic', 'Find the bouncing RR logo.'),
)


def unlock(app, key):
    """Use the same synced, retained developer records as other secret badges."""
    todo = app.todo_page()
    dev = next((d for d in todo.data['devs'] if d['name'] == todo.me.get()), None)
    if dev is None or key in (dev.get('secrets') or []):
        return False
    dev.setdefault('secrets', []).append(key)
    todo.save(undoable=False, feedback=False)
    if todo.achievement_pane is not None:
        todo.achievement_pane.fill()
    title = next(row[1] for row in THEME_BADGES if row[0] == key)
    app.set_status(f'{title} unlocked for {dev["name"]}!')
    return True
