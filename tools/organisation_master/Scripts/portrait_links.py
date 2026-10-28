"""Resolve Country Master portrait sprites to portable mod/base-game file links."""
import os

from cm_data import CountryData, find_game


def _resolver(root, game=None):
	# Use the existing sprite/path lookup without loading country histories or map data.
	data = CountryData.__new__(CountryData)
	data.root, data.game = root, game
	data.replaced = data._read_replace_paths()
	return data


def resolve_portraits(mod_root, sprites):
	root = os.path.abspath(mod_root)
	game = find_game(root)
	data = _resolver(root, game)
	base = _resolver(game) if game else None
	out = {}
	for sprite in dict.fromkeys(sprites):
		path = data.portrait_path(sprite)
		if not path and base:
			# Generic portraits can originate in a vanilla atlas replaced by the mod.
			path = base.portrait_path(sprite)
			if path:
				mod_path = os.path.join(root, base.rel(path))
				if os.path.isfile(mod_path):
					path = mod_path
		if path:
			try:
				in_mod = os.path.commonpath((os.path.normcase(root), os.path.normcase(os.path.abspath(path)))) == os.path.normcase(root)
			except ValueError:
				in_mod = False
			if not in_mod and base is None:
				continue
			out[sprite] = os.path.relpath(path, root).replace("\\", "/") if in_mod else "game:" + base.rel(path)
	return out


def game_link_path(mod_root, link):
	game = find_game(mod_root)
	if not game or not link.startswith("game:"):
		return None
	root = os.path.normcase(os.path.abspath(game))
	path = os.path.abspath(os.path.join(game, link[5:]))
	try:
		if os.path.commonpath((root, os.path.normcase(path))) == root and os.path.isfile(path):
			return path
	except ValueError:
		pass
	return None


def game_portrait_path(mod_root, game, sprite):
	"""Fallback for a vanilla sprite hidden by a mod's replace_path for interface files."""
	if not game:
		return None
	base = _resolver(game)
	path = base.portrait_path(sprite)
	if path:
		override = os.path.join(mod_root, base.rel(path))
		return override if os.path.isfile(override) else path
	return None
