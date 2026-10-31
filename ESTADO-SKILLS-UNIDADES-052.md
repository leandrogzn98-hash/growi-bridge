# ESTADO — t-skills-unidades-052 (0.5.2, componente 4 de 5: skills como unidades)

**Fecha:** 31 oct 2026, 00:40. **Veredicto:** LISTO, verificado en instancia aislada con el runner del repo (motor ollama, $0). El diseño está en `DISENO-052-SKILLS-Y-VENTAS.md`: es una **propuesta de Claude, sin aprobar todavía por Leandro** (los componentes 1–3 sí tuvieron diseño aprobado). La app instalada no se tocó.

## Qué cambia
- **Pedir una skill por su nombre:** `"skill": "carruseles"` (o una lista de hasta 3) en el `.task.json`, en un paso de workflow o con `encolar_tarea(skill=..., entradas=...)`. Se activa siempre y primero, aunque la descripción no coincida.
- **Contrato opcional en el frontmatter** (compatible con las skills de ahora):
  ```yaml
  entradas:
    - "texto | ¿Qué escribo en la nota?"            # sin valor por defecto = obligatoria
    - "archivo | ¿Cómo se llama el archivo? | nota.txt"
  salidas:
    - nota.txt                                       # se vuelve un criterio «existe» que la revisión comprueba
    - "*.png"                                        # con comodín: frase para el revisor
  ```
- **Estadísticas por skill:** `skills_estadisticas()` sale de los `.result.json` (`skills_activadas` + `skills_pedidas`).
- **Vista:** `skills_vista()` (contrato, requisitos en este PC, estadísticas, cómo pedirla) y `/gateway/skills`.
- Parche reproducible: `parches/parche_skills_unidades_052.py` (aplicado al commit anterior da el archivo idéntico).

## LISTO (evidencia en `pruebas/evidencia/skills-unidades-052/resultado.json`; prueba: `pruebas/prueba_skills_unidades_052.py`)
| Caso | Resultado |
|---|---|
| a. Pedida por nombre | Encargo «Haz lo que dice la skill.» (no se parece a la descripción). Resultado: `skills_activadas: [nota-prueba]`, `skills_pedidas: [nota-prueba]`. Las entradas llegan al motor (`texto` dada y `archivo` por defecto `nota.txt`). La salida se convirtió en el criterio tipado `{"tipo": "existe", "archivo": "nota.txt"}`. **La revisión lo comprobó y rechazó**: el motor (Hermes en Ollama) no tiene herramientas para escribir archivos y `nota.txt` no apareció. El contrato sirvió para lo que tiene que servir: atrapar una salida que no está. |
| b. Skill que no existe | No se encola: «la skill «no-existe» no existe o no es válida en este PC (hay: carruseles, edicion-video, nota-prueba)». |
| c. Entrada obligatoria sin valor | No se encola: «falta la entrada «texto» de la skill «nota-prueba»: ¿Qué escribo en la nota?». |
| d. Paso de workflow con skill | `wf_validar` acepta el paso y el `.task.json` de la fase lleva `skill` y `entradas`. |
| e. Estadísticas | `nota-prueba`: 5 usos (2 pedidos y 3 por descripción, en las rondas de corrección), última vez y costo mediano ($0, local). |
| f. Gateway | `/gateway/skills`: 200 con token, 401 sin él; incluye «cómo pedirla» con sus entradas. |

## Corregido antes del commit
- Al anotar en el resultado qué skills pidió la tarea, usaba `task` dentro de `_write_result(result)`, donde no existe: habría fallado al escribir **cada** resultado. Ahora va en el registro de la propia skill (`reg["pedidas"]`).

## FALTA
1. **Aprobación del diseño por Leandro.** Se puede ajustar sin romper nada: es todo opcional y las skills de antes funcionan igual.
2. **Tarjeta en la app** (lista de skills con estadísticas): hoy solo `skills_vista()` y `/gateway/skills`. La UI tkinter se hará al instalar.
3. La prueba positiva con un motor con herramientas (Claude o Codex creando `nota.txt`) no se hizo: la mecánica es la misma y el caso negativo ya demuestra la comprobación.
4. Ninguna skill real (`carruseles`, `edicion-video`) declara todavía `entradas` ni `salidas`: se añaden cuando Leandro apruebe el formato.

## COMO PROBARLO
```
python pruebas\prueba_skills_unidades_052.py    # ~2 min, motor ollama ($0)
```
