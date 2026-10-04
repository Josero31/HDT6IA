# HDT6 — Evals del agente de Parachute S.A.

**CC3116 · Inteligencia Artificial — Hoja de trabajo #6**

Parachute S.A. va a poner en producción el agente que construimos en la hoja anterior y lo va a seguir iterando. Para que cada cambio futuro se pueda verificar, este repositorio cierra el ciclo de desarrollo con **evals automatizados en [promptfoo](https://www.promptfoo.dev/)** sobre las dos funcionalidades del agente:

1. **Preguntas frecuentes** (RAG sobre `data/faqs.md`).
2. **Agendar citas** de salto, que depende del pronóstico del clima y de un dictamen de seguridad.

**Entregables**

- Código de los evals: carpeta [`evals/`](evals/).
- Reporte generado por promptfoo: [`evals/reporte/reporte.html`](evals/reporte/reporte.html) (y los resultados crudos en `evals/reporte/resultados.json`).

---

## Arquitectura evaluada

En la HT5 se implementaron tres arquitecturas multiagente (centralizada, jerárquica y descentralizada). Para los evals se usa la **centralizada** (`centralizada.py`), que fue la que consideramos mejor para el alcance actual: un único orquestador expone a los cuatro especialistas como herramientas (*agents-as-tools*), así que el control y la respuesta final quedan en un solo lugar y la traza de herramientas es fácil de auditar.

```
                ┌────────────────────────────┐
                │   Orquestador Parachute    │
                └──┬────────┬────────┬───────┘
                   │        │        │        └─────────┐
 consultar_informacion  consultar_  dictaminar_   gestionar_agenda
        (FAQs)         pronostico   seguridad        (Agenda)
                        (Clima)    (Seguridad)
```

| Herramienta del orquestador | Especialista | Herramientas del especialista |
|---|---|---|
| `consultar_informacion` | FAQs | `consultar_faqs` |
| `consultar_pronostico` | Clima | `consultar_clima` (Open-Meteo) |
| `dictaminar_seguridad` | Seguridad | `evaluar_fecha` / `evaluar_condiciones` (reglas determinísticas en `core/safety.py`) |
| `gestionar_agenda` | Agenda | `agendar_cita`, `cancelar_cita`, consulta de disponibilidad |

Los diagramas de las tres arquitecturas están en [`diagramas/`](diagramas/).

## Estructura del repositorio

```
.
├── centralizada.py          # Arquitectura evaluada (orquestador + 4 especialistas)
├── jerarquica.py            # Arquitectura alternativa de la HT5
├── descentralizada.py       # Arquitectura alternativa de la HT5
├── core/                    # Lógica compartida: config, prompts, tools, clima, seguridad, agenda
├── data/
│   ├── faqs.md              # Base de conocimiento de las FAQs
│   └── citas.json.example
├── diagramas/               # SVG de las tres arquitecturas
└── evals/
    ├── promptfooconfig.yaml # Configuración de promptfoo
    ├── provider.py          # Provider Python que ejecuta el agente y devuelve la traza de herramientas
    ├── assertions/
    │   └── herramientas.js  # Aserciones de tool execution reutilizables
    ├── tests/
    │   ├── faqs.yaml        # 10 casos de preguntas frecuentes
    │   └── agenda.yaml      # 9 casos de agenda (incluye un caso mixto FAQ + agenda)
    └── reporte/             # Reporte HTML y resultados JSON generados por promptfoo
```

## Requisitos

- Python 3.10 o superior
- Node.js 18 o superior (para `npx promptfoo`)
- Una API key de un proveedor compatible con la API de OpenAI. Por defecto se usa **Groq** con `openai/gpt-oss-120b`.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # Windows: copy .env.example .env
```

Luego se edita `.env` y se coloca la llave en `API_KEY`:

```env
BASE_URL=https://api.groq.com/openai/v1
API_KEY=tu_api_key
MODEL_NAME=openai/gpt-oss-120b
# Opcional: modelo juez para factuality / context-faithfulness / llm-rubric
# GRADER_MODEL=openai/gpt-oss-120b
```

`.env` está en `.gitignore`, así que la llave no se sube al repositorio.

## Uso

### Correr el agente en consola

```bash
python centralizada.py
```

### Probar el provider con una sola pregunta

```bash
python evals/provider.py "¿Cuánto cuesta un salto tándem?"
```

Imprime la respuesta, la latencia, el uso de tokens y la traza de herramientas que ven los evals.

### Correr los evals y generar el reporte

Desde la raíz del repositorio y con el entorno virtual activado:

```bash
npx promptfoo@latest eval -c evals/promptfooconfig.yaml --no-cache \
    -o evals/reporte/reporte.html -o evals/reporte/resultados.json
```

`--no-cache` es necesario para que la latencia medida sea la real. Para explorar los resultados en el navegador:

```bash
npx promptfoo@latest view
```

## Tipos de evals

Cada aserción lleva un `metric`, así el reporte agrupa los resultados por tipo de eval.

| Métrica | Tipo de aserción en promptfoo | Qué verifica | Aserciones |
|---|---|---|---|
| `factuality` | `factuality` (model-graded) | La respuesta es consistente con la respuesta de referencia (la FAQ o el resultado esperado de la agenda). | 16 |
| `fidelidad_rag` | `context-faithfulness` (model-graded) | La respuesta de las FAQs se sostiene en el contexto que realmente devolvió `consultar_faqs`, sin inventar datos. | 4 |
| `comportamiento` | `llm-rubric` (model-graded) | Casos sin una única respuesta correcta: rechazos, pedir datos faltantes, admitir que no sabe. | 3 |
| `deterministico` | `contains`, `icontains`, `icontains-all`, `regex`, `not-icontains`, JavaScript | Cifras exactas (p. ej. `Q2,200`), horas, ID de la cita en la respuesta, palabras clave del veredicto, respuesta no vacía y sin trazas de error. | 38 + 2 por caso |
| `latencia` | `latency` | Tiempo máximo de respuesta: 20 s para una consulta de FAQ y 30–45 s para un flujo completo de agenda. | 3 |
| `tool_execution` | `javascript` sobre la traza de herramientas | Qué herramientas se llamaron, con qué argumentos, en qué orden, si fueron exitosas y cuál fue el efecto real sobre la agenda. | 27 + 1 por caso |

### Tool execution

El provider (`evals/provider.py`) envuelve cada herramienta del orquestador y de los especialistas y devuelve en `metadata.tool_calls` la traza completa de la ejecución: nivel, herramienta, argumentos, salida, si fue exitosa y su duración. Las funciones de `evals/assertions/herramientas.js` revisan esa traza:

| Función | Verifica |
|---|---|
| `llamada` | Una herramienta se llamó entre `min` y `max` veces, opcionalmente con argumentos concretos (admite `re:<regex>` y `[HOY+N]`) y con resultado exitoso. |
| `noLlamada` | Una herramienta **no** se ejecutó (p. ej. una pregunta de FAQ no debe tocar la agenda). |
| `orden` | El clima y el dictamen de seguridad ocurren **antes** de `agendar_cita`. |
| `sinErrores` | Ninguna herramienta falló por argumentos mal formados (se aplica a todos los casos). |
| `citas` | Estado final de la agenda: cantidad de citas, que exista una con ciertos campos y que no haya duplicados. |
| `idEnRespuesta` | El ID de la cita creada aparece en la respuesta al cliente. |
| `mencionaFecha` | La respuesta menciona la fecha esperada (ISO o "D de mes"). |

## Casos de prueba

**Preguntas frecuentes** (`evals/tests/faqs.yaml`)

| Caso | Qué se espera |
|---|---|
| Precio del salto tándem | Q2,200, con lo que incluye |
| Requisitos de edad y peso | 18 años, 100 kg máximo y recargo de Q250 entre 95 y 100 kg |
| Política de cancelación y reembolso | 100% con más de 48 h, 50% entre 48 y 24 h, nada con menos de 24 h |
| Qué llevar el día del salto | Identificación, ropa cómoda y zapatos cerrados (no sandalias) |
| Restricción médica (embarazo) | No puede saltar |
| Altura del salto y recargo de 14,000 pies | 10,000 pies estándar, recargo de Q600 |
| Celular o cámara durante el salto | Prohibido; el video lo hace un camarógrafo de la empresa |
| Menor de edad con permiso de los padres | No puede saltar aunque tenga permiso |
| Certificación de los instructores | Certificación USPA y mínimo 500 saltos tándem |
| Pregunta fuera de la base | No debe inventar la respuesta |

**Agenda** (`evals/tests/agenda.yaml`)

| Caso | Qué se espera |
|---|---|
| Día IDEAL con todos los datos | Se registra la cita y se entrega el ID |
| Día MARGINAL | Se registra con advertencia: solo tándem con instructor experimentado |
| Día PROHIBIDO | No se agenda y se ofrece otra fecha |
| Fecha fuera de la ventana de 16 días | No se agenda y se indica la fecha máxima |
| Falta el teléfono | Lo pide y no registra |
| Horario ocupado | No duplica y ofrece horarios libres |
| Horario inválido | Ofrece los horarios oficiales |
| Cancelar una cita existente | La cita se elimina de la agenda |
| FAQ + agenda en un solo mensaje | Da el precio del paquete con video (Q2,850) y registra la cita |

### Reproducibilidad

Para que los resultados no dependan del día en que se corren ni del clima real, el provider aísla cada caso:

- **Clima fijo.** La variable `clima` (`ideal`, `marginal`, `prohibido`) reemplaza a Open-Meteo con un escenario conocido, pero conserva la validación real del formato de fecha y de la ventana de 16 días. Con `clima: real` se consulta Open-Meteo de verdad.
- **Agenda aislada.** Cada caso usa un archivo de citas temporal, opcionalmente precargado con `citas_previas`, así que los evals nunca modifican `data/citas.json`.
- **Fechas relativas.** `[HOY+N]` se reemplaza por la fecha de hoy más N días, tanto en la pregunta como en las aserciones.

## Notas

- **Rate limit.** Los casos corren de uno en uno con 1.5 s entre ellos (`delay` en `promptfooconfig.yaml`) y el provider reintenta solo ante errores 429. Si aun así fallan casos por límite de peticiones, se puede subir el `delay`.
- **Modelo juez.** Las aserciones model-graded usan el mismo proveedor del agente. Se puede usar otro modelo como juez con `GRADER_MODEL` en `.env`.
- **Variabilidad.** Las aserciones model-graded y la latencia dependen del modelo y de la carga del proveedor, así que dos corridas pueden diferir en algunos casos aunque el agente no cambie.
