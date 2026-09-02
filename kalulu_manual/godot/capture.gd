extends Node
## Screenshot harness for the Kalulu user manuals.
##
## This file does not live in Kalulu-Frontend. The manual generator copies it
## into the frontend project under `manual_capture/`, runs it, and deletes it
## again, so the app repository carries nothing for the sake of documentation.
##
## It must be run as a *scene* (`Godot --path <frontend> res://manual_capture/capture.tscn`)
## and **not** through `--script`: a `--script` run compiles before the autoloads
## register, and every menu here needs UserDataManager, Log and Database.
## It must also run **without** `--headless`, whose dummy rasterizer renders
## nothing and hands back blank images.
##
## Jobs arrive as JSON in the KALULU_MANUAL_JOBS environment variable (a path).
## A result JSON is written next to it so the Python side can report per-shot
## success without scraping stdout.

const VIEWPORT_SIZE := Vector2i(2560, 1800)
## Frames to let the scene settle. Menus animate in, fonts finish shaping and
## OpeningCurtain runs a tween; a low count captures a half-drawn screen.
const SETTLE_FRAMES := 24
## How many times to re-read a viewport that came back as one flat colour.
const GRAB_ATTEMPTS := 3
## How many times to wait again for the minigame wheel to paint.
const WHEEL_ATTEMPTS := 4
## A single shot may not take longer than this. If one does, the harness writes
## what it has and quits, rather than leaving a Godot window open forever with
## nobody watching it. A scene that awaits something which never arrives -- an
## audio "finished" that cannot fire, a curtain that never opens -- would
## otherwise hang the whole run silently.
const SHOT_TIMEOUT_SECONDS := 90.0

var _results: Array = []
var _watchdog: Timer
var _out_paths: Dictionary = {}


func _ready() -> void:
	# macOS stops driving an occluded window, and a window that is not being
	# drawn hands back black textures. Capture is an explicit developer action,
	# so a window that insists on staying visible for its duration is the right
	# trade against silently blank screenshots.
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true)
	DisplayServer.window_move_to_foreground()

	var jobs_path := OS.get_environment("KALULU_MANUAL_JOBS")
	if jobs_path.is_empty():
		push_error("KALULU_MANUAL_JOBS is not set")
		get_tree().quit(2)
		return

	var jobs: Dictionary = _read_json(jobs_path)
	if jobs.is_empty():
		get_tree().quit(2)
		return

	var out_dir: String = jobs.get("out_dir", "")
	DirAccess.make_dir_recursive_absolute(out_dir)

	_out_paths = {"result_path": jobs.get("result_path", "")}
	_watchdog = Timer.new()
	_watchdog.one_shot = true
	_watchdog.wait_time = SHOT_TIMEOUT_SECONDS
	_watchdog.timeout.connect(_on_watchdog)
	add_child(_watchdog)

	for shot: Dictionary in jobs.get("shots", []):
		_watchdog.start(SHOT_TIMEOUT_SECONDS)
		await _capture(shot, out_dir)
		_watchdog.stop()

	_write_results()
	print("CAPTURE: done, %d shots" % _results.size())
	get_tree().quit(0)


## The scene of the helper Kalulu, the one who climbs out of a hole to explain
## a screen. Behind him is a 67%-opaque near-black ColorRect covering the whole
## view, which is exactly the part of a screenshot a manual cannot use.
const KALULU_HELPER_SCENE: String = "res://sources/minigames/base/kalulu_ingame.tscn"


## Hide every helper Kalulu in the tree.
##
## Matched on the instanced scene rather than the node name: the name "Kalulu"
## is also worn by scenery -- the little one sitting on the brain map -- and by
## the boss's own Kalulu, both of which belong in the picture. Only the helper
## is an instance of this scene.
##
## Marking his speeches as already played (see `_silence_kalulu`) stops him
## talking, but the gardens, the brain and every minigame still ship him
## visible in the scene, so he has to be hidden as well as silenced.
func _hide_helper_kalulu(root: Node) -> void:
	var queue: Array[Node] = [root]
	while not queue.is_empty():
		var node: Node = queue.pop_back()
		for child: Node in node.get_children():
			queue.append(child)
		if node.scene_file_path == KALULU_HELPER_SCENE and "visible" in node:
			node.set("visible", false)


## Give up on a shot that will not finish, and take the process down with it.
##
## Timers keep firing while a coroutine is stuck, because the tree goes on
## processing frames, so this fires even when nothing else can make progress.
func _on_watchdog() -> void:
	push_error("CAPTURE: a shot exceeded %ds; quitting" % int(SHOT_TIMEOUT_SECONDS))
	_write_results()
	get_tree().quit(4)


func _write_results() -> void:
	var result_path: String = _out_paths.get("result_path", "")
	if result_path.is_empty():
		return
	var handle := FileAccess.open(result_path, FileAccess.WRITE)
	if handle:
		handle.store_string(JSON.stringify({"results": _results}, "  "))
		handle.close()


func _read_json(path: String) -> Dictionary:
	var handle := FileAccess.open(path, FileAccess.READ)
	if handle == null:
		push_error("cannot read jobs file: %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(handle.get_as_text())
	handle.close()
	return parsed if parsed is Dictionary else {}


func _capture(shot: Dictionary, out_dir: String) -> void:
	var key: String = shot.get("key", "unnamed")
	var locale: String = shot.get("locale", "fr")
	var recipe: String = shot.get("recipe", "scene")
	var args: Dictionary = shot.get("args", {})
	# One directory per locale: the same key is captured once per language and
	# they must not overwrite each other.
	var locale_dir := "%s/%s" % [out_dir, locale]
	DirAccess.make_dir_recursive_absolute(locale_dir)
	var path := "%s/%s.png" % [locale_dir, key]

	TranslationServer.set_locale(locale)
	_seed_account(args)

	var root: Node = null
	var error := ""
	match recipe:
		"scene":
			root = _instantiate(args.get("scene", ""))
		"register_step":
			root = await _register_step(args)
		"student_details":
			root = await _student_details(args)
		"gameplay":
			root = _gameplay(args)
		"garden_wheel":
			root = _gameplay(args)
		_:
			error = "unknown recipe %s" % recipe

	if root == null and error.is_empty():
		error = "scene failed to instantiate"

	if not error.is_empty():
		_results.append({"key": key, "locale": locale, "ok": false, "error": error})
		push_warning("CAPTURE %s: %s" % [key, error])
		return

	var viewport := SubViewport.new()
	viewport.size = VIEWPORT_SIZE
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.handle_input_locally = true
	add_child(viewport)
	viewport.add_child(root)

	for _i in SETTLE_FRAMES:
		await get_tree().process_frame

	# Kalulu's explanation apparatus, everywhere it appears.
	if not bool(args.get("keep_kalulu", false)):
		_hide_helper_kalulu(root)

	if recipe == "garden_wheel":
		await _open_wheel(root, viewport, int(args.get("lesson_number", 1)))

	# Late tweaks need the scene's @onready vars, so they run after the first frames.
	if args.has("after"):
		_apply_after(root, args.get("after", []))
		# A menu popup is on screen the next frame; a minigame animates its
		# pieces in over a second or more, so those shots ask for longer.
		for _i in int(args.get("after_frames", 8)):
			await get_tree().process_frame

	var image := await _grab(viewport)
	var crop: Variant = args.get("crop", null)
	if crop is Array and (crop as Array).size() == 4:
		var c: Array = crop
		image = image.get_region(Rect2i(
			int(float(c[0]) * VIEWPORT_SIZE.x), int(float(c[1]) * VIEWPORT_SIZE.y),
			int(float(c[2]) * VIEWPORT_SIZE.x), int(float(c[3]) * VIEWPORT_SIZE.y)))
	var save_error := image.save_png(path)
	# Where every named control ended up, as fractions of the capture. The
	# manual anchors its circles and arrows to node names rather than to
	# hand-measured boxes: a button is not the same width in Italian as in
	# French, and a hand-tuned box is wrong in three languages out of four.
	var rects := _collect_rects(root, viewport)
	viewport.queue_free()

	_results.append({
		"key": key, "locale": locale, "ok": save_error == OK,
		"path": path, "rects": rects,
		"error": "" if save_error == OK else "save failed: %d" % save_error,
	})
	print("CAPTURE: %s (%s) -> %s" % [key, locale, path])


## Reads the viewport's texture, retrying until it is actually drawn.
##
## Waiting a fixed number of frames is not enough: a heavy scene may still be
## streaming fonts and textures, and the grab can land before anything is
## rasterised. The texture then comes back one flat colour and `save_png`
## succeeds on it, so the failure is silent and ends up in the PDF.
##
## Two things this deliberately does not do:
##
## * `RenderingServer.force_draw()` -- called from inside a frame it deadlocks.
## * `await RenderingServer.frame_post_draw` -- that signal stops firing when
##   the window is occluded, so the await never returns and the whole run sits
##   there until the driver's timeout kills it. `process_frame` always ticks,
##   so a stalled renderer costs a few frames and a reported failure rather
##   than a hung batch.
func _grab(viewport: SubViewport) -> Image:
	var image: Image = viewport.get_texture().get_image()
	for _attempt in GRAB_ATTEMPTS:
		if not _is_flat(image):
			return image
		await _settle()
		image = viewport.get_texture().get_image()
	push_warning("CAPTURE: viewport still blank after %d attempts" % GRAB_ATTEMPTS)
	return image


## True when two frames differ over more than a twentieth of the picture.
## Sampled small: this only has to tell "the wheel is up" from "nothing
## happened", not measure anything.
func _differs(before: Image, after: Image) -> bool:
	var a := before.duplicate() as Image
	var b := after.duplicate() as Image
	a.resize(48, 34, Image.INTERPOLATE_NEAREST)
	b.resize(48, 34, Image.INTERPOLATE_NEAREST)
	var changed: int = 0
	for y: int in a.get_height():
		for x: int in a.get_width():
			if not a.get_pixel(x, y).is_equal_approx(b.get_pixel(x, y)):
				changed += 1
	return changed > (a.get_width() * a.get_height()) / 20


## True when every pixel is the same colour, which no real screen ever is.
## Sampled on a shrunk copy: exact, and far cheaper than four megapixels.
func _is_flat(image: Image) -> bool:
	var probe := image.duplicate() as Image
	probe.resize(48, 34, Image.INTERPOLATE_NEAREST)
	var first := probe.get_pixel(0, 0)
	for y in probe.get_height():
		for x in probe.get_width():
			if not probe.get_pixel(x, y).is_equal_approx(first):
				return false
	return true


## A screen from the game itself, rather than the menus.
##
## These need two things the menus do not: an open language pack (the gardens
## read their graphemes straight out of it) and a student progression, which
## decides what is unlocked and therefore what the screen even looks like.
## Both are built here rather than by signing a real student in: a real sign-in
## would depend on save files on this machine, and the manual's screenshots
## must be the same on every machine.
func _gameplay(args: Dictionary) -> Node:
	var language: String = args.get("language", "fr_FR")
	Database.language = language
	# A pack installed on this machine has the sounds too, but only the packs
	# someone happened to download. Pointing straight at Kalulu-Languages makes
	# every pack available on any checkout -- the gardens read their graphemes
	# out of the database, and nothing here needs the audio.
	var pack_path: String = args.get("pack_path", "")
	if not pack_path.is_empty() and FileAccess.file_exists(pack_path):
		Database.db_path = pack_path
	Database.connect_to_db()
	if not Database.is_open:
		push_warning("CAPTURE: no language pack for %s (looked at %s)" % [language, Database.db_path])
		return null

	UserDataManager.student = args.get("student_name", "Alice")
	_silence_kalulu()
	var progression := StudentProgression.new()
	progression.init_unlocks()
	# Play the account forward far enough that the screen has something to
	# show: a fresh progression is one unlocked lesson and eleven grey gardens,
	# which illustrates nothing.
	var completed: int = int(args.get("lessons_completed", 0))
	for lesson: int in range(1, completed + 1):
		progression.look_and_learn_completed(lesson)
		# A lesson has one to three minigames, not always three, and
		# game_completed indexes the array directly -- 0-based. Looping 1..3
		# regardless both skipped the first game and ran off the end, which is
		# what filled the wheel with out-of-bounds errors and left it blank.
		var games: Array = progression.unlocks[lesson]["games"]
		for game: int in range(games.size()):
			progression.game_completed(lesson, game)

	# Leave the next lesson part-done, so a wheel photographed here shows the
	# three states a child sees at once: finished, next up, still locked.
	var in_progress: int = int(args.get("in_progress_games", 0))
	if in_progress > 0 and progression.unlocks.has(completed + 1):
		progression.look_and_learn_completed(completed + 1)
		var next_games: Array = progression.unlocks[completed + 1]["games"]
		for game: int in range(mini(in_progress, next_games.size())):
			progression.game_completed(completed + 1, game)
	for gate: Variant in args.get("bosses_defeated", []):
		progression.boss_completed(int(gate))
	UserDataManager.student_progression = progression

	# A minigame reads which lesson it is running from a static on its base
	# script, which the gardens screen would normally have filled in. Reached
	# through `load` rather than the global class name: a class_name that does
	# not resolve is a *parse* error, which stops the whole harness compiling
	# and takes every other screenshot down with it.
	var minigame_script: Resource = load("res://sources/minigames/base/base_minigame.gd")
	if minigame_script != null:
		minigame_script.set("transition_data", {
			"current_lesson_number": int(args.get("lesson_number", 1)),
			"minigame_number": int(args.get("minigame_number", 1)),
			"is_final_boss": bool(args.get("is_final_boss", false)),
		})

	var scene: Node = _instantiate(args.get("scene", ""))
	if scene != null and args.has("starting_garden") and "starting_garden" in scene:
		scene.set("starting_garden", int(args.get("starting_garden", 0)))
	return scene


## Every speech Kalulu offers to give, marked as already given.
##
## On a first visit Kalulu climbs out of his hole to explain the screen, and
## while he talks the whole view sits under a purple veil with his burrow in the
## corner. That is right for a child and wrong for a manual: it dims the very
## thing each screenshot is meant to show. The game already suppresses the
## explanation once a child has heard it, so the harness simply says they have.
##
## The names are the ones the code gates on: the two screens, plus one per
## minigame from Minigame.TYPE_NAMES.
const KALULU_SPEECHES: Array[String] = [
	"gardens", "brain",
	"jellyfish", "crabs", "parakeets", "monkey", "caterpillar",
	"frog", "turtles", "ants", "penguin", "boss",
]


func _silence_kalulu() -> void:
	var speeches := UserSpeeches.new()
	for name: String in KALULU_SPEECHES:
		speeches.add_speech(name)
	UserDataManager.set("_student_speeches", speeches)


## Open the minigame wheel on the viewport the screenshot is taken from.
##
## The wheel is not a scene: the gardens screen builds it in place when a child
## taps a lesson. It was first opened while the gardens sat in a staging
## viewport and then re-parented -- which re-runs `_enter_tree`, rebuilds the
## gardens, and throws the wheel away again. Intermittently: sometimes the
## rebuild lost it, sometimes it did not, and the failure looks like a perfectly
## good screenshot of the garden. So it is opened here, after mounting, and
## never moved afterwards.
##
## Lesson buttons carry no lesson number: lessons are numbered by walking every
## garden's buttons in order, so the number is recovered the same way, from how
## many lessons the gardens before this one hold.
func _open_wheel(gardens: Node, viewport: SubViewport, lesson: int) -> void:
	var garden: Object = gardens.get("current_garden")
	if garden == null:
		push_warning("CAPTURE: no current garden, cannot open the wheel")
		return
	var buttons: Array = garden.call("get_lesson_buttons")
	if buttons.is_empty():
		push_warning("CAPTURE: garden has no lesson buttons")
		return

	var first: int = 1
	var distribution: Variant = gardens.get("lesson_distribution")
	if distribution is Array:
		for before: int in range(int(garden.get("garden_index"))):
			first += int((distribution as Array)[before])
	var index: int = clampi(lesson - first, 0, buttons.size() - 1)

	# What the screen looked like before the tap, to prove the wheel arrived. A
	# wheel that fails to paint leaves the garden on screen, which the
	# blank-frame check cannot see -- it is not blank, just wrong.
	var before: Image = viewport.get_texture().get_image()
	gardens.call("_open_minigames_layout", buttons[index], first + index)
	for attempt: int in WHEEL_ATTEMPTS:
		await _settle(60)
		if _differs(before, viewport.get_texture().get_image()):
			return
		push_warning("CAPTURE: wheel has not painted yet (attempt %d)" % (attempt + 1))
	push_warning("CAPTURE: wheel never painted for lesson %d" % lesson)


func _instantiate(scene_path: String) -> Node:
	if scene_path.is_empty() or not ResourceLoader.exists(scene_path):
		return null
	var packed: PackedScene = load(scene_path)
	return packed.instantiate() if packed else null


## Builds a plausible signed-in account so the settings screens have something
## to draw. Names and codes are fixed, never random: a manual whose screenshots
## reshuffle on every build produces a meaningless diff.
func _seed_account(args: Dictionary) -> void:
	if not args.get("seed_account", false):
		return
	var settings := TeacherSettings.new()
	settings.account_type = (TeacherSettings.AccountType.PARENT
		if args.get("account_type", "teacher") == "parent"
		else TeacherSettings.AccountType.TEACHER)
	settings.education_method = TeacherSettings.EducationMethod.APP_ONLY
	settings.email = args.get("email", "marie.dupont@example.org")
	settings._language = TranslationServer.get_locale()

	var students: Dictionary[int, Array] = {}
	for entry: Dictionary in args.get("students", []):
		var device: int = int(entry.get("device", 1))
		if not students.has(device):
			students[device] = [] as Array[StudentData]
		var data := StudentData.new()
		data.name = entry.get("name", "")
		data.code = int(entry.get("code", 123))
		data.age = int(entry.get("age", 6))
		students[device].append(data)
	settings.students = students
	UserDataManager.teacher_settings = settings


## A registration step, composed inside the real registration screen.
##
## The step scenes are fragments: on their own they render as widgets floating
## on nothing, because register.tscn owns the background and the progress bar.
## So the real screen is built first and its current step swapped for the one
## being documented -- after it is alive, because register.tscn fills that
## container in its own `_ready`, which would otherwise undo the swap.
##
## `on_enter()` matters too: the flow calls it, not the step, and it is what
## fills the dropdowns. Skipping it yields an empty-looking control that is
## technically the right scene and shows nothing a reader would recognise.
func _register_step(args: Dictionary) -> Node:
	var screen: Node = _instantiate("res://sources/menus/register/register.tscn")
	var step: Node = _instantiate(args.get("scene", ""))
	if step == null:
		return null
	if step is Step:
		var data := TeacherSettings.new()
		data.account_type = (TeacherSettings.AccountType.PARENT
			if args.get("account_type", "teacher") == "parent"
			else TeacherSettings.AccountType.TEACHER)
		data.education_method = TeacherSettings.EducationMethod.APP_ONLY
		data.devices_count = int(args.get("devices_count", 1))
		data._language = TranslationServer.get_locale()
		data.email = args.get("email", "")
		# The recap step totals whatever the flow gathered, so an unseeded one
		# honestly reports zero devices and zero students -- true, and useless
		# as an illustration. Give it the same cast the rest of the manual uses.
		var seeded: Dictionary[int, Array] = {}
		for entry: Dictionary in args.get("students", []):
			var device: int = int(entry.get("device", 1))
			if not seeded.has(device):
				seeded[device] = [] as Array[StudentData]
			var student := StudentData.new()
			student.name = entry.get("name", "")
			student.code = int(entry.get("code", 123))
			student.age = int(entry.get("age", 6))
			seeded[device].append(student)
		if not seeded.is_empty():
			data.students = seeded
			data.devices_count = seeded.size()
		(step as Step).data = data
		# `question` holds a translation key with a {number} placeholder that the
		# flow -- not the step -- fills in. Left alone it renders as the literal
		# "{number}" on the page.
		if args.has("number") and "question" in step:
			var raw: String = str(step.get("question"))
			step.set("question", tr(raw).format({"number": int(args.get("number", 1))}))
	if screen == null:
		return step

	var staging := _stage(screen)
	await _settle()

	var holder: Node = screen.get_node_or_null("%Steps")
	if holder == null:
		holder = screen.get_node_or_null("Steps")
	if holder == null:
		_unstage(staging, screen)
		return step
	for child: Node in holder.get_children():
		holder.remove_child(child)
		child.queue_free()
	holder.add_child(step)
	if step.has_method("on_enter"):
		step.call("on_enter")
	await _settle(10)

	_unstage(staging, screen)
	return screen



func _stage(node: Node) -> SubViewport:
	var viewport := SubViewport.new()
	viewport.size = VIEWPORT_SIZE
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(viewport)
	viewport.add_child(node)
	return viewport


func _unstage(viewport: SubViewport, node: Node) -> void:
	viewport.remove_child(node)
	viewport.queue_free()


func _settle(frames: int = SETTLE_FRAMES) -> void:
	for _i in frames:
		await get_tree().process_frame


## The student detail popup, opened over the settings screen it belongs to.
##
## It is a hidden child of teacher_settings rather than a scene of its own, so
## the only honest way to photograph it is to build the settings screen and open
## it exactly as a tap would.
func _student_details(args: Dictionary) -> Node:
	var settings: Node = _instantiate("res://sources/menus/settings/teacher_settings.tscn")
	if settings == null:
		return null
	var staging := _stage(settings)
	await _settle()

	var popup := settings.get_node_or_null("LessonUnlocks")
	if popup != null:
		if "teacher_settings" in popup:
			popup.set("teacher_settings", settings)
		if popup.has_method("_on_device_changed"):
			popup.call("_on_device_changed", int(args.get("device", 1)))
		if popup.has_method("_on_student_changed"):
			popup.call("_on_student_changed", int(args.get("code", 123)))
		if popup is CanvasItem:
			(popup as CanvasItem).show()
	await _settle(10)
	_unstage(staging, settings)
	return settings


## Small declarative tweaks applied after the scene is alive: filling a text
## field, revealing a popup, selecting a tab. Anything more elaborate belongs in
## a named recipe, not in a string the content file can smuggle in.
func _apply_after(root: Node, steps: Array) -> void:
	for raw: Variant in steps:
		if raw is not Dictionary:
			continue
		var step: Dictionary = raw
		var target := root.get_node_or_null(NodePath(step.get("node", "")))
		if target == null:
			push_warning("CAPTURE: no node %s" % step.get("node", ""))
			continue
		match step.get("do", ""):
			"set_text":
				if "text" in target:
					target.set("text", step.get("value", ""))
			"show":
				# Popups here are CanvasLayers as often as Controls, and a
				# CanvasLayer is not a CanvasItem -- testing for CanvasItem
				# silently skipped every popup in the manual. Some carry their
				# own entry point, which does more than flip a flag.
				if target.has_method("show_popup"):
					target.call("show_popup")
				elif target.has_method("show_block"):
					target.call("show_block")
				elif "visible" in target:
					target.set("visible", true)
				else:
					push_warning("CAPTURE: cannot show %s" % target.name)
			"hide":
				if "visible" in target:
					target.set("visible", false)
			"press":
				if target is BaseButton:
					(target as BaseButton).emit_signal("pressed")
			"call":
				# A minigame only spawns its content once `_start()` runs, and
				# `_ready` gets there by awaiting Kalulu's intro speech --
				# which never ends under the harness, so the stage stays empty.
				# Calling it directly is what a played-through intro would do.
				var method: String = str(step.get("method", ""))
				if target.has_method(method):
					target.call(method)
				else:
					push_warning("CAPTURE: %s has no method %s" % [target.name, method])
			"select":
				# Settings awaits a live internet check before it selects these,
				# and that await never resolves under the harness, so the
				# dropdowns photograph empty. Pick the entry directly.
				if target is OptionButton:
					(target as OptionButton).select(int(step.get("value", 0)))


## Global rects of the scene's named Controls, normalised against the viewport.
##
## Recorded under two keys: the scene-unique name (`%NextButton`) when the
## author marked one, and always the path from the scene root
## (`Footer/TeacherButton`), because plenty of useful controls were never marked
## unique. Godot's own generated names (`@OptionButton@3058`) are skipped: they
## are renumbered on every run and would be a trap to anchor to.
func _collect_rects(root: Node, viewport: SubViewport) -> Dictionary:
	var size := Vector2(viewport.size)
	var rects: Dictionary = {}
	var ambiguous: Dictionary = {}
	var queue: Array[Node] = [root]
	while not queue.is_empty():
		var node: Node = queue.pop_back()
		for child: Node in node.get_children():
			queue.append(child)
		if node is not Control or String(node.name).begins_with("@"):
			continue
		var control := node as Control
		if not control.is_visible_in_tree():
			continue
		var rect := control.get_global_rect()
		if rect.size.x <= 0.0 or rect.size.y <= 0.0:
			continue
		var value: Array = [
			rect.position.x / size.x, rect.position.y / size.y,
			rect.size.x / size.x, rect.size.y / size.y,
		]
		var path := String(root.get_path_to(control))
		if not path.contains("@"):
			rects[path] = value
		if control.unique_name_in_owner:
			var short := "%%%s" % control.name
			# A name that is unique inside a sub-scene stops being unique once
			# that sub-scene is instanced several times -- every student card
			# carries its own %Panel1. Last-write-wins would silently hand the
			# manual one arbitrary card, so an ambiguous name is dropped
			# instead: the build then reports it as unresolved and the author
			# anchors to a full path.
			if short in ambiguous:
				pass
			elif short in rects:
				ambiguous[short] = true
				rects.erase(short)
			else:
				rects[short] = value
	return rects
