# -*- coding: utf-8 -*-
"""Pruebas de la Fase 5: la capa común de canales (canales.py).

Lo frágil del §15 del diseño: emparejamiento, gramática estricta de
decisiones (B5), resolución de objetivo, el R3 intocable desde el
canal (B6), entrada exactamente-una-vez, marca de agua, ritmo,
liderazgo con época (B3), órdenes entre carriles (B1), el destino
canal de avisos con sus anti-duplicados (§7.2) y la bandeja
guardar-antes-que-enviar.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import canales


class Reloj:
    def __init__(self, t=1_760_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class Efectos:
    """Los efectos del monolito, falsos y contables."""

    def __init__(self):
        self.tareas = []
        self.decisiones = []
        self.respuestas = []
        self.existe = False
        self.falla_crear = False

    def como_dict(self):
        return {"crear_tarea": self.crear,
                "aplicar_decision": self.aplicar,
                "responder": self.responder,
                "tarea_existe": self.tarea_existe}

    def crear(self, tarea, carril):
        if self.falla_crear:
            return False, "disco lleno"
        self.tareas.append((dict(tarea), carril))
        return True, None

    def aplicar(self, aid, decision, minutos, canal):
        self.decisiones.append((aid, decision, minutos, canal))
        return {"modo": "directa", "hecho": True,
                "mensaje": "Aplicado por el circuito."}

    def responder(self, texto, meta=None):
        self.respuestas.append(texto)

    def tarea_existe(self, tid, carril):
        return self.existe


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="f5-test-")
        self.base = Path(self.tmp)
        self.reloj = Reloj()
        self.efectos = Efectos()
        self.ctx = {"cuentas": [{"id": "principal", "carril": "a"},
                                {"id": "segunda", "carril": "b"}],
                    "carril_propio": "a",
                    "dir_carril_b": str(self.base / "laneB")}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- atajos ---------------------------------------------------------

    def activar(self):
        cfg = canales.cargar_config(self.base)
        cfg["activo"] = "telegram"
        canales.guardar_config(self.base, cfg)

    def emparejar(self, remitente="424242"):
        codigo = canales.generar_codigo(self.base, "telegram",
                                        reloj=self.reloj)
        r = canales.intentar_emparejar(self.base, "telegram", remitente,
                                       codigo, reloj=self.reloj)
        self.assertEqual(r["resultado"], "emparejado")
        return codigo

    def msg(self, idm, texto, remitente="424242", cita=None, ts=None):
        return {"transporte": "telegram", "id_mensaje": str(idm),
                "remitente": remitente, "texto": texto,
                "cita_id": cita,
                "ts_transporte": self.reloj.t + 5 if ts is None else ts}

    def procesar(self, mensaje):
        return canales.procesar(self.base, mensaje,
                                self.efectos.como_dict(), self.ctx,
                                reloj=self.reloj)

    def pedido(self, aid="apr-1", nivel="R2", carril="a",
               transmitir=True, motivo="borrar la caché"):
        row = {"approval_id": aid, "nivel": nivel, "raiz": "t-x",
               "tarea": "t-x", "motivo": motivo,
               "vence_ts": self.reloj.t + 3600}
        entrada, creada = canales.ofrecer_pedido(
            self.base, row, carril, reloj=self.reloj)
        self.assertTrue(creada)
        if transmitir:
            canales.marcar_transmitido(self.base, aid, f"m-{aid}",
                                       reloj=self.reloj)
            entrada["mensaje_id"] = f"m-{aid}"
            entrada["transmitido_ts"] = self.reloj.t
        return entrada

    def eventos(self, nombre):
        return [e for e in canales.leer_registro(self.base, 500)
                if e.get("evento") == nombre]


# ---------------------------------------------------------------------------
# Emparejamiento (§4)
# ---------------------------------------------------------------------------

class TestEmparejamiento(Base):
    def test_codigo_correcto_empareja_y_quema(self):
        codigo = canales.generar_codigo(self.base, "telegram",
                                        reloj=self.reloj)
        r = canales.intentar_emparejar(self.base, "telegram", "424242",
                                       codigo, reloj=self.reloj)
        self.assertEqual(r["resultado"], "emparejado")
        cfg = canales.cargar_config(self.base)
        self.assertEqual(canales.identidad_de(cfg, "telegram"), "424242")
        # quemado: el mismo código ya no empareja a otro
        r2 = canales.intentar_emparejar(self.base, "telegram", "999",
                                        codigo, reloj=self.reloj)
        self.assertNotEqual(r2["resultado"], "emparejado")

    def test_codigo_vigente_solo_en_su_ventana(self):
        # La puerta que usa el ciclo del líder: sin código no hay
        # escucha sin emparejar; con código, solo dentro de su ventana.
        cfg = canales.cargar_config(self.base)
        self.assertFalse(canales.codigo_vigente(cfg, "telegram",
                                                reloj=self.reloj))
        canales.generar_codigo(self.base, "telegram", reloj=self.reloj)
        cfg = canales.cargar_config(self.base)
        self.assertTrue(canales.codigo_vigente(cfg, "telegram",
                                               reloj=self.reloj))
        self.reloj.t += 601
        self.assertFalse(canales.codigo_vigente(cfg, "telegram",
                                                reloj=self.reloj))

    def test_solo_se_guarda_el_hash(self):
        codigo = canales.generar_codigo(self.base, "telegram",
                                        reloj=self.reloj)
        texto = (self.base / "canales.json").read_text(encoding="utf-8")
        self.assertNotIn(codigo, texto)
        self.assertIn("sha256", texto)

    def test_codigo_incorrecto_cuenta_intento(self):
        canales.generar_codigo(self.base, "telegram", reloj=self.reloj)
        malo = "ZZZZZZZZ" if canales.forma_de_codigo("ZZZZZZZZ") else "22222222"
        r = canales.intentar_emparejar(self.base, "telegram", "1", malo,
                                       reloj=self.reloj)
        self.assertEqual(r["resultado"], "rechazado")
        self.assertEqual(r["intentos"], 1)

    def test_cinco_intentos_matan_el_codigo(self):
        codigo = canales.generar_codigo(self.base, "telegram",
                                        reloj=self.reloj)
        for i in range(5):
            canales.intentar_emparejar(self.base, "telegram", "1",
                                        "22222222", reloj=self.reloj)
        r = canales.intentar_emparejar(self.base, "telegram", "424242",
                                       codigo, reloj=self.reloj)
        self.assertEqual(r["resultado"], "sin_codigo")

    def test_codigo_expirado_no_empareja(self):
        codigo = canales.generar_codigo(self.base, "telegram",
                                        reloj=self.reloj)
        self.reloj.t += canales.CODIGO_VIGENCIA_S + 1
        r = canales.intentar_emparejar(self.base, "telegram", "424242",
                                       codigo, reloj=self.reloj)
        self.assertEqual(r["resultado"], "sin_codigo")

    def test_texto_sin_forma_de_codigo_no_gasta_intentos(self):
        codigo = canales.generar_codigo(self.base, "telegram",
                                        reloj=self.reloj)
        for texto in ("hola", "/start", "buenas tardes", "123"):
            r = canales.intentar_emparejar(self.base, "telegram", "1",
                                           texto, reloj=self.reloj)
            self.assertEqual(r["resultado"], "no_es_codigo")
        r = canales.intentar_emparejar(self.base, "telegram", "424242",
                                       codigo, reloj=self.reloj)
        self.assertEqual(r["resultado"], "emparejado")

    def test_codigo_de_otro_transporte_no_vale(self):
        codigo = canales.generar_codigo(self.base, "telegram",
                                        reloj=self.reloj)
        r = canales.intentar_emparejar(self.base, "whatsapp", "424242",
                                       codigo, reloj=self.reloj)
        self.assertEqual(r["resultado"], "sin_codigo")
        cfg = canales.cargar_config(self.base)
        self.assertIsNone(canales.identidad_de(cfg, "whatsapp"))

    def test_generar_otro_codigo_mata_el_anterior(self):
        viejo = canales.generar_codigo(self.base, "telegram",
                                       reloj=self.reloj)
        nuevo = canales.generar_codigo(self.base, "telegram",
                                       reloj=self.reloj)
        r = canales.intentar_emparejar(self.base, "telegram", "424242",
                                       viejo, reloj=self.reloj)
        self.assertNotEqual(r["resultado"], "emparejado")
        r = canales.intentar_emparejar(self.base, "telegram", "424242",
                                       nuevo, reloj=self.reloj)
        self.assertEqual(r["resultado"], "emparejado")

    def test_revocar_desempareja_al_instante(self):
        self.emparejar()
        canales.revocar(self.base, "telegram", reloj=self.reloj)
        cfg = canales.cargar_config(self.base)
        self.assertIsNone(canales.identidad_de(cfg, "telegram"))


# ---------------------------------------------------------------------------
# Gramática de decisiones (§6.3 + B5)
# ---------------------------------------------------------------------------

class TestGramatica(unittest.TestCase):
    def parse(self, texto, codigos=("XKCD",)):
        return canales.parsear_decision(texto, list(codigos))

    def test_tabla(self):
        casos = [
            ("aprobar", "aprobar"), ("Aprobar.", "aprobar"),
            ("sí", "aprobar"), ("si", None), ("ok", "aprobar"),
            ("vale", "aprobar"), ("dale", "aprobar"),
            ("hazlo", "aprobar"),
            ("rechazar", "rechazar"), ("no", "rechazar"),
            ("cancelar", "rechazar"), ("descartar", "rechazar"),
            ("aprobar XKCD", "aprobar"), ("XKCD aprobar", "aprobar"),
            ("aprobar por favor", "aprobar"),
            ("gracias, aprobar", "aprobar"),
            ("espera 30", "aplazar"), ("aplaza 30 min", "aplazar"),
            ("espera 2 h", "aplazar"), ("posponer 1 hora", "aplazar"),
            ("espera media hora", "aplazar"),
            ("espera un cuarto de hora", "aplazar"),
            ("aplazar", "aplazar_sin_duracion"),
            ("espera", "aplazar_sin_duracion"),
            ("30", "duracion"), ("30 min", "duracion"),
            ("media hora", "duracion"), ("2 horas", "duracion"),
            ("XKCD", None),
            ("si puedes revisa el log", None),
            ("sí, pero primero haz copia", "sobra"),
            ("no borres el archivo grande", "sobra"),
            ("no subas eso todavía", "sobra"),
            ("aprueba el informe y súbelo", None),
            ("revisa el informe", None),
            ("", None),
        ]
        for texto, esperado in casos:
            with self.subTest(texto=texto):
                self.assertEqual(self.parse(texto)["tipo"], esperado)

    def test_minutos_parseados(self):
        self.assertEqual(self.parse("espera 30")["minutos"], 30)
        self.assertEqual(self.parse("espera 2 h")["minutos"], 120)
        self.assertEqual(self.parse("media hora")["minutos"], 30)
        self.assertEqual(self.parse("cuarto de hora")["minutos"], 15)
        self.assertEqual(self.parse("espera 45m")["minutos"], 45)

    def test_codigo_extraido(self):
        p = self.parse("rechazar XKCD")
        self.assertEqual(p["codigo"], "XKCD")
        p = self.parse("espera 30 XKCD")
        self.assertEqual(p["codigo"], "XKCD")
        self.assertEqual(p["minutos"], 30)

    def test_codigo_corto_nunca_solo_digitos(self):
        pedidos = {}
        for _ in range(300):
            c = canales._codigo_corto_unico(pedidos)
            self.assertFalse(c.isdigit(), c)
            self.assertEqual(len(c), 4)
            pedidos[c] = {"codigo": c, "ofrecido": True,
                          "resuelto": None}
        codigos = [e["codigo"] for e in pedidos.values()]
        self.assertEqual(len(codigos), len(set(codigos)))


class TestClasificacion(unittest.TestCase):
    def test_consultas_solo_mensaje_entero(self):
        for texto in ("estado", "tablero", "pendientes", "ayuda",
                      "Estado.", "¿ayuda?"):
            with self.subTest(texto=texto):
                self.assertEqual(canales.clasificar(texto)["clase"],
                                 "consulta")
        for texto in ("estado del repo X, revísalo",
                      "tablero de anuncios de la semana",
                      "ayuda con el informe"):
            with self.subTest(texto=texto):
                self.assertEqual(canales.clasificar(texto)["clase"],
                                 "encargo")

    def test_encargos_con_no_no_son_rechazos(self):
        for texto in ("no borres el archivo grande",
                      "no subas eso todavía",
                      "si puedes revisa el log"):
            with self.subTest(texto=texto):
                self.assertEqual(canales.clasificar(texto)["clase"],
                                 "encargo")

    def test_sobra_sin_pedidos_es_encargo(self):
        c = canales.clasificar("sí, pero primero haz copia",
                               hay_pedidos_vigentes=False)
        self.assertEqual(c["clase"], "encargo")
        c = canales.clasificar("sí, pero primero haz copia",
                               hay_pedidos_vigentes=True)
        self.assertEqual(c["clase"], "aclarar")


class TestEnrutado(unittest.TestCase):
    CUENTAS = [{"id": "principal", "carril": "a"},
               {"id": "segunda", "carril": "b"}]

    def test_arroba_valido(self):
        prompt, cuenta, error = canales.enrutar(
            "@segunda revisa el log", self.CUENTAS)
        self.assertEqual((prompt, cuenta, error),
                         ("revisa el log", "segunda", None))

    def test_arroba_desconocido_es_error_y_no_crea(self):
        prompt, cuenta, error = canales.enrutar(
            "@nadie revisa el log", self.CUENTAS)
        self.assertIsNone(prompt)
        self.assertIn("principal", error)
        self.assertIn("segunda", error)

    def test_prefijo_cuenta_real(self):
        prompt, cuenta, error = canales.enrutar(
            "segunda: revisa el log", self.CUENTAS)
        self.assertEqual((prompt, cuenta), ("revisa el log", "segunda"))

    def test_prefijo_que_no_es_cuenta_es_texto_normal(self):
        texto = "nota: revisa el log a las 5"
        prompt, cuenta, error = canales.enrutar(texto, self.CUENTAS)
        self.assertEqual((prompt, cuenta, error), (texto, None, None))

    def test_sin_prefijo(self):
        prompt, cuenta, error = canales.enrutar("revisa el log",
                                                self.CUENTAS)
        self.assertEqual((prompt, cuenta, error),
                         ("revisa el log", None, None))


# ---------------------------------------------------------------------------
# La puerta de entrada: procesar (§5.1 y §5.5)
# ---------------------------------------------------------------------------

class TestProcesar(Base):
    def setUp(self):
        super().setUp()
        self.activar()

    def test_desconocido_silencio_total(self):
        r = self.procesar(self.msg("1", "hazme un informe"))
        self.assertEqual(r["resultado"], "ignorado")
        self.assertEqual(self.efectos.tareas, [])
        self.assertEqual(self.efectos.respuestas, [])

    def test_emparejar_por_el_chat_y_luego_encargo(self):
        codigo = canales.generar_codigo(self.base, "telegram",
                                        reloj=self.reloj)
        r = self.procesar(self.msg("1", codigo))
        self.assertEqual(r["resultado"], "emparejado")
        self.assertTrue(any("Emparejado" in t
                            for t in self.efectos.respuestas))
        self.reloj.t += 10
        r = self.procesar(self.msg("2", "revisa el informe"))
        self.assertEqual(r["resultado"], "encargo")
        self.assertEqual(len(self.efectos.tareas), 1)
        tarea, carril = self.efectos.tareas[0]
        self.assertEqual(tarea["tipo"], "encargo")
        self.assertEqual(tarea["canal"], "telegram")
        self.assertEqual(tarea["prompt"], "revisa el informe")
        self.assertEqual(carril, "a")
        self.assertTrue(any("Encargo recibido" in t
                            for t in self.efectos.respuestas))
        self.assertEqual(len(self.eventos("encargo_creado")), 1)

    def test_remitente_equivocado_tras_emparejar(self):
        self.emparejar()
        r = self.procesar(self.msg("7", "borra todo", remitente="666"))
        self.assertEqual(r["resultado"], "ignorado")
        self.assertEqual(self.efectos.tareas, [])
        self.assertEqual(len(self.eventos("mensaje_ignorado")), 1)

    def test_tras_revocar_el_mismo_remitente_es_desconocido(self):
        self.emparejar()
        canales.revocar(self.base, "telegram", reloj=self.reloj)
        r = self.procesar(self.msg("8", "revisa el informe"))
        self.assertEqual(r["resultado"], "ignorado")
        self.assertEqual(self.efectos.tareas, [])

    def test_duplicado_no_crea_dos_encargos(self):
        self.emparejar()
        m = self.msg("42", "revisa el informe")
        self.assertEqual(self.procesar(m)["resultado"], "encargo")
        self.assertEqual(self.procesar(m)["resultado"], "duplicado")
        self.assertEqual(len(self.efectos.tareas), 1)

    def test_tid_determinista(self):
        a = canales.tid_de_mensaje("telegram", "99", reloj=self.reloj)
        b = canales.tid_de_mensaje("telegram", "99", reloj=self.reloj)
        c = canales.tid_de_mensaje("telegram", "100", reloj=self.reloj)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("t-"))

    def test_mensaje_anterior_al_emparejamiento_es_viejo(self):
        self.emparejar()
        viejo = self.msg("3", "revisa el informe",
                         ts=self.reloj.t - 1000)
        r = self.procesar(viejo)
        self.assertEqual(r["resultado"], "viejo")
        self.assertEqual(self.efectos.tareas, [])

    def test_replay_tras_muerte_en_proceso_recrea_una_sola_vez(self):
        self.emparejar()
        # El líder murió tras registrar en_proceso y antes de crear.
        est = canales.cargar_estado(self.base, reloj=self.reloj)
        te = canales.transporte_estado(est, "telegram")
        tid = canales.tid_de_mensaje("telegram", "77", reloj=self.reloj)
        te["en_proceso"]["77"] = {"tid": tid, "ts": self.reloj.t,
                                  "carril": "a"}
        canales.guardar_estado(self.base, est)
        self.efectos.existe = False
        r = self.procesar(self.msg("77", "revisa el informe"))
        self.assertEqual(r["resultado"], "encargo")
        self.assertEqual(len(self.efectos.tareas), 1)
        self.assertEqual(self.efectos.tareas[0][0]["id"], tid)
        # Y una segunda llegada ya es duplicado limpio.
        r = self.procesar(self.msg("77", "revisa el informe"))
        self.assertEqual(r["resultado"], "duplicado")
        self.assertEqual(len(self.efectos.tareas), 1)

    def test_en_proceso_con_tarea_existente_no_recrea(self):
        self.emparejar()
        est = canales.cargar_estado(self.base, reloj=self.reloj)
        te = canales.transporte_estado(est, "telegram")
        tid = canales.tid_de_mensaje("telegram", "78", reloj=self.reloj)
        te["en_proceso"]["78"] = {"tid": tid, "ts": self.reloj.t,
                                  "carril": "a"}
        canales.guardar_estado(self.base, est)
        self.efectos.existe = True
        r = self.procesar(self.msg("78", "revisa el informe"))
        self.assertEqual(r["resultado"], "duplicado")
        self.assertEqual(self.efectos.tareas, [])

    def test_estado_reconstruido_cursor_al_final(self):
        ent = self.base / "canal-entrantes.jsonl"
        ent.write_text('{"x": 1}\n{"x": 2}\n', encoding="utf-8")
        est = canales.cargar_estado(self.base, reloj=self.reloj)
        te = canales.transporte_estado(est, "telegram")
        self.assertEqual(te["cursor"]["byte"], ent.stat().st_size)
        self.assertEqual(te["marca_agua_ts"], self.reloj.t)

    def test_sin_texto_responde_una_vez_por_hora(self):
        self.emparejar()
        r = self.procesar(self.msg("5", None))
        self.assertEqual(r["resultado"], "no_texto")
        self.assertEqual(len(self.efectos.respuestas), 1)
        r = self.procesar(self.msg("6", None))
        self.assertEqual(r["resultado"], "no_texto")
        self.assertEqual(len(self.efectos.respuestas), 1)
        self.assertEqual(self.efectos.tareas, [])

    def test_consulta_estado_responde_sin_crear_tarea(self):
        self.emparejar()
        r = self.procesar(self.msg("9", "estado"))
        self.assertEqual(r["resultado"], "consulta")
        self.assertEqual(self.efectos.tareas, [])
        self.assertTrue(any("Modo:" in t
                            for t in self.efectos.respuestas))

    def test_encargo_al_carril_b_deriva_con_md(self):
        self.emparejar()
        r = self.procesar(self.msg("10", "@segunda revisa el log"))
        self.assertEqual(r["resultado"], "encargo")
        tarea, carril = self.efectos.tareas[0]
        self.assertEqual(carril, "b")
        self.assertEqual(tarea["lane"], "b")
        md = Path(tarea["archivos"][0])
        self.assertTrue(md.exists())
        self.assertIn("revisa el log", md.read_text(encoding="utf-8"))

    def test_fallo_al_crear_no_finge_exito(self):
        self.emparejar()
        self.efectos.falla_crear = True
        r = self.procesar(self.msg("11", "revisa el informe"))
        self.assertEqual(r["resultado"], "error_creacion")
        self.assertTrue(any("No pude registrar" in t
                            for t in self.efectos.respuestas))
        self.assertFalse(any("Encargo recibido" in t
                             for t in self.efectos.respuestas))


# ---------------------------------------------------------------------------
# Decisiones por el canal (§6)
# ---------------------------------------------------------------------------

class TestDecisiones(Base):
    def setUp(self):
        super().setUp()
        self.activar()
        self.emparejar()

    def test_decision_directa_con_codigo(self):
        e = self.pedido()
        r = self.procesar(self.msg("1", f"aprobar {e['codigo']}"))
        self.assertEqual(r["resultado"], "decision")
        self.assertEqual(self.efectos.decisiones,
                         [("apr-1", "aprobar", None, "telegram")])
        # La confirmación lleva el mensaje literal del circuito.
        self.assertTrue(any("Aplicado por el circuito." in t
                            for t in self.efectos.respuestas))
        self.assertTrue(any(e["codigo"] in t
                            for t in self.efectos.respuestas))

    def test_unico_pendiente_sin_codigo(self):
        self.pedido()
        r = self.procesar(self.msg("1", "sí"))
        self.assertEqual(r["resultado"], "decision")
        self.assertEqual(len(self.efectos.decisiones), 1)

    def test_dos_pendientes_si_sin_codigo_no_decide_nada(self):
        self.pedido("apr-1")
        self.pedido("apr-2")
        r = self.procesar(self.msg("1", "sí"))
        self.assertEqual(r["resultado"], "sin_objetivo")
        self.assertEqual(self.efectos.decisiones, [])
        self.assertEqual(len(self.eventos("decision_sin_objetivo")), 1)

    def test_cita_gana_al_codigo(self):
        e1 = self.pedido("apr-1")
        e2 = self.pedido("apr-2")
        r = self.procesar(self.msg("1", f"aprobar {e2['codigo']}",
                                   cita="m-apr-1"))
        self.assertEqual(r["resultado"], "decision")
        self.assertEqual(self.efectos.decisiones[0][0], "apr-1")

    def test_pedido_no_transmitido_no_es_objetivo(self):
        self.pedido(transmitir=False)
        r = self.procesar(self.msg("1", "aprobar"))
        self.assertEqual(r["resultado"], "sin_objetivo")
        self.assertEqual(self.efectos.decisiones, [])

    def test_pedido_resuelto_en_la_app_deja_de_contar(self):
        self.pedido("apr-1")
        self.pedido("apr-2")
        canales.reconciliar_pedidos(
            self.base, "a",
            lambda aid: "aprobada" if aid == "apr-2" else "pendiente",
            reloj=self.reloj)
        # apr-2 ya no cuenta: «sí» decide apr-1 como único.
        r = self.procesar(self.msg("1", "sí"))
        self.assertEqual(r["resultado"], "decision")
        self.assertEqual(self.efectos.decisiones[0][0], "apr-1")

    def test_r3_por_cita_no_toca_el_circuito(self):
        e = self.pedido(nivel="R3", transmitir=True)
        self.assertFalse(e["ofrecido"])
        self.assertIsNone(e["codigo"])
        r = self.procesar(self.msg("1", "aprobar", cita="m-apr-1"))
        self.assertEqual(r["resultado"], "r3_no_ofrecida")
        self.assertEqual(self.efectos.decisiones, [])
        self.assertTrue(any("R3" in t and "app" in t
                            for t in self.efectos.respuestas))
        self.assertEqual(
            len(self.eventos("decision_r3_no_ofrecida")), 1)
        # El pedido sigue intacto: ni resuelto ni con código.
        datos = canales.cargar_pedidos(self.base)
        entrada = datos["pedidos"]["apr-1"]
        self.assertIsNone(entrada["resuelto"])
        self.assertIsNone(entrada["codigo"])

    def test_aplazar_sin_duracion_pregunta_y_completa(self):
        e = self.pedido()
        r = self.procesar(self.msg("1", "espera"))
        self.assertEqual(r["resultado"], "aplazar_pregunta")
        self.assertEqual(self.efectos.decisiones, [])
        self.reloj.t += 60
        r = self.procesar(self.msg("2", "30"))
        self.assertEqual(r["resultado"], "decision")
        self.assertEqual(self.efectos.decisiones,
                         [("apr-1", "aplazar", 30, "telegram")])

    def test_duracion_suelta_aplaza_el_unico(self):
        self.pedido()
        r = self.procesar(self.msg("1", "media hora"))
        self.assertEqual(r["resultado"], "decision")
        self.assertEqual(self.efectos.decisiones,
                         [("apr-1", "aplazar", 30, "telegram")])

    def test_a_medias_expira(self):
        self.pedido()
        self.procesar(self.msg("1", "espera"))
        self.assertIsNotNone(
            canales.decision_en_curso(self.base, reloj=self.reloj))
        self.reloj.t += canales.A_MEDIAS_S + 1
        self.assertIsNone(
            canales.decision_en_curso(self.base, reloj=self.reloj))

    def test_a_medias_se_descarta_con_otro_mensaje(self):
        self.pedido()
        self.procesar(self.msg("1", "espera"))
        r = self.procesar(self.msg("2", "revisa el informe"))
        self.assertEqual(r["resultado"], "encargo")
        self.assertEqual(self.efectos.decisiones, [])
        self.assertIsNone(
            canales.decision_en_curso(self.base, reloj=self.reloj))

    def test_zona_gris_pregunta_y_encargo(self):
        self.pedido()
        r = self.procesar(self.msg("1", "sí, pero primero haz copia"))
        self.assertEqual(r["resultado"], "aclarar")
        self.assertEqual(self.efectos.decisiones, [])
        self.assertEqual(self.efectos.tareas, [])
        r = self.procesar(self.msg("2", "encargo"))
        self.assertEqual(r["resultado"], "encargo")
        self.assertEqual(len(self.efectos.tareas), 1)
        self.assertEqual(self.efectos.tareas[0][0]["prompt"],
                         "sí, pero primero haz copia")

    def test_zona_gris_pregunta_y_el_pedido(self):
        self.pedido()
        self.procesar(self.msg("1", "sí, pero primero haz copia"))
        r = self.procesar(self.msg("2", "el pedido"))
        self.assertEqual(r["resultado"], "decision")
        self.assertEqual(self.efectos.decisiones,
                         [("apr-1", "aprobar", None, "telegram")])

    def test_ofrecer_es_idempotente_y_conserva_codigo(self):
        e1 = self.pedido(transmitir=False)
        row = {"approval_id": "apr-1", "nivel": "R2", "raiz": "t-x",
               "tarea": "t-x", "motivo": "otro motivo",
               "vence_ts": self.reloj.t + 10}
        e2, creada = canales.ofrecer_pedido(self.base, row, "a",
                                            reloj=self.reloj)
        self.assertFalse(creada)
        self.assertEqual(e2["codigo"], e1["codigo"])


# ---------------------------------------------------------------------------
# Ritmo (§5.6)
# ---------------------------------------------------------------------------

class TestRitmo(Base):
    def setUp(self):
        super().setUp()
        self.activar()
        cfg = canales.cargar_config(self.base)
        cfg["limites"] = {"mensajes_hora": 30, "encargos_hora": 2,
                          "consultas_hora": 12}
        canales.guardar_config(self.base, cfg)
        self.emparejar()

    def test_encargos_se_cortan_y_las_decisiones_no(self):
        self.assertEqual(self.procesar(
            self.msg("1", "encargo uno"))["resultado"], "encargo")
        self.assertEqual(self.procesar(
            self.msg("2", "encargo dos"))["resultado"], "encargo")
        r = self.procesar(self.msg("3", "encargo tres"))
        self.assertEqual(r["resultado"], "ritmo")
        self.assertEqual(len(self.efectos.tareas), 2)
        # La decisión pasa aunque el ritmo de encargos esté cortado.
        e = self.pedido()
        r = self.procesar(self.msg("4", f"aprobar {e['codigo']}"))
        self.assertEqual(r["resultado"], "decision")
        self.assertEqual(len(self.efectos.decisiones), 1)


# ---------------------------------------------------------------------------
# Liderazgo (§2.2, B3) y órdenes entre carriles (§6.4, B1)
# ---------------------------------------------------------------------------

class TestLiderazgo(Base):
    def test_epoca_crece_y_el_viejo_lider_no_actua(self):
        e1 = canales.tomar_liderazgo(self.base, "a", 111,
                                     reloj=self.reloj)
        self.assertTrue(canales.soy_lider(self.base, "a", e1))
        e2 = canales.tomar_liderazgo(self.base, "b", 222,
                                     reloj=self.reloj)
        self.assertEqual(e2, e1 + 1)
        self.assertFalse(canales.soy_lider(self.base, "a", e1))
        self.assertTrue(canales.soy_lider(self.base, "b", e2))

    def test_paso_no_roba_un_liderazgo_vivo(self):
        canales.tomar_liderazgo(self.base, "b", 222, reloj=self.reloj)
        es, _ep = canales.paso_liderazgo(self.base, "a", 111,
                                         reloj=self.reloj)
        self.assertFalse(es)

    def test_paso_toma_un_liderazgo_vencido(self):
        canales.tomar_liderazgo(self.base, "b", 222, reloj=self.reloj)
        self.reloj.t += canales.LIDER_VIEJO_S + 1
        es, ep = canales.paso_liderazgo(self.base, "a", 111,
                                        reloj=self.reloj)
        self.assertTrue(es)
        self.assertTrue(canales.soy_lider(self.base, "a", ep))


class TestOrdenes(Base):
    def test_una_sola_orden_en_vuelo_por_aprobacion(self):
        o1, c1 = canales.crear_orden(self.base, "apr-9", "aprobar",
                                     None, "telegram", reloj=self.reloj)
        o2, c2 = canales.crear_orden(self.base, "apr-9", "rechazar",
                                     None, "telegram", reloj=self.reloj)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(o1["id"], o2["id"])
        self.assertEqual(o2["decision"], "aprobar")

    def test_aplicar_una_vez_y_resultado_devuelto(self):
        orden, _ = canales.crear_orden(self.base, "apr-9", "aprobar",
                                       None, "telegram",
                                       reloj=self.reloj)
        llamadas = []

        def decidir(aid, dec, canal, mins):
            llamadas.append((aid, dec, canal, mins))
            return True, "aplicada"

        r1 = canales.aplicar_orden_local(self.base, orden, decidir,
                                         reloj=self.reloj)
        self.assertTrue(r1["hecho"])
        r2 = canales.aplicar_orden_local(self.base, orden, decidir,
                                         reloj=self.reloj)
        self.assertEqual(r2["mensaje"], "aplicada")
        self.assertEqual(len(llamadas), 1)

    def test_claim_sin_resultado_se_resuelve_por_el_circuito(self):
        # Murió entre tomar el claim y aplicar: no hay resultado. La
        # reaplicación llama a decidir igualmente: el circuito, sobre
        # una fila ya resuelta, devuelve la tardía sin cambiar nada.
        self.assertTrue(canales.tomar_claim(self.base, "apr-9",
                                            reloj=self.reloj))
        self.assertFalse(canales.tomar_claim(self.base, "apr-9",
                                             reloj=self.reloj))
        orden, _ = canales.crear_orden(self.base, "apr-9", "aprobar",
                                       None, "telegram",
                                       reloj=self.reloj)
        llamadas = []

        def decidir(aid, dec, canal, mins):
            llamadas.append(aid)
            return False, "tardía, descartada: no se ejecutó nada"

        r = canales.aplicar_orden_local(self.base, orden, decidir,
                                        reloj=self.reloj)
        self.assertEqual(llamadas, ["apr-9"])
        self.assertIn("tardía", r["mensaje"])

    def test_confirmacion_asincrona(self):
        orden, _ = canales.crear_orden(self.base, "apr-9", "aprobar",
                                       None, "telegram",
                                       reloj=self.reloj)
        canales.aplicar_orden_local(
            self.base, orden, lambda *a: (True, "ok"), reloj=self.reloj)
        pend = canales.ordenes_para_confirmar(self.base)
        self.assertEqual([p["id"] for p in pend], [orden["id"]])
        canales.marcar_confirmada(self.base, orden["id"])
        self.assertEqual(canales.ordenes_para_confirmar(self.base), [])


# ---------------------------------------------------------------------------
# Bandeja saliente (§7.5) y destino canal (§7)
# ---------------------------------------------------------------------------

class TestBandeja(Base):
    def test_guardar_antes_que_enviar(self):
        m = canales.encolar_saliente(self.base, "aviso", "hola",
                                     nivel="accion", reloj=self.reloj)
        pend = canales.salientes_pendientes(self.base)
        self.assertEqual(len(pend), 1)
        ruta, datos = pend[0]
        self.assertTrue(ruta.exists())  # ya está en disco, sin enviar
        self.assertEqual(datos["texto"], "hola")
        self.assertEqual(datos["id"], m["id"])
        self.assertTrue(canales.retirar_saliente(ruta))
        self.assertEqual(canales.salientes_pendientes(self.base), [])

    def test_cinco_intentos_a_fallidos(self):
        canales.encolar_saliente(self.base, "aviso", "hola",
                                 nivel="accion", reloj=self.reloj)
        ruta, _ = canales.salientes_pendientes(self.base)[0]
        for _ in range(4):
            self.assertEqual(
                canales.registrar_intento_saliente(
                    self.base, ruta, reloj=self.reloj), "reintentar")
        self.assertEqual(
            canales.registrar_intento_saliente(
                self.base, ruta, reloj=self.reloj), "fallido")
        self.assertEqual(canales.salientes_pendientes(self.base), [])
        fallidos = list((self.base / "canal-salientes"
                         / "fallidos").glob("*.json"))
        self.assertEqual(len(fallidos), 1)

    def test_info_se_descarta_con_la_bandeja_llena_accion_no(self):
        for i in range(canales.LIMITE_SALIENTES_INFO + 1):
            canales.encolar_saliente(self.base, "aviso", f"i{i}",
                                     nivel="info", reloj=self.reloj)
        self.assertIsNone(canales.encolar_saliente(
            self.base, "aviso", "info de más", nivel="info",
            reloj=self.reloj))
        self.assertIsNotNone(canales.encolar_saliente(
            self.base, "aviso", "acción", nivel="accion",
            reloj=self.reloj))


class TestDestinoCanal(Base):
    def setUp(self):
        super().setUp()
        self.activar()
        self.destino = canales.DestinoCanal(self.base)

    def aviso(self, tipo="canal_prueba", nivel="info", **kw):
        d = {"id": "av-1", "ts": self.reloj.t, "tipo": tipo,
             "nivel": nivel, "cuenta": None, "raiz": None,
             "tarea": None, "texto": "texto del aviso"}
        d.update(kw)
        return d

    def test_sin_emparejar_no_encola(self):
        self.assertFalse(self.destino.disponible())
        self.assertFalse(self.destino.enviar(self.aviso(nivel="accion")))
        self.assertEqual(canales.salientes_pendientes(self.base), [])

    def test_accion_siempre_info_solo_suscritos(self):
        self.emparejar()
        self.assertTrue(self.destino.disponible())
        self.assertTrue(self.destino.enviar(
            self.aviso(tipo="lo_que_sea", nivel="accion")))
        pend = canales.salientes_pendientes(self.base)
        self.assertTrue(pend[0][1]["texto"].startswith("⚠️"))
        self.assertFalse(self.destino.enviar(
            self.aviso(tipo="tipo_no_suscrito", nivel="info")))
        self.assertTrue(self.destino.enviar(
            self.aviso(tipo="canal_prueba", nivel="info")))

    def test_encargo_terminado_no_duplica_el_resumen(self):
        self.emparejar()
        # Sin reloj inyectado: DestinoCanal.enviar también lee la hora
        # real al comprobar la marca.
        canales.marcar_resumen_encolado(self.base, "enc-1")
        self.assertFalse(self.destino.enviar(self.aviso(
            tipo="encargo_terminado", raiz="enc-1")))
        self.assertTrue(self.destino.enviar(self.aviso(
            tipo="encargo_terminado", raiz="enc-2")))


class TestSaneado(unittest.TestCase):
    def test_resumen_error_quita_el_token(self):
        token = "123456789:AAHcanarycanarycanarycanarycanary"
        s = canales.resumen_error(
            f"fallo al llamar a https://api.telegram.org/bot{token}/x",
            secretos_conocidos=(token,))
        self.assertNotIn(token, s)
        self.assertNotIn("AAHcanary", s)

    def test_resumen_error_de_excepcion_solo_tipo(self):
        token = "123456789:AAHcanarycanarycanarycanarycanary"
        s = canales.resumen_error(
            RuntimeError(f"la url lleva {token}"))
        self.assertEqual(s, "RuntimeError")
        self.assertNotIn(token, s)

    def test_enmascarar(self):
        self.assertEqual(canales.enmascarar("424242"), "•••4242")
        self.assertEqual(canales.enmascarar("12"), "•••")
        self.assertEqual(canales.enmascarar(None), "•••")


if __name__ == "__main__":
    unittest.main()
