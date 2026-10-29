extends Node2D
# 16 sprites 32x48 (14 personajes + Runa + vigilante), 4 fotogramas a 8 FPS, a 30 FPS de juego.
# Fases: «reposo» (quietos) y luego «animando» (caminan y cambian de fotograma). Cada segundo escribe una línea
# JSON en --salida=<ruta>: fps, fotogramas lentos (>50 ms), el peor fotograma y la memoria que Godot dice usar.

const N_SPRITES := 16
var sprites := []
var cuadros := []
var t := 0.0
var t_seg := 0.0
var frames := 0
var max_dt := 0.0
var lentos := 0
var reposo := 20.0
var total := 80.0
var salida := ""

func _ready() -> void:
	Engine.max_fps = 30
	# fuera de pantalla: se mide sin que la ventana se vea ni robe el foco (PC en uso)
	get_window().position = Vector2i(-16000, 0)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--salida="): salida = a.substr(9)
		if a.begins_with("--reposo="): reposo = float(a.substr(9))
		if a.begins_with("--total="): total = float(a.substr(8))
	for i in N_SPRITES:
		var marcos := []
		for f in 4:
			var img := Image.create(32, 48, false, Image.FORMAT_RGBA8)
			img.fill(Color.from_hsv(float(i) / N_SPRITES, 0.6, 0.9))
			img.fill_rect(Rect2i(8, 2 + f, 16, 16), Color(0.95, 0.9, 0.8))
			img.fill_rect(Rect2i(4 + f * 2, 40, 8, 8), Color(0.1, 0.1, 0.1))
			marcos.append(ImageTexture.create_from_image(img))
		cuadros.append(marcos)
		var s := Sprite2D.new()
		s.texture = marcos[0]
		s.position = Vector2(40 + (i % 8) * 72, 90 + int(i / 8) * 140)
		add_child(s)
		sprites.append(s)
	_escribir({"evento": "inicio", "motor": "godot", "version": Engine.get_version_info().string,
		"metodo": RenderingServer.get_current_rendering_method(),
		"adaptador": RenderingServer.get_video_adapter_name(),
		"fabricante": RenderingServer.get_video_adapter_vendor(),
		"api": RenderingServer.get_video_adapter_api_version(),
		"tipo": RenderingServer.get_video_adapter_type(), "sprites": N_SPRITES,
		"ventana": [get_window().position.x, get_window().position.y]})

func _process(dt: float) -> void:
	t += dt
	t_seg += dt
	frames += 1
	max_dt = max(max_dt, dt)
	if dt > 0.05:
		lentos += 1
	var animando := t > reposo
	if animando:
		var f := int(t * 8.0) % 4
		for i in N_SPRITES:
			sprites[i].texture = cuadros[i][f]
			sprites[i].position.x = 40 + (i % 8) * 72 + sin(t * 1.5 + i) * 20.0
	if t_seg >= 1.0:
		_escribir({"t": snappedf(t, 0.1), "fase": "animando" if animando else "reposo", "frames": frames,
			"fps": Engine.get_frames_per_second(), "peor_ms": snappedf(max_dt * 1000.0, 0.1), "lentos": lentos,
			"vram_godot": Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED),
			"mem_static": Performance.get_monitor(Performance.MEMORY_STATIC)})
		t_seg = 0.0
		frames = 0
		max_dt = 0.0
		lentos = 0
	if t >= total:
		get_tree().quit()

func _escribir(d: Dictionary) -> void:
	if salida == "":
		print(JSON.stringify(d))
		return
	var fa := FileAccess.open(salida, FileAccess.READ_WRITE if FileAccess.file_exists(salida) else FileAccess.WRITE)
	fa.seek_end()
	fa.store_line(JSON.stringify(d))
	fa.close()
